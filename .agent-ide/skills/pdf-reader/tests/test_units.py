"""Assertions that protect the rules, not the implementation.

Run with ``python3 tests/test_units.py`` -- standard library only, no pytest, no
network, no credential.  What is checked here is exactly the set of behaviours whose
breakage produced a real defect before: a page selection that crashed the quota
pre-check, an admission check skipped for an explicitly selected read, two names that
collide, an error envelope that escaped as a transport exception, an exit code that
could not be told apart from another, and a parameter table that could not be
regenerated.

Nothing here talks to the endpoint: the network contracts are covered by
``docs/protocol-notes.md`` and by running a real ``read``.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import mode as mode_pkg                                    # noqa: E402
from src.config import schema                                       # noqa: E402
from src.config.resolve import ConfigError, env_name, resolve        # noqa: E402
from src.deliver import emit                                        # noqa: E402
from src.endpoint import errors                                      # noqa: E402
from src.endpoint.models import Job, RunRecord, Source               # noqa: E402
from src.plan import planner                                         # noqa: E402
from src.run.scheduler import job_lines                              # noqa: E402
from src.util import exit_codes                                      # noqa: E402


PASSED = 0
FAILED: list[str] = []


def check(condition: bool, what: str) -> None:
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILED.append(what)


def check_eq(got, want, what: str) -> None:
    check(got == want, f"{what}: got {got!r}, want {want!r}")


def check_raises(exc, fn, what: str) -> None:
    try:
        fn()
    except exc:
        global PASSED
        PASSED += 1
        return
    except Exception as other:                                      # noqa: BLE001
        check(False, f"{what}: raised {type(other).__name__} instead of {exc.__name__}")
        return
    check(False, f"{what}: nothing raised")


def caps_for(name: str):
    return mode_pkg.caps_for(mode_pkg.Mode(name), resolve(overrides={}))


# --------------------------------------------------------------------------- #
# page selections -- the selection that crashed the pre-check
# --------------------------------------------------------------------------- #

def test_page_selections() -> None:
    check_eq(planner.pages_selected("1-200"), 200, "a full span counts its pages")
    check_eq(planner.pages_selected("5"), 1, "a single page counts one")
    check_eq(planner.pages_selected("2,4-6"), 4, "a comma list counts every page it names")
    check_eq(planner.pages_selected(" 1 - 3 , 9 "), 4, "spaces around parts are ignored")
    check_eq(planner.parse_selection("2,4-6"), [(2, 2), (4, 6)], "a list parses into spans")
    for bad in ("", "a-b", "2-1", "0-5", "2,", "2--2", "1-2-3"):
        check_raises(ConfigError, lambda spec=bad: planner.parse_selection(spec),
                     f"{bad!r} is refused")


def test_selection_survives_the_ledger() -> None:
    from src.plan import quota
    job = Job(job_id="x", source=Source(value="a.pdf", kind="file", name="a.pdf", pages=9),
              name="a.pdf", page_range="2,4-6")
    check_eq(quota.estimate([job]), 4, "the ledger counts a comma selection")
    totals = quota.commit([_done(job)], caps_for("precision"), "UTC")
    check(totals["pages"] >= 4, "the ledger records it without crashing")


def test_flash_takes_one_span_only() -> None:
    caps = caps_for("flash")
    spans = planner.parse_selection("2,4-6")
    check(caps.single_file_only and len(spans) > 1,
          "a comma list is more than flash can express in one request")
    check_eq(len(planner.parse_selection("1-20")), 1, "one span is fine for flash")


# --------------------------------------------------------------------------- #
# names -- a batch item comes back by name alone
# --------------------------------------------------------------------------- #

def test_names_are_unique() -> None:
    taken: set[str] = set()
    check_eq(planner.unique_name("paper.pdf", taken), "paper.pdf", "the first name stands")
    check_eq(planner.unique_name("paper.pdf", taken), "paper_2.pdf", "a clash is suffixed")
    check_eq(planner.unique_name("paper.pdf", taken), "paper_3.pdf", "and again")
    check_eq(planner.unique_name("noext", taken), "noext", "a name without a dot is kept")
    check_eq(planner.unique_name("noext", taken), "noext_2", "and suffixed without a dot")
    check_eq(len(taken), 5, "every returned name is claimed")


# --------------------------------------------------------------------------- #
# planning -- admission applies with or without an explicit selection
# --------------------------------------------------------------------------- #

def _with_fake_probe(sources: dict[str, Source], fn):
    original = planner.probe.probe
    planner.probe.probe = lambda value: sources[value]
    try:
        return fn()
    finally:
        planner.probe.probe = original


def test_admission_and_windows() -> None:
    big = Source(value="big.pdf", kind="file", name="big.pdf", pages=None, size_mb=300.0)
    caps = caps_for("precision")
    planned = _with_fake_probe({"big.pdf": big}, lambda: planner.plan(["big.pdf"], caps))
    check_eq(len(planned.jobs), 0, "an oversized file is refused")
    check_eq(len(planned.rejected), 1, "and it is reported as rejected")

    planned = _with_fake_probe({"big.pdf": big},
                               lambda: planner.plan(["big.pdf"], caps, pages="1-200"))
    check_eq(len(planned.jobs), 0, "a selected read does not smuggle it past admission")

    long_pdf = Source(value="long.pdf", kind="file", name="long.pdf", pages=450, size_mb=8.0)
    planned = _with_fake_probe({"long.pdf": long_pdf}, lambda: planner.plan(["long.pdf"], caps))
    check_eq([job.page_range for job in planned.jobs], ["1-200", "201-400", "401-450"],
             "450 pages split into three windows at the limit")

    blind = Source(value="https://x/y.pdf", kind="url", name="y.pdf")
    planned = _with_fake_probe({"https://x/y.pdf": blind},
                               lambda: planner.plan(["https://x/y.pdf"], caps))
    check_eq([job.page_range for job in planned.jobs], [None],
             "a URL is submitted whole: the page count is not knowable locally")

    same = [Source(value=f"{d}/paper.pdf", kind="file", name="paper.pdf", pages=1, size_mb=1.0)
            for d in ("a", "b")]
    planned = _with_fake_probe({"a/paper.pdf": same[0], "b/paper.pdf": same[1]},
                               lambda: planner.plan(["a/paper.pdf", "b/paper.pdf"], caps))
    check_eq([job.name for job in planned.jobs], ["paper.pdf", "paper_2.pdf"],
             "two sources with the same basename get distinct names")


def test_window_names_and_ladder() -> None:
    source = Source(value="p.pdf", kind="file", name="p.pdf", pages=300, size_mb=5.0)
    check_eq(planner.window_name(source, 1, 200), "p_p1-200.pdf", "a window is named by range")
    check_eq(planner.window_at(200, 401), (401, 600), "the ladder's next window starts where asked")
    check_eq(len(planner.windows(200, 10000)), planner.MAX_WINDOWS,
             "windows are bounded even for an absurd page count")


# --------------------------------------------------------------------------- #
# configuration -- one definition area, four sources, bounds that match the service
# --------------------------------------------------------------------------- #

def test_config_precedence_and_bounds() -> None:
    key = "precision.split_page_limit"
    check_eq(resolve(overrides={}).get(key), 200, "the default comes from the schema")
    check_eq(resolve(overrides={key: 150}).get(key), 150, "a stored override wins over it")
    check_eq(resolve(overrides={key: 150}, env={env_name(key): "100"}).get(key), 100,
             "the environment wins over the file")
    cfg = resolve(overrides={key: 150}, env={env_name(key): "100"}, cli_sets={key: "120"})
    check_eq(cfg.get(key), 120, "--set wins over everything")
    check_eq(cfg.origin(key), "--set", "and it says so")
    check_eq(env_name(key), "PDF_READER_PRECISION_SPLIT_PAGE_LIMIT", "env names are derived")

    check_raises(ConfigError, lambda: resolve(cli_sets={key: "300"}),
                 "a value above the endpoint ceiling is refused")
    check_raises(ConfigError, lambda: resolve(cli_sets={"precision.nope": "1"}),
                 "an unknown key is refused")
    check_raises(ConfigError, lambda: resolve(cli_sets={key: "many"}),
                 "an unparsable value is refused")
    check_raises(ConfigError,
                 lambda: resolve(cli_sets={"common.concurrency_initial": "9"}),
                 "a cross-parameter constraint is enforced")
    check_raises(ConfigError,
                 lambda: resolve(cli_sets={"common.backoff_steps": "[8, 2]"}),
                 "a sequence must be non-decreasing")


def test_schema_invariants() -> None:
    for param in schema.PARAMS:
        check(bool(param.source), f"{param.key} cites a source")
        check(bool(param.effect), f"{param.key} says what it does")
        check(bool(param.readers), f"{param.key} names a reader")
    keys = [param.key for param in schema.PARAMS]
    check_eq(len(keys), len(set(keys)), "no parameter is declared twice")
    check("common.quota_reset_tz" in keys, "the ledger's timezone is channel-independent")
    for left, op, right in schema.CONSTRAINTS:
        check(left in keys and right in keys, f"constraint {left} {op} {right} names real keys")
    for weak, strong in (("common.concurrency_initial", "common.concurrency_max"),
                         ("common.poll_init_s", "common.poll_max_s")):
        check(resolve(overrides={}).get(weak) <= resolve(overrides={}).get(strong),
              f"{weak} starts at or below {strong}")


# --------------------------------------------------------------------------- #
# modes -- a token selects a channel, it does not tune one
# --------------------------------------------------------------------------- #

def test_mode_caps() -> None:
    check(mode_pkg.decide_mode(False, True) is mode_pkg.Mode.PRECISION,
          "a token selects precision")
    check(mode_pkg.decide_mode(False, False) is mode_pkg.Mode.FLASH,
          "no token selects flash instead of failing")
    check(mode_pkg.decide_mode(True, True) is mode_pkg.Mode.FLASH, "--flash overrides the token")

    precision, flash = caps_for("precision"), caps_for("flash")
    check_eq((precision.page_limit, flash.page_limit), (200, 20), "page limits differ per channel")
    check_eq((precision.max_file_mb, flash.max_file_mb), (200, 10), "size limits differ too")
    check(precision.has_zip and precision.has_blocks and precision.has_images,
          "only precision delivers a zip with blocks and figures")
    check(not (flash.has_zip or flash.has_blocks or flash.has_images),
          "flash delivers markdown and nothing else")
    check_eq((precision.link_batch_size, flash.link_batch_size), (50, 1),
             "batching is a precision-only capability")
    check(precision.needs_token and not flash.needs_token, "the token requirement differs")
    check_eq((precision.daily_quota_unit, flash.daily_quota_unit), ("pages", "files"),
             "the ledgers count different things")
    check_eq(flash.daily_quota_value, None, "flash's ledger stays off until a number is known")


# --------------------------------------------------------------------------- #
# errors -- both envelopes, and a failure reported as text
# --------------------------------------------------------------------------- #

def test_error_envelopes() -> None:
    body = b'{"code": -60005, "msg": "file too large"}'
    err = None
    try:
        errors.parse(200, body)
    except errors.ApiError as exc:
        err = exc
    check(err is not None and err.action is errors.Action.INPUT_REJECT,
          "a business failure is classified from its code")
    check(err is not None and err.code == "-60005", "and it keeps the code")

    auth = b'{"traceId": "t", "msgCode": "A0211", "msg": "token invalid", "success": false}'
    err = None
    try:
        errors.parse(401, auth)
    except errors.ApiError as exc:
        err = exc
    check(err is not None and err.action is errors.Action.BAD_TOKEN,
          "the authentication envelope is parsed rather than escaping as a transport error")
    check(err is not None and err.http_status == 401, "and it keeps the status")

    check_eq(errors.parse(200, b'{"code": 0, "data": {"batch_id": "b"}}'), {"batch_id": "b"},
             "a success returns the data payload")
    check_raises(errors.ApiError, lambda: errors.parse(200, b'{"code": -60018, "msg": "x"}'),
                 "a quota refusal is raised, not returned")
    check_raises(errors.ApiError, lambda: errors.parse(503, b""),
                 "a 5xx without a body is still an error")


def test_flash_limits_are_separated() -> None:
    check(errors.classify("-30003") is errors.Action.SPLIT_REQUIRED,
          "flash's page limit is splittable: fewer pages would work")
    check(errors.classify("-30001") is errors.Action.FLASH_LIMIT,
          "flash's size limit is not splittable, so it must not enter the window ladder")
    check(errors.ApiError(errors.Action.FLASH_LIMIT, "", "").should_split,
          "a channel-level refusal still tells the caller a split is an option")


def test_error_from_text() -> None:
    check(errors.action_from_message("pages exceed the limit of 200") is errors.Action.SPLIT_REQUIRED,
          "a page-limit failure is recognised from wording, so the ladder can start")
    check(errors.action_from_message("错误码: -60006") is errors.Action.SPLIT_REQUIRED,
          "an embedded code is recovered")
    check(errors.action_from_message("任务提交队列已满 请稍后再试") is errors.Action.RETRY_BACKOFF,
          "a full queue is retryable")
    check(errors.action_from_message("每日解析任务数量已达上限") is errors.Action.QUOTA_STOP,
          "a daily quota refusal halts the run")
    check(errors.action_from_message("文件页数已达上限") is errors.Action.SPLIT_REQUIRED,
          "a page-limit message that also says '已达上限' is still a split, not a quota stop")
    check(errors.action_from_message("URL 无法访问") is errors.Action.URL_UNREADABLE,
          "an unreadable URL is separated from a quota problem")
    check(errors.action_from_message("") is errors.Action.UNKNOWN, "silence is unknown")


# --------------------------------------------------------------------------- #
# state, ordering and exit codes
# --------------------------------------------------------------------------- #

def _done(job: Job) -> Job:
    job.state = "done"
    return job


def test_record_round_trip() -> None:
    job = Job(job_id="abc12345", source=Source(value="a.pdf", kind="file", name="a.pdf", pages=3),
              name="a.pdf")
    record = RunRecord(run_id="20260101_000000_abcdef", mode="precision", created_at=1.0,
                       input_dir="", output_dir="/tmp/x", jobs=[_done(job)])
    reloaded = RunRecord.from_dict(record.to_dict())
    check_eq(reloaded.jobs[0].name, "a.pdf", "a record survives a round trip")
    check_eq(reloaded.jobs[0].state, "done", "including job state")

    legacy = record.to_dict()
    legacy["jobs"][0]["err_code"] = "-60006"          # a field a previous version wrote
    legacy["something_new"] = 1                       # and a key this version never had
    check_eq(RunRecord.from_dict(legacy).jobs[0].name, "a.pdf",
             "an older record still loads instead of raising TypeError")


def test_delivery_is_idempotent() -> None:
    job = _done(Job(job_id="j", source=Source(value="a.pdf", kind="file", name="a.pdf", pages=1),
                    name="a.pdf"))
    check(not emit.already_materialized(job), "a finished job is not yet materialized")
    job.materialized_at = 1.0
    check(not emit.already_materialized(job), "a timestamp without outputs is not enough")
    job.outputs = ["full.md"]
    check(emit.already_materialized(job), "products on disk make it materialized")


def test_exit_codes_are_distinct() -> None:
    values = {exit_codes.OK, exit_codes.FAILED, exit_codes.PARTIAL, exit_codes.USAGE}
    check_eq(len(values), 4, "no two outcomes share a code")
    check_eq(exit_codes.USAGE, 64, "a usage error stays out of the 0/1/2 outcome family")
    check(exit_codes.PARTIAL != exit_codes.USAGE,
          "partial success can be told apart from a bad command")


def test_job_lines_report_the_truth() -> None:
    job = _done(Job(job_id="j", source=Source(value="a.pdf", kind="file", name="a.pdf", pages=9),
                    name="a.pdf", page_range="1-5"))
    job.block_count, job.image_count = 12, 3
    record = RunRecord(run_id="r", mode="precision", created_at=1.0, input_dir="", output_dir="",
                       jobs=[job])
    line = job_lines(record)[0]
    check(line.startswith("ok"), f"a finished job is marked ok: {line!r}")
    check("pages 1-5" in line, "a window reports its range rather than the file's page count")


def test_ladder_walks_one_window_at_a_time() -> None:
    """A blind source is split by asking for windows one at a time.

    The window's *mapping table* is what decides where the file ends: pages that do not
    exist map to nothing, so the ladder stops before sending a window that could not
    succeed -- and the window that does travel is an ordinary PDF of exactly the pages it
    names.  The endpoint is faked, which is what the client protocol exists for.
    """
    import contextlib
    import io
    import re
    import tempfile
    from pathlib import Path

    import pymupdf

    from src.endpoint.models import ItemState, LinkBatch
    from src.run.scheduler import Scheduler

    class FakePrecision:
        def __init__(self, total: int) -> None:
            self.total = total
            self.batches: dict[str, list[str]] = {}
            self.submitted: list[str] = []
            self.uploads: list[tuple[str, int]] = []
            self._n = 0

        def request_links(self, body):
            self._n += 1
            names = [entry["name"] for entry in body["files"]]
            self.batches[f"b{self._n}"] = names
            self.submitted.extend(names)
            return LinkBatch(batch_id=f"b{self._n}",
                             file_urls=[f"https://oss/b{self._n}/{name}" for name in names])

        def upload(self, url, path):
            return 1

        def upload_bytes(self, url, data):
            with pymupdf.open(stream=data, filetype="pdf") as window:
                self.uploads.append((url.rsplit("/", 1)[-1], window.page_count))
            return len(data)

        def poll_batch(self, batch_id):
            return [self._answer(name) for name in self.batches.get(batch_id, [])]

        def _answer(self, name: str) -> ItemState:
            window = re.search(r"_p(\d+)-(\d+)", name)
            if window is None or int(window.group(1)) > self.total:
                return ItemState(file_name=name, state="failed",
                                 err_msg="file page count exceeds API limit (200 pages), "
                                         "please input page_ranges")
            return ItemState(file_name=name, state="done", zip_url=f"https://cdn/{name}.zip")

    source = Path(tempfile.mkdtemp()) / "p.pdf"
    with pymupdf.open() as doc:
        for _ in range(250):
            doc.new_page()
        doc.save(str(source))

    fake = FakePrecision(total=250)
    cfg = resolve(cli_sets={"common.backoff_steps": "[0]"})
    job = Job(job_id="blind", source=Source(value=str(source), kind="file", name="p.pdf"),
              name="p.pdf")
    record = RunRecord(run_id="r", mode="precision", created_at=1.0, input_dir="",
                       output_dir=tempfile.mkdtemp())
    scheduler = Scheduler(fake, cfg, caps_for("precision"), record,
                          options={"formula": True, "table": True})
    with contextlib.redirect_stdout(io.StringIO()):
        code = scheduler.run([job])

    check_eq(code, exit_codes.OK, "a ladder that delivered everything reports success")
    check_eq([entry.name for entry in record.jobs], ["p_p1-200.pdf", "p_p201-400.pdf"],
             "only the windows are deliverables; the blind parent and the probe are not")
    check_eq(fake.submitted, ["p.pdf", "p_p1-200.pdf", "p_p201-400.pdf"],
             "windows are asked for one at a time, and the window that would start past the "
             "end of the file is never submitted: its mapping table is empty")
    check_eq(fake.uploads, [("p_p1-200.pdf", 200), ("p_p201-400.pdf", 50)],
             "each window travels as a PDF of exactly the pages it maps to: the 200 asked "
             "for, then the 50 that are left")


def main() -> int:
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        try:
            test()
        except Exception:                                            # noqa: BLE001
            FAILED.append(f"{test.__name__} raised:\n{traceback.format_exc()}")
    print(f"{PASSED} assertions passed, {len(FAILED)} failed ({len(tests)} tests)")
    for failure in FAILED:
        print(f"  FAIL {failure}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
