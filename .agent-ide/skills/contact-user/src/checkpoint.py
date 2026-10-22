"""The per-round git checkpoint of the project root.

The message comes from `commit_msg_<id>.txt`, is flattened to one line, is
prefixed exactly once with `@skill:contact-user `, and its body is clamped, so
round commits stay greppable and uniform.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

from .exit_codes import Exit
from .paths import project_root

PREFIX = "@skill:contact-user "
BODY_MAX = 200
NOTHING_TO_COMMIT = ("nothing to commit", "nothing added to commit",
                     "no changes added to commit", "working tree clean")


def commit(raw_message: str) -> None:
    message = _message(raw_message)
    if not message:
        return

    root = project_root()
    if not (root / ".git").is_dir():
        _run(["git", "init"], root, "git init")
    if (root / ".git" / "MERGE_HEAD").is_file() or (root / ".git" / "rebase-merge").is_dir():
        _die("a git merge or rebase is in progress; resolve it first", root)
    _run(["git", "add", "."], root, "git add")
    if _run(["git", "diff", "--cached", "--quiet"], root, "", allow_fail=True).returncode == 0:
        return
    done = _run(["git", "commit", "-m", message], root, "git commit", allow_fail=True)
    if done.returncode == 0:
        return
    detail = (done.stderr or done.stdout or "").lower()
    if any(phrase in detail for phrase in NOTHING_TO_COMMIT):
        return
    _die((done.stderr or done.stdout or "").strip(), root)


def _message(raw: str) -> str:
    body = " ".join((raw or "").split())
    if body.startswith(PREFIX.strip()):
        body = body[len(PREFIX.strip()):].strip()
    if not body:
        return ""
    if len(body) > BODY_MAX:
        body = body[: BODY_MAX - 3].rstrip() + "..."
    return PREFIX + body


def _run(command, root: Path, label: str, allow_fail: bool = False):
    try:
        done = subprocess.run(command, cwd=root, capture_output=True, text=True)
    except OSError as exc:
        _die(f"{label} could not start: {exc}", root)
    if done.returncode != 0 and not allow_fail:
        _die((done.stderr or done.stdout or label).strip(), root)
    return done


def _die(detail: str, root: Path) -> None:
    print(f"contact-user: checkpoint failed in {root}: {detail}", file=sys.stderr)
    raise SystemExit(Exit.Git.CHECKPOINT_FAILED)
