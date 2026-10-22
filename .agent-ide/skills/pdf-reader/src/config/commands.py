"""``config`` verb: the generic way to read or change any parameter.

One form, no per-parameter flags: ``config set <KEY> <VALUE>``.  The key must exist in
the schema, the value is coerced to the declared type, upper bounds pinned to the
endpoint's own ceilings are enforced, and cross-parameter constraints are checked
before anything is written.

Output is one line per action on stderr, like every other verb; nothing is written to
stdout except a product that was explicitly asked for.  ``config list --markdown`` is
that case -- the markdown parameter table *is* the requested product, so it is what gets
printed to stdout and what is then written to ``docs/config.md``.
"""
from __future__ import annotations

import argparse

from ..util import log
from ..util.exit_codes import OK, USAGE
from . import store
from .resolve import ConfigError, coerce, env_name, resolve
from .schema import PARAMS, PARAMS_BY_KEY, keys_in_scope


def rows(cfg) -> list[dict]:
    """Every parameter as a record: value, where it came from, and how to set it."""
    out: list[dict] = []
    for param in PARAMS:
        value = cfg.get(param.key)
        out.append({
            "key": param.key,
            "value": value,
            "default": param.default,
            "bounds": list(param.bounds) if param.bounds else None,
            "origin": cfg.origin(param.key),
            "overridden": cfg.is_overridden(param.key),
            "env": env_name(param.key),
            "effect": param.effect,
            "source": param.source,
        })
    return out


def shown(value) -> str:
    """How a value reads in one line of text."""
    if value is None:
        return "null"
    if isinstance(value, list):
        return "[" + ", ".join(str(item) for item in value) + "]"
    return str(value)


def _narrate(cfg, verbose: bool) -> None:
    last_scope = None
    for row in rows(cfg):
        scope, _, leaf = row["key"].partition(".")
        if scope != last_scope:
            log.info(f"[{scope}]")
            last_scope = scope
        mark = "*" if row["overridden"] else " "
        tail = f"  ({row['origin']})" if row["overridden"] else ""
        log.info(f" {mark} {leaf:<28} {shown(row['value']):<16}{tail}")
        if verbose:
            bounds = f"  bounds={row['bounds']}" if row["bounds"] else ""
            log.info(f"      {row['effect']}{bounds}")
            log.info(f"      source: {row['source']}")
    log.debug("'*' marks a value that is overridden; `config unset <KEY>` reverts it")


def _markdown() -> str:
    lines = [
        "# pdf-reader parameters",
        "",
        "Generated from `src/config/schema.py` -- do not edit by hand. Regenerate with",
        "`pdf-reader config list --markdown`.",
        "",
        "A value comes from the first of these that names it: `--set KEY=VALUE` on a",
        "`read`/`fetch` call (this invocation only), the environment variable in the",
        "**env** column, `data/config.json` (written by `config set`), then the default.",
        "Upper bounds are pinned to the endpoint's own ceilings, so a parameter cannot be",
        "raised into a value the service would refuse anyway.",
        "",
        "Where a number comes from is marked in the **source** column: `[D1]` the official",
        "API documentation, `[D2]` the ecosystem repository, `[D3]` the official client's",
        "own defaults, `[T]` measured against the live endpoint, `[C]` carried over from",
        "the archived tool, `[?]` no published value exists.",
        "",
    ]
    for scope in ("common", "precision", "flash"):
        lines += [f"## {scope}", "",
                  "| key | default | bounds | env | what it does | source |",
                  "|---|---|---|---|---|---|"]
        for key in keys_in_scope(scope):
            param = PARAMS_BY_KEY[key]
            bounds = f"{param.bounds[0]}..{param.bounds[1]}" if param.bounds else "-"
            lines.append(f"| `{key}` | `{shown(param.default)}` | {bounds} | "
                         f"`{env_name(key)}` | {param.effect} | {param.source} |")
        lines.append("")
    return "\n".join(lines)


def run(args: argparse.Namespace, cli_sets: dict[str, str]) -> int:
    action = args.config_action
    try:
        cfg = resolve(cli_sets=cli_sets)
    except ConfigError as exc:
        log.error(str(exc))
        return USAGE

    if action == "list":
        if getattr(args, "markdown", False):
            log.emit_stdout(_markdown())
        else:
            _narrate(cfg, verbose=getattr(args, "verbose", False))
        return OK

    if action == "get":
        if args.key not in PARAMS_BY_KEY:
            log.error(f"unknown parameter {args.key!r}")
            return USAGE
        default = PARAMS_BY_KEY[args.key].default
        value = shown(cfg.get(args.key))
        origin = cfg.origin(args.key)
        # the value *is* the answer, so it is a human line like every other one; the
        # default is only worth naming when it is not what is in force
        log.info(f"{args.key} = {value} ({origin})"
                 + ("" if cfg.get(args.key) == default else f", default {shown(default)}"))
        return OK

    if action == "set":
        if args.key not in PARAMS_BY_KEY:
            log.error(f"unknown parameter {args.key!r}")
            return USAGE
        param = PARAMS_BY_KEY[args.key]
        try:
            value = coerce(param, args.value)
        except ConfigError as exc:
            log.error(str(exc))
            return USAGE
        # validate the whole set with the candidate applied, so cross-parameter
        # constraints cannot be slipped past one key at a time
        candidate = cfg.as_dict()
        candidate[args.key] = value
        overrides = store.load_overrides()
        overrides[args.key] = args.value
        try:
            probe = resolve(cli_sets={k: str(v) for k, v in candidate.items()},
                            overrides=overrides)
        except ConfigError as exc:
            log.error(str(exc))
            return USAGE
        store.set_override(args.key, args.value)
        log.info(f"{args.key} = {shown(probe.get(args.key))} (config.json)")
        return OK

    if action == "unset":
        if args.key not in PARAMS_BY_KEY:
            log.error(f"unknown parameter {args.key!r}")
            return USAGE
        reverted = store.unset_override(args.key)
        if reverted:
            log.info(f"{args.key} reverted to {shown(PARAMS_BY_KEY[args.key].default)}")
        else:
            log.info(f"{args.key} was already at its default")
        return OK

    if action == "reset":
        store.reset_overrides()
        log.info("all overrides cleared; every parameter is back at its default")
        return OK

    log.error(f"unknown config action {action!r}")
    return USAGE
