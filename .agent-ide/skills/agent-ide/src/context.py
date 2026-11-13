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

import json
import os
from concurrent.futures import ThreadPoolExecutor
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
PROBE_MAX_CONVERSATION_FILES = 1000

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


def probe_keys(store, fragment_file: Path, limit: int | None = None) -> list[tuple[str, int]]:
    """Keys whose message files contain any non-empty line of the fragment file.

    A probe looks for a *fresh* session: the fragment names one sentence that
    session produced, and that session began empty. Anything far larger than the
    conversation bound to this project cannot be it, so it is skipped unread —
    the bound conversation's own size sets the scale (5% by default). That cut is
    what makes a probe over a 1 GB store take seconds instead of minutes.

    Comparison is on *decoded, normalised* text — JSON unescaping, NFKC, full-width
    to half-width, backticks and whitespace removed — because a fragment copied out
    of a UI differs from the stored bytes in exactly those ways and nowhere else.
    Normalising is not an option: a strict byte compare answers "not present" to
    sentences that are present, which is worse than being slow.

    Progress goes to stderr so stdout stays a clean key<TAB>hits table.
    """
    needles = [ln.strip() for ln in fragment_file.read_text(
        encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    if not needles:
        raise ValueError(f"{fragment_file}: no non-empty line to match")
    needles = [_normalise(n) for n in needles]

    convs = conversation_dirs(store)
    files_of = {c.name: store.message_files(c) for c in convs}
    count = {k: len(v) for k, v in files_of.items()}

    keep = [c for c in convs if count[c.name] <= PROBE_MAX_CONVERSATION_FILES]
    dropped = len(convs) - len(keep)
    files = [(c, p) for c in keep for p in files_of[c.name]]
    print(f"probe: {len(keep)}/{len(convs)} conversations kept"
          f" (> {PROBE_MAX_CONVERSATION_FILES} files dropped: {dropped}),"
          f" {len(files)} files", file=sys.stderr, flush=True)

    hits: dict[str, int] = {}
    t0 = time.monotonic()
    queue = list(files)
    done = 0

    def scan(item):
        conv, path = item
        try:
            blob = path.read_bytes()
        except OSError:
            return None
        try:
            body = _normalise("\n".join(_strings(json.loads(blob))))
        except Exception:
            body = _normalise(blob.decode("utf-8", "replace"))
        return conv.name if any(n in body for n in needles) else None

    # Reading is I/O bound and the containment test runs in C, so threads (not
    # processes) buy the parallelism without pickling 10k paths.
    with ThreadPoolExecutor(max_workers=min(16, (os.cpu_count() or 4) * 2)) as pool:
        for name in pool.map(scan, queue, chunksize=32):
            done += 1
            if name:
                hits[name] = hits.get(name, 0) + 1
            if done % 500 == 0 or done == len(queue):
                print(f"\rprobe: {done}/{len(queue)} files  {done/len(queue):5.0%}  "
                      f"{time.monotonic()-t0:5.1f}s  hits={len(hits)}",
                      end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)

    out = sorted(hits.items(), key=lambda kv: kv[1], reverse=True)
    return out[:limit] if limit else out


# ------------------------------------------------------------------- render


def _load(store, conv: Path, since: str | None, until: str | None) -> list[Message]:
    since_dt = parse_ts(since)
    until_dt = parse_ts(until)
    msgs = store.read_messages(conv, since=since_dt)
    if until_dt:
        msgs = [m for m in msgs if m.at is None or m.at <= until_dt]
    return msgs


def render_conversation(store, conv: Path, *, last: int | None = None,
                        since: str | None = None, until: str | None = None,
                        with_tools: bool = True, stamps: bool = False) -> str:
    msgs = _load(store, conv, since, until)
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
    text = _BOLD.sub(_unwrap, text)
    text = _BOLD_UNDER.sub(_unwrap, text)
    text = _ITALIC_STAR.sub(_unwrap, text)
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
