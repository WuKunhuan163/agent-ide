"""Archived rounds: read them back, or move them between agent ids.

A round is two files with the same timestamp prefix:

    data/contact_msg/<id>/<ts>_contact_msg.txt
    data/user_response/<id>/<ts>_user_response.txt
"""
from __future__ import annotations
import shutil
from datetime import datetime
from pathlib import Path

from .exit_codes import Exit
from .paths import CONTACT, RESPONSE, archived, data, input_text, project_root
from .utils import trash


# ---------------------------------------------------------------------- recent


def print_recent(agent_id: str, count: int) -> None:
    count = max(1, int(count))
    rounds = _rounds(agent_id)
    selected = rounds[-count:]

    print(f"agent_id={agent_id} rounds={len(rounds)} selected={len(selected)}")

    if not rounds:
        cli = project_root() / ".agent-tools" / "contact-user"
        print("new project: no archived rounds")
        print(f"write {input_text(agent_id, 'contact')}")
        print(f"write {input_text(agent_id, 'commit')}")
        print(f"run   {cli} --id {agent_id}")
        return

    for ts, contact_text, reply in selected:
        print(f"\n## {ts} agent\n")
        print(_plain(contact_text))
        if reply.strip():
            print(f"\n## {ts} user\n")
            print(reply)

    directive = next((reply.strip() for _, _, reply in reversed(rounds) if reply.strip()), "")
    if directive:
        print("\n# latest directive\n")
        print(_plain(directive))


def _rounds(agent_id: str) -> list[tuple[str, str, str]]:
    folder = data(CONTACT, agent_id)
    if not folder.is_dir():
        return []
    out = []
    for path in sorted(folder.glob(f"*_{CONTACT}.txt")):
        ts = path.name[: -len(f"_{CONTACT}.txt")]
        out.append((ts, _read(path), _read(archived(agent_id, RESPONSE, ts))))
    return out


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _plain(text: str) -> str:
    """Keep archived headings from turning into structure of this output."""
    return "\n".join(
        "\\" + line if line.startswith("#") or line.strip() == "---" else line
        for line in text.splitlines()
    )


# ------------------------------------------------------------------ maintenance


def merge(target: str, sources: list[str], start_time: str | None = None,
          end_time: str | None = None) -> int:
    if not target:
        return Exit.Merge.MISSING_TARGET
    if not sources:
        return Exit.Merge.MISSING_SOURCES
    for source in sources:
        for kind in (RESPONSE, CONTACT):
            _move(source, target, kind, start_time, end_time)
    print(f"moved {', '.join(sources)} -> {target}")
    return Exit.OK


def _move(source: str, target: str, kind: str, start: str | None, end: str | None) -> None:
    folder = data(kind, source)
    if not folder.is_dir():
        return
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        ts = path.name.split("_")[0]
        if (start and ts < start) or (end and ts > end):
            continue
        destination = _free_name(data(kind, target, create=True) / path.name)
        try:
            shutil.copy2(path, destination)
        except OSError:
            continue
        trash(path)
    try:
        if not any(folder.iterdir()):
            folder.rmdir()
    except OSError:
        pass


def _free_name(path: Path) -> Path:
    if not path.exists():
        return path
    index = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def delete(agent_id: str) -> int:
    if not agent_id:
        return Exit.Runtime.MISSING_ID
    for kind in (RESPONSE, CONTACT, "autosave"):
        folder = data(kind, agent_id)
        if folder.is_dir():
            trash(folder)
    print(f"moved {agent_id} to the trash")
    return Exit.OK
