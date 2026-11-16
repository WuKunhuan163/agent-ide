"""Move between an IDE's transcript store and this project.

Two directions, both read-only:

    probe     a file holding a fragment of some agent's reply -> the
              conversation keys whose messages contain it
    render    a conversation key -> that conversation as markdown, filtered
              by --last N, --since, --until

The probe direction never prints transcript text: the fragment is matched
inside each message file, and only keys and counts come back.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import json
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import sys as _sys


class Sys:
    maxsize = 2**63 - 1
import re
import sys
import shutil
import unicodedata
import time

from .ide import registry
from .ide.base import Message, iso, parse_ts

CONFIG = Path(__file__).resolve().parent.parent / "data" / "config.json"


# ---------------------------------------------------------------- discovery


# Probe prior: the target is a *fresh* session, so a conversation far larger than
# this project's own cannot be it. Count entries only — counting 185k files costs
# 0.24 s, `stat`-ing them costs 7 s. A literal, never recomputed at runtime.
# Measured on this machine: a needle for a fresh session, so anything with more
# files than this cannot be the source. Counted with os.scandir, never stat.
PROBE_MAX_CONVERSATION_FILES = 2000
# 覆盖：AGENT_IDE_PROBE_MAX_FILES=0 表示不设上限（长会话必须能探）
PROBE_MAX_FILES_ENV = "AGENT_IDE_PROBE_MAX_FILES"

def transcripts_config() -> dict:
    """The `transcripts` block of agent-ide's own config: ide, history_root, bindings."""
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8")).get("transcripts", {}) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def bindings() -> dict[str, str]:
    """Agent id -> conversation key, as migrated from the user channel."""
    return dict(transcripts_config().get("bindings", {}))


def key_for(agent_id: str) -> str:
    """Resolve a bound agent id to its conversation key."""
    table = bindings()
    if agent_id in table:
        return table[agent_id]
    # `--id` takes the *agent id*, the left column of `--bindings`. Passing the
    # conversation key here is the one mistake everybody makes, so name it instead of
    # echoing "not bound": the message is the only place the user learns the pair.
    if agent_id in set(table.values()):
        raise LookupError(
            f"'{agent_id}' is a conversation key, not an agent id; use --key {agent_id}, "
            f"or --id <one of: {', '.join(sorted(table))}>"
        )
    known = ", ".join(sorted(table)) or "none"
    raise LookupError(
        f"no conversation bound to '{agent_id}'; --id takes the agent id (left column of "
        f"--bindings), bound ids: {known}"
    )


def store_for(ide: str | None = None, root: str | None = None):
    """A SessionStore for `ide`, with its history root resolved.

    Precedence: `--root`, then agent-ide's own `transcripts.history_root`,
    then the adapter's discovery.
    """
    cfg = transcripts_config()
    ide = ide or cfg.get("ide")
    root = root or cfg.get("history_root")

    if root:
        ide = ide or registry.DEFAULT_IDE
        return registry.create(ide, Path(root).expanduser())

    if ide:
        found = dict(registry.detect(ide))
        if ide not in found:
            raise LookupError(f"{ide}: history root not found; pass --root")
        return registry.create(ide, found[ide])

    found = registry.detect()
    if not found:
        raise LookupError("no IDE transcript store found; pass --ide / --root")
    name, path = found[0]
    return registry.create(name, path)


def conversation_dirs(store) -> list[Path]:
    return store.conversations()


# -------------------------------------------------------------------- probe


class ProbeHit(NamedTuple):
    """One matching conversation: how often it matched, and how big it is.

    The two size numbers are not decoration. A key alone says "this is the
    session"; it does not say whether the session is 12 messages or 4000, and
    that changes how the answer should be read -- a two-message match is a
    fragment quoted somewhere, a 4000-message match is the session itself. The
    third number matters for the other reason: anything above the cap is
    *unprobeable*, so a key sitting at 1900/2000 files is one edit away from
    disappearing from every future probe.
    """

    key: str
    hits: int
    msgs: int
    bytes: int
    files: int
    last: float = 0.0




