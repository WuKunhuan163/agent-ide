"""Export archived rounds to a markdown journal, and prune them on request.

Two separate commands on purpose: `export` only reads the archive and writes a
file, `prune` is the one that moves rounds to the Trash. Deleting is never a side
effect of exporting — the archive is the sole record a compressed session leaves
behind, and a typo in a filename should not cost rounds.

`--tail` keeps the newest rounds in place in both: they are what the next agent
needs to start cold.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .paths import CONTACT, RESPONSE, data, resolve_arg, stamp

TS_FMT = "%Y%m%d_%H%M%S"
TAIL_DEFAULT = 5


class JournalError(Exception):
    pass


def export(
    agent_id: str,
    out_path: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    tail: int = TAIL_DEFAULT,
    title: str | None = None,
    summary_path: str | None = None,
) -> dict:
    """Write the journal. The archive is not touched."""
    selected, kept = _select(agent_id, since, until, tail)
    if not selected:
        raise JournalError("no archived rounds left to export")

    summary = _read_summary(summary_path)
    title = title or "Journal"
    out = resolve_arg(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [f"# {title} (Agent: {agent_id})", ""]
    lines.append(
        f"<!-- contact-user-archive id={agent_id} from={selected[0]['ts']} "
        f"until={selected[-1]['ts']} rounds={len(selected)} -->"
    )
    lines += ["", "## Summary", "", summary, "", "---", "", "## Raw Context", ""]

    for index, item in enumerate(selected, start=1):
        lines.append(f"### Agent Prompt {index} ({_human(item['at'])})")
        lines.append(_escape(_read(item["contact"])))
        lines.append("")
        lines.append(f"### User Response {index} ({_human(item['at'])})")
        lines.append(_escape(_read(item["response"])))
        lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return {
        "exported": str(out),
        "rounds": len(selected),
        "from": selected[0]["ts"],
        "until": selected[-1]["ts"],
        "kept": len(kept),
    }


def prune(
    agent_id: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    tail: int = TAIL_DEFAULT,
) -> dict:
    """Move the rounds in the window to the Trash, and nothing else."""
    selected, kept = _select(agent_id, since, until, tail)
    if not selected:
        raise JournalError("no archived rounds left to prune")
    trash, moved = _move_to_trash(agent_id, selected)
    return {
        "pruned": len(selected),
        "from": selected[0]["ts"],
        "until": selected[-1]["ts"],
        "kept": len(kept),
        "moved": moved,
        "trash": str(trash),
    }


# ------------------------------------------------------------------- internals


def _select(
    agent_id: str, since: datetime | None, until: datetime | None, tail: int
) -> tuple[list[dict], list[dict]]:
    everything = _rounds(agent_id)
    kept: list[dict] = []
    if tail > 0:
        kept = everything[-tail:]
        everything = everything[:-tail] if len(everything) > tail else []
    return [r for r in everything if _in_range(r["at"], since, until)], kept


def _move_to_trash(agent_id: str, rounds: list[dict]) -> tuple[Path, int]:
    target = _trash_dir(agent_id)
    for kind in (CONTACT, RESPONSE):
        (target / kind).mkdir(parents=True, exist_ok=True)
    moved = 0
    for item in rounds:
        for kind, key in ((CONTACT, "contact"), (RESPONSE, "response")):
            source = item[key]
            if source.exists():
                shutil.move(str(source), str(target / kind / source.name))
                moved += 1
    return target, moved


def _rounds(agent_id: str) -> list[dict]:
    folder = data(CONTACT, agent_id)
    if not folder.is_dir():
        return []
    rounds = []
    for contact in sorted(folder.glob(f"*_{CONTACT}.txt")):
        ts = contact.name[: -len(f"_{CONTACT}.txt")]
        try:
            at = datetime.strptime(ts, TS_FMT).astimezone()
        except ValueError:
            continue
        response = data(RESPONSE, agent_id, f"{ts}_{RESPONSE}.txt")
        rounds.append({"ts": ts, "at": at, "contact": contact, "response": response})
    return rounds


def _in_range(at: datetime, since: datetime | None, until: datetime | None) -> bool:
    moment = at.astimezone(timezone.utc)
    if since is not None and moment < since:
        return False
    if until is not None and moment > until:
        return False
    return True


def _human(at: datetime) -> str:
    return at.strftime("%Y-%m-%d %H:%M:%S")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return "(missing)"


def _escape(text: str) -> str:
    """A quoted `# heading` in the raw text must not become document structure."""
    lines = []
    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            hashes = len(stripped) - len(stripped.lstrip("#"))
            rest = stripped[hashes:]
            if rest[:1] in (" ", "\t") or not rest:
                indent = line[: len(line) - len(stripped)]
                line = indent + "\\" + stripped
        lines.append(line)
    return "\n".join(lines)


def _read_summary(path: str | None) -> str:
    if not path:
        return "*No summary written.*"
    try:
        text = resolve_arg(path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise JournalError(f"cannot read summary {path}: {exc}")
    return text or "*No summary written.*"


def _trash_dir(agent_id: str) -> Path:
    trash = Path.home() / ".Trash"
    base = trash if trash.is_dir() else data("trash", create=True)
    return base / f"{agent_id}_contact_archive_{stamp()}"


def dump(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)
