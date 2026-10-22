"""The parameter definition area: single source of truth for every tunable.

Four rules, all of them load-bearing:

1. **Keys are namespaced** -- ``common.*`` / ``precision.*`` / ``flash.*``.
   Anything whose value differs between the two endpoint modes must live in that
   mode's namespace, never in ``common``.  That is what removes the
   "same name, two meanings" ambiguity (``SPLIT_PAGE_LIMIT`` was both 200 and 20).
2. **Upper bounds are pinned to the documented endpoint ceilings.**  A user cannot
   raise ``precision.split_page_limit`` past 200: the server would reject the file
   anyway, so allowing it would only manufacture a failure.
3. **Every value carries its source.**  ``source`` quotes the official document
   (``[D1]`` = mineru.net API docs) or marks a measured value (``[T]``).
4. **``docs/config.md`` is generated from this table** -- see
   ``pdf-reader config list --markdown``.  It is never hand-edited; that is how the
   old tool's documentation drifted away from its code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


# --------------------------------------------------------------------------- #
# declaration
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Param:
    """One declared parameter.

    ``type`` is one of ``int`` / ``float`` / ``str`` / ``ints`` / ``int_or_null``.
    ``bounds`` is inclusive and optional; for documented ceilings the upper bound
    *is* the ceiling.  ``readers`` lists the modules that consume the value, which
    is how necessity was audited: a parameter with no reader does not belong here.
    """

    key: str
    type: str
    default: Any
    bounds: tuple | None = None
    source: str = ""
    effect: str = ""
    readers: tuple[str, ...] = field(default_factory=tuple)

    @property
    def scope(self) -> str:
        return self.key.split(".", 1)[0]

    @property
    def leaf(self) -> str:
        return self.key.split(".", 1)[1]


def _p(*args, **kwargs) -> Param:
    return Param(*args, **kwargs)


PARAMS: tuple[Param, ...] = (
    # ---------------------------------------------------------------- common --
    _p("common.request_timeout_s", "int", 60, (5, 300),
       source="[?] no official value; measured 0.16s (link request) / 0.75s (state probe)",
       effect="per-HTTP-request timeout for link requests and state probes",
       readers=("endpoint.client",)),
    _p("common.upload_timeout_s", "int", 300, (30, 1800),
       source="[D3] SDK upload read-timeout is 300s",
       effect="timeout for one PUT upload; on expiry the job is retried",
       readers=("run.submit",)),
    _p("common.poll_init_s", "int", 2, (1, 30),
       source="[T] local uploads reach done in 6-16s, so a 2s first probe is fine",
       effect="first polling interval",
       readers=("run.poll",)),
    _p("common.poll_max_s", "int", 30, (5, 300),
       source="[T] worst observed completion is ~38s (URL input)",
       effect="top of the polling backoff",
       readers=("run.poll",)),
    _p("common.poll_total_timeout_s", "int", 1800, (60, 7200),
       source="[D3] SDK batch-level timeout is 1800s",
       effect="total wall-clock budget for one run before it is declared stalled",
       readers=("run.poll", "run.scheduler")),
    _p("common.retry_max", "int", 3, (0, 10),
       source="[C] carried over from the archived tool (--retries 3)",
       effect="retry budget per job",
       readers=("run.scheduler",)),
    _p("common.concurrency_initial", "int", 4, (1, 64),
       source="[T] 6 concurrent flash jobs succeeded with zero 429; 4 is the conservative start",
       effect="in-flight job budget at the beginning of a run",
       readers=("run.scheduler",)),
    _p("common.concurrency_max", "int", 6, (1, 64),
       source="[?] no published ceiling; [T] 6 verified. Raise only after calibration",
       effect="ceiling for the adaptive in-flight budget",
       readers=("run.scheduler",)),
    _p("common.concurrency_down_factor", "float", 0.5, (0.1, 0.9),
       source="[?] policy value, not documented",
       effect="multiplier applied to the budget when -60009 or 429 is observed",
       readers=("run.scheduler",)),
    _p("common.concurrency_up_step", "int", 1, (1, 4),
       source="[?] policy value, not documented",
       effect="increment applied to the budget after a clean streak",
       readers=("run.scheduler",)),
    _p("common.concurrency_probe_after", "int", 3, (1, 10),
       source="[?] policy value, not documented",
       effect="consecutive successes required before probing the budget upwards",
       readers=("run.scheduler",)),
    _p("common.backoff_steps", "ints", [2, 4, 8, 16, 30], None,
       source="[?] fixed sequence replacing the old POLL_FACTOR/RETRY_DELAY pair",
       effect="sleeps used by the retry/poll backoff",
       readers=("run.poll", "run.scheduler")),
    _p("common.quota_reset_tz", "str", "Asia/Shanghai", None,
       source="[C] the archived key pool reset on the Beijing calendar day",
       effect="timezone whose midnight resets the local ledger (the endpoint never says "
              "when its own day rolls over)",
       readers=("plan.quota",)),

    # ------------------------------------------------------------- precision --
    _p("precision.split_page_limit", "int", 200, (1, 200),
       source="[D1] 'file pages must not exceed 200'; also the -60006 trigger",
       effect="a source larger than this is split by page range, never physically",
       readers=("plan.planner", "mode")),
    _p("precision.max_file_mb", "int", 200, (1, 200),
       source="[D1] 'single file size must not exceed 200MB' (-60005)",
       effect="admission check; an oversized file is refused before submission",
       readers=("plan.planner", "mode")),
    _p("precision.link_batch_size", "int", 50, (1, 50),
       source="[D1] 'a single request may not ask for more than 50 links'",
       effect="how many files one link request carries (the real batch ceiling)",
       readers=("run.submit", "mode")),
    _p("precision.daily_page_quota", "int", 1000, (1, 100000),
       source="[D1] 'each account gets 1000 pages/day at top priority'; beyond that priority drops",
       effect="basis of the local page ledger; exceeding it warns, it does not refuse",
       readers=("plan.quota",)),

    # ----------------------------------------------------------------- flash --
    _p("flash.split_page_limit", "int", 20, (1, 20),
       source="[D1] flash page limit is 20 (-30003)",
       effect="a source larger than this is split by page range before submission",
       readers=("plan.planner", "mode")),
    _p("flash.max_file_mb", "int", 10, (1, 10),
       source="[D1] flash size limit is 10MB (-30001)",
       effect="admission check",
       readers=("plan.planner", "mode")),
    _p("flash.daily_file_quota", "int_or_null", None, (1, 100000),
       source="[?] user reports 5000 files/day on the web UI; absent from every public doc",
       effect="optional local file ledger for flash; null disables the ledger",
       readers=("plan.quota",)),
)


PARAMS_BY_KEY: dict[str, Param] = {p.key: p for p in PARAMS}


# --------------------------------------------------------------------------- #
# cross-parameter constraints
# --------------------------------------------------------------------------- #

#: (left, operator, right) -- validated whenever a value is set.
CONSTRAINTS: tuple[tuple[str, str, str], ...] = (
    ("common.concurrency_initial", "<=", "common.concurrency_max"),
    ("common.poll_init_s", "<=", "common.poll_max_s"),
)


def scope_of(key: str) -> str:
    return key.split(".", 1)[0]


def keys_in_scope(scope: str) -> list[str]:
    return [p.key for p in PARAMS if p.scope == scope]


def all_keys() -> list[str]:
    return [p.key for p in PARAMS]


def suggest(key: str) -> Iterable[str]:
    """Close matches for a typo'd key, so a mistake costs one glance not one search."""
    import difflib

    matched = difflib.get_close_matches(key, all_keys(), n=4, cutoff=0.6)
    if matched:
        return matched
    leaf = key.split(".")[-1]
    return [k for k in all_keys() if leaf and leaf in k]
