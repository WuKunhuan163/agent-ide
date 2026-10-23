"""Verb dispatch. Thin on purpose: it wires layers, it does not decide anything.

Four verbs, split by intent rather than by object:

``read``
    the single submission entry point -- plan, submit, poll, deliver;
``fetch``
    finish what a previous run could not: poll again from the saved handles and
    download whatever is still missing.  Idempotent, so running it twice is free;
``keys``
    the cloud credential (``set`` / ``status`` / ``delete``);
``config``
    every tunable, via ``config get|set|unset|reset|list``.

There is deliberately no ``runs`` verb and no ``clean`` verb: the batch query returns
four fields per file and cannot stand in for history, and the only products that ever
exist live inside a run directory.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import mode as mode_pkg
from .auth import credentials
from .config import commands as config_commands
from .config.resolve import ConfigError, parse_set_flag, resolve
from .deliver import emit, fetch
from .endpoint.client import HttpEndpoint
from .endpoint.errors import ApiError
from .endpoint.models import Job, Source
from .plan import planner, probe, quota
from .run import store
from .run.scheduler import Scheduler, job_lines
from .util import log, paths
from .util.exit_codes import FAILED as EXIT_FAILED
from .util.exit_codes import OK as EXIT_OK
from .util.exit_codes import PARTIAL as EXIT_PARTIAL
from .util.exit_codes import USAGE as EXIT_USAGE
from .util.ids import new_job_id


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #

def _shared_flags() -> argparse.ArgumentParser:
    """The global flags, mirrored onto every verb.

    ``--id`` is required by every command, and both ``read`` and ``fetch`` take
    ``--token``; forcing them to be typed before the verb is a needless trap.  The
    mirrored copies use ``SUPPRESS`` defaults so that omitting them after the verb
    leaves the value parsed at the top level untouched.
    """
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--id", default=argparse.SUPPRESS)
    shared.add_argument("--token", default=argparse.SUPPRESS)
    shared.add_argument("--flash", action="store_true", default=argparse.SUPPRESS)
    shared.add_argument("--set", action="append", default=argparse.SUPPRESS, metavar="KEY=VALUE")
    shared.add_argument("-v", "--verbose", action="store_true", default=argparse.SUPPRESS)
    return shared


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-reader",
        description="Read PDFs (or URLs) through the MinerU endpoint and keep the products on disk.",
    )
    parser.add_argument("--id", required=True, help="agent id this skill runs as")
    parser.add_argument("--token", default=None, help="one-off cloud token (overrides the stored one)")
    parser.add_argument("--flash", action="store_true",
                        help="force the free flash channel (10MB / 20 pages / markdown only)")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="override a parameter for this invocation only (repeatable)")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")

    verbs = parser.add_subparsers(dest="verb", required=True)
    shared = _shared_flags()

    read = verbs.add_parser("read", parents=[shared], help="submit and deliver")
    source = read.add_mutually_exclusive_group(required=True)
    source.add_argument("-p", "--pdf", nargs="+", help="local file(s)")
    source.add_argument("-u", "--url", nargs="+", help="URL(s) for the server to fetch")
    read.add_argument("-o", "--output", default=None,
                      help="directory for this run (used verbatim, no implicit suffix)")
    read.add_argument("--pages", default=None,
                      help="page selection for a single source, e.g. 1-200 or 2,4-6; "
                           "each span becomes its own submission")
    read.add_argument("--ocr", action="store_true", default=None, help="enable OCR")
    read.add_argument("--lang", default=None, help="document language (default: endpoint's ch)")
    read.add_argument("--model", default=None,
                      choices=["pipeline", "vlm", "html"], help="model version")

    fetch_cmd = verbs.add_parser("fetch", parents=[shared], help="resume a run and download what is missing")
    fetch_cmd.add_argument("--run", default=None, help="run id, or a path to a run directory")
    fetch_cmd.add_argument("--batch", default=None, help="precision batch id (works without local state)")
    fetch_cmd.add_argument("-o", "--output", default=None, help="directory for a --batch rescue")

    keys = verbs.add_parser("keys", parents=[shared], help="cloud credential")
    keys.add_argument("keys_action", choices=["set", "status", "delete"])
    keys.add_argument("value", nargs="?", default=None, help="the token, for `keys set`")

    cfg = verbs.add_parser("config", parents=[shared], help="inspect or change any parameter")
    cfg.add_argument("config_action", choices=["list", "get", "set", "unset", "reset"])
    cfg.add_argument("key", nargs="?", default=None, help="parameter key, e.g. precision.split_page_limit")
    cfg.add_argument("value", nargs="?", default=None, help="new value, for `config set`")
    cfg.add_argument("--markdown", action="store_true", help="render the parameter table as markdown")
    return parser


# --------------------------------------------------------------------------- #
# entry
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if getattr(args, "verbose", False):
        log.set_level("debug")

    try:
        cli_sets = parse_set_flag(getattr(args, "set", []) or [])
    except ConfigError as exc:
        log.error(str(exc))
        return EXIT_USAGE

    try:
        if args.verb == "config":
            return config_commands.run(args, cli_sets)
        if args.verb == "keys":
            return cmd_keys(args)
        if args.verb == "read":
            return cmd_read(args, cli_sets)
        if args.verb == "fetch":
            return cmd_fetch(args, cli_sets)
    except ConfigError as exc:
        log.error(f"configuration error: {exc}")
        return EXIT_USAGE
    except KeyboardInterrupt:
        log.warn("interrupted")
        return 130
    parser.error("unknown verb")
    return EXIT_USAGE


# --------------------------------------------------------------------------- #
# keys
# --------------------------------------------------------------------------- #

def cmd_keys(args) -> int:
    if args.keys_action == "set":
        if not args.value:
            log.error("keys set needs the token as an argument")
            return EXIT_USAGE
        credentials.save_token(args.value.strip())
        cred = credentials.resolve_credential()
        log.info(f"token stored in the skill's data directory (0600); channel {cred.channel()}")
        return EXIT_OK
    if args.keys_action == "delete":
        removed = credentials.delete_token()
        cred = credentials.resolve_credential()
        log.info(("token deleted" if removed else "no stored token")
                 + f"; channel {cred.channel()}")
        return EXIT_OK
    cred = credentials.resolve_credential()
    if cred.present:
        log.info(f"token {cred.masked()} from {cred.origin}; channel {cred.channel()}")
    else:
        log.info(f"no token; channel {cred.channel()} (set one with `keys set <token>`)")
    log.debug("the endpoint exposes no usage endpoint, so no quota figure can be read")
    return EXIT_OK


# --------------------------------------------------------------------------- #
# read
# --------------------------------------------------------------------------- #

def _check_pages(pages: str) -> None:
    """Validate the selection's syntax before anything is fetched or submitted.

    A comma list is no longer a channel limitation: every span becomes a job of its own
    and is uploaded as the file it stands for, so flash can read '2,4-6' too.
    """
    planner.parse_selection(pages)


def cmd_read(args, cli_sets: dict[str, str]) -> int:
    cfg = resolve(cli_sets=cli_sets)
    cred = credentials.resolve_credential(args.token)
    chosen = mode_pkg.decide_mode(args.flash, cred.present)
    caps = mode_pkg.caps_for(chosen, cfg)

    sources = list(args.pdf or []) + list(args.url or [])
    if args.pages and len(sources) != 1:
        log.error("--pages applies to a single source only")
        return EXIT_USAGE
    if args.pages:
        _check_pages(args.pages)

    if chosen is mode_pkg.Mode.FLASH and not args.flash:
        log.warn("no token found: falling back to flash (20 pages / 10MB / markdown only, no images)")
    if chosen is mode_pkg.Mode.PRECISION and not cred.present:
        log.error("precision mode needs a token; run `keys set <token>` or pass --token")
        return EXIT_USAGE

    client = HttpEndpoint(
        token=cred.token,
        request_timeout=cfg.common.request_timeout_s,
        upload_timeout=cfg.common.upload_timeout_s,
    )
    try:
        local = [probe.materialise(client, value) for value in sources]
        plan_result = planner.plan(local, caps, pages=args.pages)
    except FileNotFoundError as exc:
        log.error(str(exc))
        return EXIT_FAILED
    except ApiError as exc:
        log.error(f"could not fetch a source: {exc.describe()}")
        return EXIT_FAILED

    for source, reason in plan_result.rejected:
        log.error(f"refused: {reason}")
    if not plan_result.jobs:
        log.error("nothing left to submit")
        return EXIT_FAILED

    quota.prewarn(plan_result.jobs, caps, cfg)

    options = {
        "ocr": args.ocr,
        "language": args.lang,
        "model": args.model,
        "formula": True,
        "table": True,
    }
    record = store.create(chosen.value, options, paths.resolve_arg(args.output) if args.output else None)
    run_dir = Path(record.output_dir)

    # the run handle, and the first line of the run: the record is already on disk, so this
    # is what a killed process can be resumed from.  It is printed before polling starts.
    log.info(f"run {record.run_id} ({record.mode}) -> {run_dir}")
    log.debug(quota.describe(caps, cfg))

    scheduler = Scheduler(client, cfg, caps, record, options)
    exit_code = scheduler.run(plan_result.jobs)

    delivered = materialize(record, client, caps, run_dir)
    quota.commit(record.jobs, caps, cfg.common.quota_reset_tz)
    _finish(record, run_dir, delivered, exit_code)
    for line in scheduler.summary().splitlines():
        log.info(line)
    log_result(record, delivered)
    return exit_code


def log_result(record, delivered: int) -> None:
    """The closing line: what the run amounted to, and where its summary is.

    Nothing goes to stdout any more, so this line and the exit code are what a caller
    gets back; the per-job ``ok``/``FAIL`` lines just above it come from
    ``scheduler.summary()``, and ``exit_codes`` keeps its usual meaning.
    """
    done = sum(1 for job in record.jobs if job.state == "done")
    failed = sum(1 for job in record.jobs if job.state == "failed")
    log.info(f"{done}/{len(record.jobs)} done, {failed} failed, {delivered} written; "
             f"summary at {Path(record.output_dir) / 'summary.json'}")


def materialize(record, client: HttpEndpoint, caps, run_dir: Path) -> int:
    """Download and write every finished job that has not been written yet."""
    written = 0
    for job in record.jobs:
        if job.state != "done" or emit.already_materialized(job):
            continue
        try:
            if job.zip_url and caps.has_zip:
                product = fetch.fetch_zip(client, job.zip_url)
            elif job.markdown_url:
                product = fetch.fetch_markdown(client, job.markdown_url)
            else:
                log.warn(f"{job.name}: finished but the endpoint handed back no product")
                continue
            emit.write_job(run_dir, job, product, caps)
            written += 1
        except ApiError as exc:
            log.error(f"{job.name}: could not collect the product ({exc.describe()})")
    return written


def _finish(record, run_dir: Path, delivered: int, exit_code: int) -> None:
    record.finished_at = time.time()
    record.exit_code = exit_code
    store.save(record)
    emit.write_summary(run_dir, record)


# --------------------------------------------------------------------------- #
# fetch
# --------------------------------------------------------------------------- #

def cmd_fetch(args, cli_sets: dict[str, str]) -> int:
    cfg = resolve(cli_sets=cli_sets)
    cred = credentials.resolve_credential(args.token)

    if args.run:
        try:
            record = store.load(args.run)
        except FileNotFoundError as exc:
            log.error(str(exc))
            return EXIT_FAILED
    elif args.batch:
        record = store.create("precision", {}, paths.resolve_arg(args.output) if args.output else None)
        record.batch_ids = [args.batch]
    else:
        log.error("fetch needs --run <run_id> or --batch <batch_id>")
        return EXIT_USAGE

    chosen = mode_pkg.Mode(record.mode)
    caps = mode_pkg.caps_for(chosen, cfg)

    # Only reach for the server when something is genuinely outstanding; a run whose
    # products are already on disk must not demand a token just to say "nothing to do".
    outstanding = [job for job in record.jobs
                   if job.state == "done" and not emit.already_materialized(job)]
    needs_server = bool(outstanding) or not record.jobs
    if needs_server and caps.needs_token and not cred.present:
        log.error("this run used precision mode and needs the same token; run `keys set <token>`")
        return EXIT_USAGE

    client = HttpEndpoint(
        token=cred.token,
        request_timeout=cfg.common.request_timeout_s,
        upload_timeout=cfg.common.upload_timeout_s,
    )
    run_dir = Path(record.output_dir)

    if caps.has_zip and needs_server and record.batch_ids:
        refreshed = refresh_from_batches(record, client)
        log.info(f"re-asked {len(record.batch_ids)} batch(es); {refreshed} job state(s) updated")

    delivered = materialize(record, client, caps, run_dir)
    done = sum(1 for job in record.jobs if job.state == "done")
    if not record.jobs and args.batch:
        log.warn("the batch reported no files")
    exit_code = EXIT_OK if record.jobs and done == len(record.jobs) else (
        EXIT_PARTIAL if done else EXIT_FAILED)
    _finish(record, run_dir, delivered, exit_code)
    log.debug(f"fetch: {done}/{len(record.jobs)} complete, {delivered} product(s) written")
    for line in job_lines(record):
        log.info(line)
    log_result(record, delivered)
    return exit_code


def refresh_from_batches(record, client: HttpEndpoint) -> int:
    """Re-read server state for every batch this run owned, updating jobs in place.

    A batch item comes back identified by file name alone, so this can only work
    because the planning layer guarantees one name per job within a run.
    """
    updated = 0
    by_name = {job.name: job for job in record.jobs}
    for batch_id in record.batch_ids:
        try:
            items = client.poll_batch(batch_id)
        except ApiError as exc:
            log.warn(f"batch {batch_id}: {exc.describe()}")
            continue
        for item in items:
            job = by_name.get(item.file_name)
            if job is None:
                # a rescue: the local record never heard of this file (e.g. --batch)
                job = Job(job_id=new_job_id(),
                          source=Source(value=item.file_name, kind="file", name=item.file_name),
                          name=item.file_name)
                record.jobs.append(job)
                by_name[item.file_name] = job
            job.state = item.state
            job.zip_url = item.zip_url
            if item.err_msg:
                job.err_msg = item.err_msg
            if item.state == "done" and item.zip_url:
                updated += 1
    return updated