# ------------------------------------------------------------------ scan worker
# 模块级函数：ProcessPoolExecutor 只能 pickle 顶层函数，所以扫描逻辑不放在闭包里。
_W = {}


def _worker_init(raw_needles, cjk_runs, needles):
    _W["raw"] = raw_needles
    _W["cjk"] = cjk_runs
    _W["n"] = needles


def _scan_one(payload):
    name, raw_path = payload
    path = Path(raw_path)
    try:
        blob = path.read_bytes()
    except OSError:
        return None
    if any(n in blob for n in _W["raw"]):
        return name
    if _W["cjk"] and b"\\u" not in blob:
        if not any(r in _DELETABLE.sub(b"", blob) for r in _W["cjk"]):
            return None
    try:
        body = _normalise("\n".join(_strings(json.loads(blob))))
    except Exception:
        body = _normalise(blob.decode("utf-8", "replace"))
    return name if any(n in body for n in _W["n"]) else None


def probe_keys(store, fragment_file: Path, limit: int | None = None,
               max_files: int | None = None, processes: int | None = None) -> list[ProbeHit]:
    """Keys whose message files contain any non-empty line of the fragment file.

    Three levels, cheapest first, and all of them exact in what they claim:

    1. **Count gate, no stat.** A needle names a *fresh* session, so a conversation
       with more than `PROBE_MAX_CONVERSATION_FILES` message files cannot be it. The
       count comes from `os.scandir`, never from sizes: one `stat` per conversation
       cost 7 s on a 185k-file store, counting cost 0.24 s.
    2. **Byte-equal needle.** A fragment copied out of a reply is byte-identical to
       what was stored, so one C substring test per file answers the common case.
    3. **Sound prefilter, then the lenient pass.** The lenient pass (JSON unescape,
       full-width folding, emphasis stripped) costs ~1 ms per file, and it only ever
       *deletes or maps* characters. So a CJK run from the needle — which carries no
       folding — must be present in the file once the deletable bytes are removed;
       if it is not, no normalisation can produce the needle there.

    Comparison is on decoded, normalised text for level 3 because a fragment copied
    out of a UI differs from the stored bytes in exactly those ways. Levels 1-2 are
    filters, not answers: they can only pass a file through to level 3.

    Progress goes to stderr so stdout stays a clean key<TAB>hits table.
    """
    needles = [ln.strip() for ln in fragment_file.read_text(
        encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    if not needles:
        raise ValueError(
            f"{fragment_file}: 针是空的（0 行非空文本）。把被找的那句话原文写进这个文件，"
            f"例如：printf '%s' '<一句原文>' > {fragment_file}；"
            f"不要 cat 它，也不要往里写多条候选。")
    needles_raw = list(needles)
    needles = [_normalise(n) for n in needles]
    if not any(needles):
        raise ValueError(
            f"{fragment_file}: 针里只有不可见字符（U+FFFD／零宽／空格），归一化后为空 — the fragment "
            f"holds only characters that carry no text (U+FFFD, zero-width, spaces). "
            f"Copy a longer stretch of the reply, or pick a line with words in it.")

    convs = conversation_dirs(store)
    files_of = {c.name: store.message_files(c) for c in convs}
    count = {k: len(v) for k, v in files_of.items()}

    cap = max_files
    if cap is None:
        cap = int(os.environ.get(PROBE_MAX_FILES_ENV, PROBE_MAX_CONVERSATION_FILES))
    keep = [c for c in convs if cap <= 0 or count[c.name] <= cap]
    dropped = len(convs) - len(keep)
    files = [(c, p) for c in keep for p in files_of[c.name]]
    print(f"probe: {len(keep)}/{len(convs)} conversations kept"
          f" (> {cap if cap > 0 else Sys.maxsize} files dropped: {dropped}),"
          f" {len(files)} files", file=sys.stderr, flush=True)

    queue = list(files)
    raw_needles = [ln.encode("utf-8") for ln in needles_raw if ln]
    # A CJK run is the safe prefilter: the lenient pass never folds a CJK
    # character into another, so if the run is absent from the file with the
    # deletable bytes removed, no normalisation can produce the needle.
    cjk_runs = [r.encode("utf-8") for r in (_core_run(n) for n in needles_raw)
                if len(r) >= 3 and all("\u4e00" <= ch <= "\u9fff" for ch in r)]
    t0 = time.monotonic()

    hits = {}
    done = 0
    # 进度只报里程碑：首条 + 1/2/5/10/20/50/100%。大库全扫 20 万文件时，
    # 每 500 条刷一次会把终端冲掉，读数反而看不见。
    marks = [0.01, 0.02, 0.05, 0.10, 0.20, 0.50, 1.00]
    steps = [max(1, int(len(queue) * m)) for m in marks]
    step_i = 0
    jobs = [(conv.name, str(path)) for conv, path in queue]
    workers = processes or max(2, (os.cpu_count() or 4))
    use_procs = len(jobs) > 20000 and workers > 1
    if use_procs:
        pool_ctx = ProcessPoolExecutor(
            max_workers=workers,
            initializer=_worker_init,
            initargs=(raw_needles, cjk_runs, needles),
        )
    else:
        _worker_init(raw_needles, cjk_runs, needles)
        pool_ctx = ThreadPoolExecutor(max_workers=min(32, workers * 4))

    with pool_ctx as pool:
        mapper = pool.map(_scan_one, jobs, chunksize=64) if use_procs else pool.map(_scan_one, jobs, chunksize=64)
        for name in mapper:
            done += 1
            if name:
                hits[name] = hits.get(name, 0) + 1
            label = None
            if done == 1:
                label = f"{1/len(queue):.0%}" if len(queue) > 100 else "0%"
            elif step_i < len(steps) and done >= steps[step_i]:
                label = f"{marks[step_i]:.0%}"
                step_i += 1
            if label:
                print(f"probe: {label:>4} ({done}/{len(queue)}) "
                      f"{time.monotonic()-t0:5.1f}s  hits={len(hits)}",
                      file=sys.stderr, flush=True)
    print(file=sys.stderr)

    sized = {
        name: ProbeHit(
            key=name,
            hits=n,
            msgs=count[name],
            bytes=sum(f.stat().st_size for f in files_of[name] if f.is_file()),
            files=count[name],
            last=max((p.stat().st_mtime for p in files_of[name] if p.is_file()), default=0.0),
        )
        for name, n in hits.items()
    }
    out = sorted(sized.values(), key=lambda h: (h.hits, h.last, h.msgs), reverse=True)
    return out[:limit] if limit else out





def _deletable():
    """The bytes the lenient pass removes: whitespace, storage quoting, emphasis marks."""
    return re.compile(rb"[\s`\\*_]")


_DELETABLE = _deletable()


def _core_run(needle: str) -> str:
    """The longest run of letters/CJK in a needle: punctuation and whitespace are
    what the lenient pass deletes, so a run of these survives it."""
    best, cur = "", ""
    for ch in needle:
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
            cur += ch
        else:
            if len(cur) > len(best):
                best = cur
            cur = ""
    return best if len(best) > len(cur) else cur


# ------------------------------------------------------------------- render


def _load(store, conv: Path, since: str | None, until: str | None,
          tail: int | None = None) -> list[Message]:
    """Read the messages a render can actually use, and nothing else.

    `tail` is passed straight through: with `--last N` there is no reason to
    parse a 110k-file conversation to keep the final two messages.
    """
    since_dt = parse_ts(since)
    until_dt = parse_ts(until)
    return store.read_messages(conv, since=since_dt, until=until_dt, tail=tail)


def render_conversation(store, conv: Path, *, last: int | None = None,
                        since: str | None = None, until: str | None = None,
                        with_tools: bool = True, stamps: bool = False) -> str:
    msgs = _load(store, conv, since, until, tail=last)
    if last:
        msgs = msgs[-last:]

    rounds = _rounds(msgs)
    out: list[str] = [f"# {conv.name}  {len(msgs)} msgs  {len(rounds)} rounds"]
    out.append(f"# tz: all stamps are UTC (`...Z`)   local offset {_local_offset()}; "
               f"'# rN' spans are the first->last message of the round")
    if since or until:
        out.append(f"# window {since or '-'} .. {until or '-'}")

    for i, rnd in enumerate(rounds, 1):
        first, lastmsg = rnd[0], rnd[-1]
        span = f"{iso(first.at)}->{iso(lastmsg.at)}"
        out.append("")
        out.append(f"# r{i} {span}")
        for msg in rnd:
            out.extend(_emit(msg, with_tools, stamps=stamps))
    return "\n".join(out)





def _call_summary(call) -> str:
    args = call.args or {}
    for key in ("command", "filePath", "file_path", "path", "pattern", "query"):
        if args.get(key):
            extra = args.get("explanation") or args.get("description") or ""
            head = f"{key}={str(args[key])}"
            return head + (f"  （{extra}）" if extra else "")
    return str(args)







def _result_flag(res) -> str:
    return "error" if res.is_error else (res.status or "ok")


def _result_body(res) -> str:
    raw = res.text or ""
    try:
        import json as _json
        doc = _json.loads(raw)
    except Exception:
        return raw
    if isinstance(doc, dict):
        if "stdout" in doc or "stderr" in doc:
            code = doc.get("exitCode")
            parts = [f"exit={code}"]
            if doc.get("stdout"):
                parts.append(str(doc["stdout"]).rstrip())
            if doc.get("stderr"):
                parts.append("[stderr] " + str(doc["stderr"]).rstrip())
            return "\n".join(parts)
        if "content" in doc:
            return f"{doc.get('path', '')}\n{doc.get('content', '')}"
        if "path" in doc:
            return str(doc.get("path"))
    return raw



def _rounds(msgs: list[Message]) -> list[list[Message]]:
    """One round = a user message plus everything until the next user message."""
    rounds: list[list[Message]] = []
    for msg in msgs:
        if msg.role == "user" or not rounds:
            rounds.append([msg])
        else:
            rounds[-1].append(msg)
    return rounds


def _local_offset() -> str:
    """The machine's UTC offset, so a reader can convert without guessing."""
    off = datetime.now().astimezone().utcoffset()
    if off is None:
        return "UTC+0"
    minutes = int(off.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    return f"UTC{sign}{abs(minutes) // 60}" + (f":{abs(minutes) % 60:02d}" if minutes % 60 else "")


def _stamp(msg: Message) -> str:
    at = iso(msg.at)
    return at[11:19] + "Z" if at != "?" else "?"


def _emit(msg: Message, with_tools: bool, stamps: bool = False) -> list[str]:
    """Bash-style lines for one message: $ user, > assistant, * call, = result, ~ thought."""
    role = msg.role
    lead = "$" if role == "user" else ">" if role == "assistant" else " "
    lines: list[str] = []
    # Thinking first: that is the order it was produced in. Reading a record by
    # line number, a `~` block sitting after the prose looks like the message has
    # ended, and a reader then reports "the reply was never written" while the
    # `>` body sits further up the file.
    if msg.reasoning.strip():
        body = msg.reasoning.rstrip().splitlines() or [""]
        lines.append(f"~ {body[0]}")
        lines.extend(f"  {ln}" for ln in body[1:])
    if msg.text.strip():
        body = msg.text.rstrip().splitlines() or [""]
        prefix = f"@{_stamp(msg)} " if stamps else ""
        lines.append(f"{prefix}{lead} {body[0]}")
        lines.extend(f"  {ln}" for ln in body[1:])
    if with_tools:
        for call in msg.calls:
            lines.append(f"* {call.name} {_call_summary(call)}")
        for res in msg.results:
            body = _result_body(res).rstrip().splitlines() or [""]
            flag = _result_flag(res)
            lines.append(f"= {res.name} {flag}: {body[0]}")
            lines.extend(f"  {ln}" for ln in body[1:])
    return lines


def resolve_key(store, key: str) -> Path:
    for conv in conversation_dirs(store):
        if conv.name == key:
            return conv
    raise LookupError(f"no conversation with key {key} under {store.root}")

def _build_table() -> dict[int, str | None]:
    """One translate table for every difference copying can introduce.

    Full-width forms map to ASCII (the FF01-FF5E band is NFKC's main win for us),
    CJK punctuation maps to its ASCII counterpart, and whitespace (including the
    ideographic space) maps to nothing. Doing this in a table keeps the pass in C:
    `unicodedata.normalize` over a store this size costs more than the JSON parse.
    """
    table: dict[int, str | None] = {}
    for cp in range(0xFF01, 0xFF5F):
        table[cp] = chr(cp - 0xFEE0)
    table.update({
        0x201C: '"', 0x201D: '"', 0x2018: "'", 0x2019: "'",
        0x3001: ",", 0x3002: ".", 0x300C: '"', 0x300D: '"',
        0x300A: '"', 0x300B: '"', 0x3008: "(", 0x3009: ")",
        0x2014: "-", 0x2013: "-", 0xB7: ".",
    })
    for cp in (0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0xA0, 0x3000):
        table[cp] = None
    # Transport noise: characters that carry no meaning and exist only because the
    # text was copied, re-encoded or truncated mid-sequence. U+FFFD is what a lost
    # byte becomes — keeping it makes every needle containing it unmatchable, and
    # deleting it is what the reader would do anyway.
    for cp in (0xFFFD, 0x00AD, 0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0xFE0F, 0xFEFE):
        table[cp] = None
    for cp in range(0x2000, 0x200B):  # en/em/thin spaces → nothing, same as ASCII space
        table[cp] = None
    return table


_PUNCT = _build_table()


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
_BOLD_UNDER = re.compile(r"(?<![A-Za-z0-9_])__(?=\S)(.+?)(?<=\S)__(?![A-Za-z0-9_])")
_ITALIC_STAR = re.compile(r"(?<![A-Za-z0-9_*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![A-Za-z0-9_*])")
_ITALIC_UNDER = re.compile(r"(?<![A-Za-z0-9_])_(?=\S)([^_\n]+?)(?<=\S)_(?![A-Za-z0-9_])")
_IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")


def _unwrap(match: re.Match[str]) -> str:
    """Keep a dunder name, unwrap anything else.

    `__init__` surrounded by spaces *is* markdown bold by the letter of the
    syntax, and would render as "init" — but in a sentence about code it is a
    name, and a fragment that says `__init__` must not be searched for as
    `init`. Double-underscore wrapping a plain ASCII identifier is therefore
    read as a name; anything else (CJK, punctuation, spaces) is emphasis.
    """
    inner = match.group(1)
    if match.group(0).startswith("__") and _IDENT.match(inner):
        return match.group(0)
    return inner


def _strip_emphasis(text: str) -> str:
    """Remove markdown emphasis marks, and only those.

    `**bold**`, `*italic*`, `__bold__`, `_italic_` render without their marks, so a
    sentence copied from the rendered reply carries none of them. But `_` is also an
    ordinary character: `ai_task`, `probe_keys`, `x_y_z` must survive. The
    difference is syntax, not the character: a mark counts only when it sits at an
    ASCII word boundary and wraps non-space text. Boundaries are ASCII on purpose —
    in Python's `\\w`, CJK characters are word characters, so emphasis markers touching them would not match
    the closing test and never be stripped.
    """
    # A pass whose marker character is absent cannot match. Most messages carry
    # neither `*` nor `_`, and four regex passes over 13 KB of prose cost more
    # than the JSON parse; the guard is what keeps the whole probe in seconds.
    if "*" in text:
        text = _BOLD.sub(_unwrap, text)
        text = _ITALIC_STAR.sub(_unwrap, text)
    if "_" in text:
        text = _BOLD_UNDER.sub(_unwrap, text)
        text = _ITALIC_UNDER.sub(_unwrap, text)
    return text
def _normalise(text: str) -> str:
    """Defeat the ways a copied sentence differs from the stored bytes.

    Five kinds of difference, all artefacts of the medium rather than of the
    sentence: JSON escaping, the storage's own quoting (backticks), markdown
    emphasis (stripped by syntax, see `_strip_emphasis`), the full-width forms a
    Chinese input method produces, and whitespace.

    What is left is the characters themselves, in order. Nothing that carries
    meaning is removed — `_` inside an identifier is meaning, `_italic_` is not.
    """
    text = text.replace("\\", "").replace("`", "")
    return _strip_emphasis(text).translate(_PUNCT)
