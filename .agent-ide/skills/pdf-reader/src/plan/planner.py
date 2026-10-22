"""Turn sources into jobs: the only place that knows about page windows.

Three rules carry the whole design:

* **Splitting cuts in memory, and only ever at a limit.**  A source that is over the
  mode's page limit *or* over its file-size limit becomes several jobs carrying a
  ``page_range``, and each of those windows is cut out of the source in memory when it
  is uploaded, so a job sends the pages it stands for rather than the whole file plus a
  range.  Nothing is written to disk: the archived tool wrote ``chunk_0000.pdf`` files
  into a cwd-relative temp dir and then reassembled page numbers by hand.
* **Splitting happens only at the limit, never for speed.**  Measured end-to-end
  latency is dominated by a fixed server-side cost of ~3-4s (a 3-page upload takes
  5.8s), so cutting a file into 5-page pieces multiplies requests without saving
  time.  The archived tool's 5-page chunks cost 4x the necessary requests.
* **A selection the caller named is still admitted.**  ``--pages`` decides *how much*
  of a source to read, never *whether* it may be read: a source over the file limit
  whose pages cannot be measured is refused the same way with or without it.

A fourth rule is about identity rather than scheduling.  The name sent to the endpoint
is the only key a batch item ever comes back with, so two jobs in one run may never
share one; duplicate basenames are disambiguated here, once, and any window the
execution layer adds later goes through the same helper.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..config.resolve import ConfigError
from ..endpoint.models import Job, Source
from ..mode import Caps
from ..util import log
from ..util.ids import new_job_id
from . import probe


#: Guard against a pathological page selection; with windows at the mode's page
#: limit this covers 10k pages, far beyond anything the endpoint accepts.
MAX_WINDOWS = 50


@dataclass
class Plan:
    jobs: list[Job] = field(default_factory=list)
    rejected: list[tuple[Source, str]] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# page selections
# --------------------------------------------------------------------------- #

def parse_selection(spec: str) -> list[tuple[int, int]]:
    """Read a page selection into ``(start, end)`` spans.

    A selection may name single pages and spans, comma-separated (``2,4-6``); only
    the precision channel understands a list, flash takes a single span.  Both the
    syntax check and the arithmetic live here, so a page count can never be computed
    from text that was never parsed -- two independent parsers is how a documented
    selection ended up crashing the quota pre-check.
    """
    spans: list[tuple[int, int]] = []
    for chunk in str(spec).split(","):
        chunk = chunk.strip()
        if not chunk:
            raise ConfigError(f"{spec!r}: empty part in the page selection")
        head, dash, tail = chunk.partition("-")
        if dash:
            if not (head.strip().isdigit() and tail.strip().isdigit()):
                raise ConfigError(f"{spec!r}: expected a page span like '4-6'")
            start, end = int(head), int(tail)
            if end < start:
                raise ConfigError(f"{spec!r}: {start}-{end} runs backwards")
        else:
            if not chunk.isdigit():
                raise ConfigError(f"{spec!r}: expected a page number or a span")
            start = end = int(chunk)
        if start < 1:
            raise ConfigError(f"{spec!r}: page numbers start at 1")
        spans.append((start, end))
    if not spans:
        raise ConfigError(f"{spec!r}: no pages selected")
    return spans


def pages_selected(spec: str) -> int:
    """How many pages a selection names."""
    return sum(end - start + 1 for start, end in parse_selection(spec))


# --------------------------------------------------------------------------- #
# names
# --------------------------------------------------------------------------- #

def _suffixed(name: str, suffix: str) -> str:
    stem, dot, extension = name.rpartition(".")
    return f"{stem}{suffix}{dot}{extension}" if dot else f"{name}{suffix}"


def unique_name(name: str, taken: set[str]) -> str:
    """Claim ``name``, or the first free ``name_2`` / ``name_3`` ... variant."""
    if name not in taken:
        taken.add(name)
        return name
    index = 1
    while True:
        index += 1
        candidate = _suffixed(name, f"_{index}")
        if candidate not in taken:
            taken.add(candidate)
            return candidate


def window_name(source: Source, start: int, end: int) -> str:
    return _suffixed(source.name, f"_p{start}-{end}")


# --------------------------------------------------------------------------- #
# windows
# --------------------------------------------------------------------------- #

def windows(limit: int, total: int) -> list[tuple[int, int]]:
    """Fixed-size page windows covering ``total`` pages."""
    return windows_by_pages(limit, 1, total)


def windows_by_pages(limit: int, first: int, last: int) -> list[tuple[int, int]]:
    """Fixed-size page windows over ``first``..``last``, one ceiling only."""
    out: list[tuple[int, int]] = []
    start = first
    while start <= last and len(out) < MAX_WINDOWS:
        end = min(start + limit - 1, last)
        out.append((start, end))
        start = end + 1
    return out


def windows_by_bytes(page_limit: int, byte_limit: int, page_bytes: list[int],
                     first: int = 1, last: int | None = None) -> list[tuple[int, int]]:
    """Greedy page windows: as many pages as fit under *both* ceilings.

    The two ceilings are independent -- flash refuses at 20 pages **or** 10MB, precision
    at 200 pages **or** 200MB -- so a window is closed by whichever it reaches first and
    is never cut short for the other.  ``page_bytes`` holds the size of page 1, 2, ...
    (see ``probe.page_sizes``), which is why the sum over a window over-estimates it:
    the estimate errs towards a smaller window, the safe direction.

    A page that is over the byte ceiling **on its own** is left out instead of being
    sent as a window of one: measured, the endpoint refuses on the bytes it is handed, so
    such a page could only come back refused -- a request spent for nothing.  The pages
    around it still travel, which is the difference between losing one page and losing
    the document.
    """
    total = len(page_bytes) if last is None else min(last, len(page_bytes))
    out: list[tuple[int, int]] = []
    start = first
    while start <= total and len(out) < MAX_WINDOWS:
        if page_bytes[start - 1] > byte_limit:
            start += 1
            continue
        end = start - 1
        used = 0
        while end + 1 <= total and (end + 1 - start) < page_limit:
            size = page_bytes[end]
            if used + size > byte_limit:
                break
            used += size
            end += 1
        out.append((start, end))
        start = end + 1
    return out


def window_map(spec: str, total: int) -> list[int]:
    """The mapping table of a window: which original pages it carries, in order.

    Page 1 of the equivalent PDF is ``window_map(...)[0]`` of the original, page 2 is its
    second entry, and so on: ``8-14`` maps to ``[8, 9, ..., 14]``, and a selection that
    jumps maps the same way (``2,4-6`` -> ``[2, 4, 5, 6]``).  Pages past the end of the
    document are dropped, so a window that starts beyond it maps to nothing at all -- and
    an empty mapping is exactly a window that does not qualify for submission.  That is
    how the end of a file is recognised locally, instead of by provoking a refusal to
    discover it.
    """
    return [page for start, end in parse_selection(spec)
            for page in range(start, min(end, total) + 1)]


def window_pages(source: Source, spec: str) -> list[int] | None:
    """The mapping table of a window of ``source``, measuring the source if need be.

    ``None`` means the document cannot be measured at all, so no window of it can be cut
    and the caller must say that rather than send something else.  An empty list is a
    different answer: the pages are measurable and simply do not exist.
    """
    total = source.pages
    if total is None:
        sizes = _sizes(source)
        total = None if sizes is None else len(sizes)
    if total is None:
        return None
    return window_map(spec, total)


def window_at(limit: int, start: int) -> tuple[int, int]:
    """The window that begins at ``start``.

    Used for sources whose page count is unknown (a URL, or no PyMuPDF): the endpoint
    is asked for one window at a time and its answer is the measurement, so the
    planning layer only has to say where the next window begins.
    """
    return start, start + limit - 1


# --------------------------------------------------------------------------- #
# the plan
# --------------------------------------------------------------------------- #

def plan(sources: list[str], caps: Caps, pages: str | None = None) -> Plan:
    """Admission-check every input, then cut it into windows no larger than the caps."""
    result = Plan()
    taken: set[str] = set()
    byte_limit = caps.max_file_mb * 1024 * 1024
    for value in sources:
        try:
            source = probe.probe(value)
        except FileNotFoundError as exc:
            # like the size refusal below: recorded here, printed once by the caller
            result.rejected.append((Source(value=value, kind="file", name=value), str(exc)))
            continue

        if (source.pages is None and source.size_mb is not None
                and source.size_mb > caps.max_file_mb):
            reason = (f"{source.name} is {source.size_mb:.1f} MB, above the "
                      f"{caps.mode.value} limit of {caps.max_file_mb} MB, and its pages "
                      f"cannot be measured, so it cannot be cut either")
            # reported by the caller, which owns the user-facing line: printing it here
            # as well is how one refusal showed up as two errors
            result.rejected.append((source, reason))
            continue

        if pages is not None:
            _emit(result, source, _cut(source, caps, byte_limit, parse_selection(pages)), taken)
            continue

        if source.pages is None:
            if not source.is_url:
                log.warn(f"{source.name}: page count unknown; submitting blind and "
                         f"letting a page-limit error drive the split")
            result.jobs.append(_job(source, unique_name(source.name, taken), None))
            continue

        sizes = _sizes(source)
        over_pages = source.pages > caps.page_limit
        over_bytes = sizes is not None and sum(sizes) > byte_limit
        if not over_pages and not over_bytes:
            result.jobs.append(_job(source, unique_name(source.name, taken), None))
            continue

        log.info(f"{source.name}: {source.pages} pages"
                 + (f" / {sum(sizes) / (1024 * 1024):.1f} MB" if sizes else "")
                 + f" exceeds the {caps.mode.value} limits; cutting it into windows "
                   f"(each window uploads its own pages)")
        _emit(result, source, _cut(source, caps, byte_limit, [(1, source.pages)]), taken)
    return result


def _sizes(source: Source) -> list[int] | None:
    """Per-page serialized sizes, measured once and kept on the source."""
    if source.page_bytes is None:
        source.page_bytes = probe.page_sizes(Path(source.value))
    return source.page_bytes


def _cut(source: Source, caps: Caps, byte_limit: int,
         spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Cut each requested span down to the caps.

    The greedy cut needs per-page sizes; without them the page ceiling is still
    enforceable, which is what keeps a file whose size cannot be profiled splittable.
    """
    sizes = _sizes(source)
    out: list[tuple[int, int]] = []
    for start, end in spans:
        if sizes is None:
            out.extend(windows_by_pages(caps.page_limit, start, end))
        else:
            out.extend(windows_by_bytes(caps.page_limit, byte_limit, sizes, start, end))
    _warn_left_out(source, spans, out, byte_limit)
    return out


def _warn_left_out(source: Source, spans: list[tuple[int, int]],
                   windows: list[tuple[int, int]], byte_limit: int) -> None:
    """Say which requested pages no window carries, and why.

    Silence here would be the worst failure mode in the skill: pages would go missing
    from a delivered document with nothing on stderr to explain it.
    """
    wanted = {page for start, end in spans for page in range(start, end + 1)}
    covered = {page for start, end in windows for page in range(start, end + 1)}
    missing = sorted(wanted - covered)
    if not missing:
        return
    shown = ", ".join(str(page) for page in missing[:8]) + (" ..." if len(missing) > 8 else "")
    log.warn(f"{source.name}: {len(missing)} page(s) left out -- each is bigger than the "
             f"whole {byte_limit // (1024 * 1024)}MB allowance on its own: {shown}")


def _emit(result: Plan, source: Source, spans: list[tuple[int, int]], taken: set[str]) -> None:
    """One job per window; its name carries the range it stands for."""
    for start, end in spans:
        result.jobs.append(_job(source,
                                unique_name(window_name(source, start, end), taken),
                                f"{start}-{end}"))


def _job(source: Source, name: str, page_range: str | None) -> Job:
    return Job(job_id=new_job_id(), source=source, name=name, page_range=page_range)
