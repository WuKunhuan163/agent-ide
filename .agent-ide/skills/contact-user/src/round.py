"""One blocking contact round.

    lock -> (wait if a round is running) -> gate -> inputs -> bell + GUI
         -> archive -> checkpoint -> mirror -> marker -> print the reply

The order matters twice: the gate runs before anything is consumed, so a
blocked round leaves its drafts intact; the archive runs before the checkpoint,
so the reply survives a git failure.
"""
from __future__ import annotations
import atexit
import os
import subprocess
import sys
import time

from . import checkpoint, config, gate, handshake, paths, session_mirror
from .exit_codes import Exit
from .process import is_alive

POLL_SECS = 0.5


def run(agent_id: str) -> int:
    reply = _reply_from_running_round(agent_id)
    if reply is not None:
        print(reply)
        return Exit.OK

    reason = gate.blocked_reason(agent_id)
    if reason:
        first, *rest = reason.splitlines()
        print(f"contact-user: {first}", file=sys.stderr)
        for line in rest:
            print(f"  {line}", file=sys.stderr)
        return Exit.Runtime.CONTEXT_REQUIRED

    contact_text, commit_text = _load_inputs(agent_id)
    _discard_inputs(agent_id)

    _take_lock(agent_id)
    reply = _open_gui(agent_id, contact_text)
    if reply is None:
        print(
            f"contact-user: no reply after {config.gui_attempts()} windows",
            file=sys.stderr,
        )
        return Exit.Runtime.GUI_ABORTED

    _finalize(agent_id, reply, contact_text, commit_text)
    print(reply)
    return Exit.OK


# ------------------------------------------------------------ an open round


def _lock_pid(agent_id: str) -> int | None:
    try:
        return int(paths.lock(agent_id).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _take_lock(agent_id: str) -> None:
    lock = paths.lock(agent_id)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(str(os.getpid()), encoding="utf-8")

    def release() -> None:
        try:
            if _lock_pid(agent_id) == os.getpid():
                lock.unlink(missing_ok=True)
        except OSError:
            pass

    atexit.register(release)


def _reply_from_running_round(agent_id: str) -> str | None:
    """Wait for a round already in progress and return the reply it produced.

    A reply is delivered on this path without being archived by us — the other
    process archived it — so it is read from the archive rather than printed
    from memory.
    """
    pid = _lock_pid(agent_id)
    if pid is None or not is_alive(pid) or pid == os.getpid():
        return None
    started = time.time()
    while is_alive(pid):
        time.sleep(POLL_SECS)
    return _newest_response_since(agent_id, started - 1)


def _newest_response_since(agent_id: str, since: float) -> str | None:
    folder = paths.data(paths.RESPONSE, agent_id)
    if not folder.is_dir():
        return None
    candidates = []
    for path in folder.glob("*_user_response.txt"):
        try:
            if path.stat().st_mtime >= since:
                candidates.append((path.stat().st_mtime, path))
        except OSError:
            continue
    if not candidates:
        return None
    latest = max(candidates)[1]
    try:
        return latest.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


# --------------------------------------------------------------------- inputs


def _load_inputs(agent_id: str) -> tuple[str, str]:
    contact = _read_required(
        paths.input_text(agent_id, "contact"),
        missing=Exit.Input.MISSING_CONTACT,
        empty=Exit.Input.EMPTY_CONTACT,
    )
    commit = _read_required(
        paths.input_text(agent_id, "commit"),
        missing=Exit.Input.MISSING_COMMIT,
        empty=Exit.Input.EMPTY_COMMIT,
    )
    return contact, commit


def _read_required(path, *, missing: int, empty: int) -> str:
    if not path.is_file():
        print(f"contact-user: 缺草稿 {path}\n"
              f"       路径以 `--id <id> --input-path` 打印的为准", file=sys.stderr)
        raise SystemExit(missing)
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        print(f"contact-user: 草稿是空的 {path}", file=sys.stderr)
        raise SystemExit(empty)
    return text.strip()


def _discard_inputs(agent_id: str) -> None:
    for kind in ("contact", "commit"):
        try:
            paths.input_text(agent_id, kind).unlink(missing_ok=True)
        except OSError:
            pass


# ------------------------------------------------------------------ gui round


def _gui_executable(agent_id: str) -> str:
    """The agent's `.app` bundle when it can be built, so the Dock shows the id
    and the skill icon instead of a bare Python interpreter."""
    from .app_bundle import ensure_agent_app

    try:
        bundle = ensure_agent_app(agent_id)
    except (OSError, RuntimeError):
        bundle = None
    return str(bundle) if bundle is not None else sys.executable


def _open_gui(agent_id: str, contact_text: str) -> str | None:
    """Spawn the window until the user submits; None when every attempt failed.

    The draft the agent wrote is handed over in the environment, not on the
    command line: it is the text the user must see when the window opens, and it
    can be long, multiline and full of quotes.
    """
    code = "from src.gui import main; main()"
    env = dict(os.environ, CONTACT_USER_HINT=contact_text)
    for _ in range(config.gui_attempts()):
        handshake.clear(agent_id)
        try:
            subprocess.run(
                [_gui_executable(agent_id), "-c", code, agent_id],
                cwd=str(paths.pkg_dir()),
                capture_output=True,
                text=True,
                env=env,
            )
        except OSError as exc:
            print(f"contact-user: window failed to start: {exc}", file=sys.stderr)
        status, content = handshake.read(agent_id)
        if status == "SUBMITTED":
            return content.strip()
        time.sleep(1)
    return None


# ------------------------------------------------------------------ finalize


def _finalize(agent_id: str, reply: str, contact_text: str, commit_text: str) -> None:
    """Archive first (the reply must survive a git failure), then commit."""
    _archive(agent_id, reply, contact_text)
    checkpoint.commit(commit_text)
    _after_commit(agent_id)


def _archive(agent_id: str, reply: str, contact_text: str) -> None:
    """Both halves of the round, from the text already in memory."""
    for kind, body in ((paths.RESPONSE, reply), (paths.CONTACT, contact_text)):
        path = paths.archived(agent_id, kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def _after_commit(agent_id: str) -> None:
    """Auxiliary state, after the reply exists on disk and git has run.

    None of these steps may turn a delivered round into a failed one.
    """
    session_mirror.sync_quietly()
    _sync_replicas()
    try:
        gate.write_marker(agent_id)
    except OSError as exc:
        print(f"contact-user: marker not written: {exc}", file=sys.stderr)


def _sync_replicas() -> None:
    """Ask agent-ide to copy both archives into the shard it manages."""
    sys.path.insert(0, str(paths.project_root() / ".agent-ide" / "skills" / "agent-ide"))
    try:
        from replicas import ReplicaError, Replicator
    except ImportError as exc:
        print(f"contact-user: replica sync skipped: {exc}", file=sys.stderr)
        return
    try:
        Replicator.for_skill(paths.pkg_dir()).sync_quietly()
    except ReplicaError as exc:
        print(f"contact-user: replica sync skipped: {exc}", file=sys.stderr)
