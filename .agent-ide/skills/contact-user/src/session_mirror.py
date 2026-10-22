"""A separate git repository that versions the transcript's content.

The IDE owns its transcript files and never runs git there, so this module
mirrors the *parsed* content into `data/session_mirror/` (one JSONL per
conversation) and commits it after every round. `data/` is git-ignored by the
project, so this repository stays independent of the project checkpoint.

Syncs are incremental: `index.json` keeps the last timestamp and the tail of
message ids per conversation, so a round parses only what was written since.
"""
from __future__ import annotations
import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from . import config
from .ide.base import SessionStore, parse_ts
from .paths import mirror

REASONING_MAX = 8000
RESULT_MAX = 2000
TAIL_IDS = 500
OVERLAP_SECS = 180
GIT_IDENTITY = ("-c", "user.name=contact-user", "-c", "user.email=contact-user@localhost")


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *GIT_IDENTITY, *args], cwd=cwd, capture_output=True, text=True)


def ensure_repo() -> Path:
    repo = mirror()
    if not (repo / ".git").is_dir():
        done = _git("init", "-q", cwd=repo)
        if done.returncode != 0:
            raise RuntimeError((done.stderr or done.stdout or "git init failed").strip())
    return repo


def sync(store: SessionStore) -> dict:
    repo = ensure_repo()
    previous = _index(repo).get("conversations")
    previous = previous if isinstance(previous, dict) else {}

    conversations = store.conversations()
    state: dict[str, dict] = {}
    total = added = 0
    touched: list[str] = []

    for conv in conversations:
        name = store.label(conv)
        old = previous.get(name) if isinstance(previous.get(name), dict) else {}
        known = {str(mid) for mid in (old.get("tail_ids") or [])}
        since = _since(old)

        if _unchanged(conv, old):
            total += int(old.get("count") or 0)
            state[name] = old
            continue

        messages = store.read_messages(conv, since)
        fresh = [m for m in messages if m.mid not in known]
        target = repo / f"{name}.jsonl"
        if not target.exists():
            target.write_text("", encoding="utf-8")
            touched.append(target.name)
        if fresh:
            with target.open("a", encoding="utf-8") as handle:
                for message in fresh:
                    handle.write(json.dumps(_record(message), ensure_ascii=False) + "\n")
            added += len(fresh)
            touched.append(target.name)

        count = int(old.get("count") or 0) + len(fresh)
        if not old.get("count") and not fresh:
            count = len(store.message_files(conv))
        last_at = messages[-1].at.isoformat() if messages and messages[-1].at else old.get("last_at")
        state[name] = {
            "count": count,
            "last_at": last_at,
            "tail_ids": [m.mid for m in messages[-TAIL_IDS:]] or (old.get("tail_ids") or []),
        }
        total += count

    removed = _drop_stale(repo, {f"{store.label(conv)}.jsonl" for conv in conversations})
    (repo / "index.json").write_text(
        json.dumps(
            {"source_root": str(store.root), "ide": store.ide_id,
             "conversations": state, "messages": total},
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    committed = _commit(repo, touched, removed, added, total, len(conversations))
    return {
        "repo": str(repo),
        "ide": store.ide_id,
        "conversations": len(conversations),
        "messages": total,
        "added": added,
        "removed": len(removed),
        "committed": committed,
    }


def log(n: int = 10) -> str:
    repo = ensure_repo()
    done = _git("log", f"-{max(1, n)}", "--oneline", cwd=repo)
    return done.stdout.strip() if done.returncode == 0 else (done.stderr or "").strip()


def sync_quietly() -> None:
    """Best-effort sync at the end of a round: it must never fail the round."""
    if not config.mirror_enabled():
        return
    try:
        sync(config.make_store())
    except (config.ConfigError, RuntimeError, OSError) as exc:
        print(f"contact-user: mirror skipped: {exc}", file=sys.stderr)


# ----------------------------------------------------------------- internals


def _record(message) -> dict:
    return {
        "id": message.mid,
        "role": message.role,
        "at": message.at.isoformat() if message.at else None,
        "text": message.text,
        "reasoning": message.reasoning[:REASONING_MAX],
        "calls": [{"name": call.name, "args": call.args} for call in message.calls],
        "results": [
            {"name": r.name, "status": r.status, "isError": r.is_error,
             "text": r.text[:RESULT_MAX]}
            for r in message.results
        ],
    }


def _index(repo: Path) -> dict:
    try:
        doc = json.loads((repo / "index.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _since(state: dict):
    last = parse_ts(state.get("last_at")) if state.get("last_at") else None
    return last - timedelta(seconds=OVERLAP_SECS) if last else None


def _unchanged(conv: Path, state: dict) -> bool:
    """`messages/` mtime moves only when a file is added: one stat beats a scan."""
    last = parse_ts(state.get("last_at")) if state.get("last_at") else None
    if last is None or not state.get("count"):
        return False
    try:
        return (conv / "messages").stat().st_mtime <= last.timestamp() + 5
    except OSError:
        return False


def _drop_stale(repo: Path, keep: set[str]) -> list[str]:
    """A re-pinned store must not leave another store's conversations behind."""
    removed = []
    for path in repo.glob("*.jsonl"):
        if path.name in keep:
            continue
        try:
            path.unlink()
            removed.append(path.name)
        except OSError:
            continue
    return removed


def _commit(repo: Path, touched: list[str], removed: list[str], added: int,
            total: int, conversations: int) -> bool:
    present = [name for name in dict.fromkeys(touched) if (repo / name).exists()]
    done = _git("add", "--", *present, "index.json", cwd=repo)
    if done.returncode != 0:
        raise RuntimeError((done.stderr or done.stdout or "git add failed").strip())
    if removed:
        _git("add", "-A", "--", *removed, cwd=repo)  # staged deletions only
    if _git("diff", "--cached", "--quiet", cwd=repo).returncode == 0:
        return False
    message = f"session: +{added} msgs (total {total}) / {conversations} conversations"
    done = _git("commit", "-q", "-m", message, cwd=repo)
    if done.returncode != 0:
        raise RuntimeError((done.stderr or done.stdout or "git commit failed").strip())
    return True
