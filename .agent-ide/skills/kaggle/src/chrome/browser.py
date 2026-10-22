"""Chrome profile manager for the kaggle skill.

Two entry points: ``launch_browser`` (raises on failure) and ``open_once`` (a
once-per-process convenience that never raises). One profile per key, one error
surface. There is deliberately no ``webbrowser`` fallback and no ``mode`` switch:
when Chrome cannot be opened the caller gets ``BROWSER_FAILED`` instead of a
silently different browser, so "did we get a real Kaggle session?" always has one
answer.

Profile key (``account``):
    account=None          -> data/agents/<agent_id>/chrome_profile   (cold start, per agent)
    account=<kaggle_user>  -> data/accounts/<kaggle_user>/chrome_profile (shared token pool)
"""
from __future__ import annotations

import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime

from src.exit_codes import BROWSER_FAILED, IdentityError
from src.paths import require_ctx

PROFILE_DIRNAME = "chrome_profile"
LOG_NAME = "chrome_profile.log"


def _canonical_path(path: str) -> str:
    return os.path.realpath(os.path.expanduser(path))


def resolve_profile(account: str | None = None) -> tuple[str, str]:
    """Return ``(profile_dir, log_path)`` for the key; create both parent dirs."""
    ctx = require_ctx()
    base = os.path.join(ctx.accounts_dir, account) if account else ctx.agent_dir
    profile_dir = os.path.join(base, PROFILE_DIRNAME)
    log_path = os.path.join(base, LOG_NAME)
    os.makedirs(profile_dir, exist_ok=True)
    return profile_dir, log_path


def _chrome_profile_log(log_path: str, message: str, **fields) -> None:
    """Append one line per chrome-profile operation (for post-mortem debugging)."""
    if not log_path:
        return
    try:
        parts = [datetime.now().isoformat(timespec="seconds"), message]
        for key, val in fields.items():
            parts.append(f"{key}={val}")
        line = " | ".join(str(p) for p in parts) + "\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def _chrome_profile_is_healthy(profile_dir: str) -> bool:
    pref = os.path.join(profile_dir, "Default", "Preferences")
    try:
        return os.path.isfile(pref) and os.path.getsize(pref) > 100
    except OSError:
        return False


def _chrome_profile_size_mb(profile_dir: str) -> float:
    total = 0
    try:
        for root, _, files in os.walk(profile_dir):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    pass
    except OSError:
        return 0
    return total / (1024 * 1024)


def _chrome_profile_has_data(profile_dir: str) -> bool:
    if not os.path.isdir(profile_dir):
        return False
    for name in os.listdir(profile_dir):
        if name not in ("SingletonLock", "Lock", "SingletonCookie"):
            return True
    return False


def _chrome_profile_lock_pid(profile_dir: str) -> int | None:
    lock_path = os.path.join(profile_dir, "SingletonLock")
    if not os.path.islink(lock_path):
        return None
    try:
        target = os.readlink(lock_path)
        if "-" in target:
            return int(target.rsplit("-", 1)[-1])
    except (OSError, ValueError):
        pass
    return None


def _pid_is_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _profile_chrome_main_pids(profile_dir: str) -> list[int]:
    """Alive Chrome *main* processes for this user-data-dir (SingletonLock alone is unreliable)."""
    profile_dir = _canonical_path(profile_dir)
    pids: set[int] = set()
    lock_pid = _chrome_profile_lock_pid(profile_dir)
    if lock_pid:
        pids.add(lock_pid)
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["pgrep", "-lf", "Google Chrome"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in (result.stdout or "").splitlines():
                if profile_dir not in line or "Google Chrome Helper" in line:
                    continue
                if "/Google Chrome " not in line and not line.rstrip().endswith("Google Chrome"):
                    continue
                try:
                    pids.add(int(line.split(None, 1)[0]))
                except (ValueError, IndexError):
                    pass
        except Exception:
            pass
    elif platform.system() == "Linux":
        try:
            result = subprocess.run(
                ["pgrep", "-af", "chrome"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in (result.stdout or "").splitlines():
                if profile_dir in line and "--type=" not in line:
                    try:
                        pids.add(int(line.split(None, 1)[0]))
                    except (ValueError, IndexError):
                        pass
        except Exception:
            pass
    return [p for p in sorted(pids) if _pid_is_alive(p)]


def _clean_chrome_profile_locks(profile_dir: str, log_path: str | None = None) -> None:
    """Remove stale Chrome singleton artifacts only when no live holder process."""
    holder = _chrome_profile_lock_pid(profile_dir)
    if holder and _pid_is_alive(holder):
        if log_path:
            _chrome_profile_log(log_path, "skip_lock_clean", reason="profile_in_use", pid=holder)
        return
    stale_names = (
        "SingletonLock",
        "SingletonCookie",
        "SingletonSocket",
        "RunningChromeVersion",
        "DevToolsActivePort",
    )
    removed = []
    for lock_file in stale_names:
        lock_path = os.path.join(profile_dir, lock_file)
        if not os.path.lexists(lock_path):
            continue
        try:
            if lock_file == "SingletonSocket" and os.path.islink(lock_path):
                target = os.readlink(lock_path)
                if not os.path.exists(lock_path) and not os.path.exists(target):
                    os.unlink(lock_path)
                    removed.append(lock_file)
                    continue
            if os.path.islink(lock_path):
                os.unlink(lock_path)
            else:
                os.remove(lock_path)
            removed.append(lock_file)
        except OSError as exc:
            if log_path:
                _chrome_profile_log(log_path, "lock_remove_failed", file=lock_file, error=exc)
    if log_path and removed:
        _chrome_profile_log(log_path, "locks_cleaned", removed=",".join(removed))


def _acquire_profile_spawn_slot(profile_dir: str, log_path: str, *, wait_s: float = 5.0) -> str:
    """Return 'reuse' if Chrome holds the profile; 'spawn' if safe to start; 'busy' if contended."""
    mains = _profile_chrome_main_pids(profile_dir)
    if len(mains) > 1:
        _chrome_profile_log(
            log_path,
            "multiple_mains_detected",
            pids=",".join(str(p) for p in mains),
            hint="quit extra Chrome windows for this profile",
        )
        print(
            f"[WARN] Multiple Chrome main processes on profile ({mains}). "
            "Quit extras in Activity Monitor to avoid profile corruption.",
            file=sys.stderr,
        )
    if mains:
        _chrome_profile_log(log_path, "profile_in_use_ps", pids=",".join(str(p) for p in mains))
        return "reuse"
    lock_path = os.path.join(profile_dir, ".kaggle_chrome_open.lock")
    deadline = time.time() + wait_s
    while time.time() < deadline:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, f"{os.getpid()}\n".encode())
            os.close(fd)
            return "spawn"
        except FileExistsError:
            mains = _profile_chrome_main_pids(profile_dir)
            if mains:
                return "reuse"
            time.sleep(0.2)
    _chrome_profile_log(log_path, "open_guard_busy", lock=lock_path)
    return "busy"


def _release_profile_spawn_slot(profile_dir: str) -> None:
    lock_path = os.path.join(profile_dir, ".kaggle_chrome_open.lock")
    try:
        os.remove(lock_path)
    except OSError:
        pass


def _release_spawn_slot_when_chrome_ready(
    profile_dir: str, log_path: str, *, wait_s: float = 12.0
) -> None:
    """Hold .kaggle_chrome_open.lock until Chrome main appears (avoid double-spawn race)."""
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if _profile_chrome_main_pids(profile_dir):
            _release_profile_spawn_slot(profile_dir)
            return
        time.sleep(0.25)
    _chrome_profile_log(log_path, "spawn_lock_release_timeout", wait_s=wait_s)
    _release_profile_spawn_slot(profile_dir)


def _reset_chrome_profile(profile_dir: str, log_path: str) -> None:
    """Explicit reset only — never called automatically outside corrupt self-heal."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.dirname(log_path)
    backup = os.path.join(base, f"chrome_profile_backup_{ts}")
    try:
        if os.path.isdir(profile_dir):
            shutil.move(profile_dir, backup)
    except Exception as exc:
        _chrome_profile_log(log_path, "reset_backup_failed", error=exc)
        shutil.rmtree(profile_dir, ignore_errors=True)
    os.makedirs(profile_dir, exist_ok=True)
    _chrome_profile_log(log_path, "reset_done", backup=backup)
    print(f"[WARN] Chrome profile reset; backup: {backup}", file=sys.stderr)


def _profile_log_tail_has_corruption(log_path: str, profile_dir: str, *, lines: int = 100) -> bool:
    """True when the log shows high-confidence profile corruption (not normal Chrome stderr)."""
    if not os.path.isfile(log_path):
        return False
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except OSError:
        return False
    start = 0
    for i, line in enumerate(all_lines):
        if "reset_done" in line:
            start = i + 1
    text = "".join(all_lines[start:][-lines:])
    if "multiple_mains_detected" in text or "auto_reset_blocked_mains" in text:
        return True
    if "database is locked" in text:
        return True
    if not _chrome_profile_is_healthy(profile_dir):
        return text.count("crashpad/handler/mac/exception_handler_server") >= 5
    return False


def _terminate_profile_chrome(profile_dir: str, log_path: str, *, wait_s: float = 3.0) -> list[int]:
    """SIGTERM then SIGKILL Chrome mains on this profile. Returns surviving PIDs."""
    profile_dir = _canonical_path(profile_dir)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in _profile_chrome_main_pids(profile_dir):
            try:
                os.kill(pid, sig)
            except OSError:
                pass
        if sig == signal.SIGTERM:
            time.sleep(wait_s)
    surviving = _profile_chrome_main_pids(profile_dir)
    if surviving:
        _chrome_profile_log(
            log_path, "terminate_profile_chrome", pids=",".join(str(p) for p in surviving), sig="done"
        )
    return surviving


def _fail_open(log_path: str, reason: str) -> None:
    """Abort the open — the caller must surface BROWSER_FAILED; never a silent fallback."""
    print("\n" + "=" * 72, file=sys.stderr)
    print("[ERROR] BROWSER OPEN FAILED — Chrome profile", file=sys.stderr)
    print(f"  reason:   {reason}", file=sys.stderr)
    print(f"  log:      {log_path or '(none)'}", file=sys.stderr)
    print("\nAGENT: stop push/monitor workflow. Contact the user via contact-user:", file=sys.stderr)
    print("  1) Ask the user to quit all Chrome windows for this profile, then retry open.", file=sys.stderr)
    print("  2) If the profile is corrupt, the next open auto-resets it when no Chrome holds it.", file=sys.stderr)
    print("  Do NOT report 'opened' until open succeeds.", file=sys.stderr)
    print("=" * 72 + "\n", file=sys.stderr)
    raise IdentityError(BROWSER_FAILED, reason)


def _ensure_fresh_profile_if_corrupt(profile_dir: str, log_path: str) -> str:
    """On corrupt profile: kill stale Chrome -> reset -> return the fresh profile dir."""
    has_data = _chrome_profile_has_data(profile_dir)
    unhealthy = has_data and not _chrome_profile_is_healthy(profile_dir)
    corrupt = unhealthy or _profile_log_tail_has_corruption(log_path, profile_dir)
    if not corrupt:
        return profile_dir

    mains = _profile_chrome_main_pids(profile_dir)
    if mains:
        print(
            f"[WARN] Corrupt Chrome profile — stopping PIDs {mains} and resetting.",
            file=sys.stderr,
        )
        _chrome_profile_log(log_path, "auto_recover_kill", pids=",".join(str(p) for p in mains))
        surviving = _terminate_profile_chrome(profile_dir, log_path)
        if surviving:
            _fail_open(
                log_path,
                f"Profile corrupt; could not stop Chrome PIDs {surviving}. "
                "Quit them in Activity Monitor, then retry open.",
            )

    _chrome_profile_log(log_path, "auto_reset_corrupt_profile", path=profile_dir)
    print("[WARN] Chrome profile is corrupt — auto-reset to a fresh profile.", file=sys.stderr)
    _reset_chrome_profile(profile_dir, log_path)
    _clean_chrome_profile_locks(profile_dir, log_path=log_path)
    return profile_dir


def assess_chrome_profile(account: str | None = None) -> dict:
    """Programmatic corruption detection — run before reporting open success."""
    profile_dir, log_path = resolve_profile(account)
    has_data = _chrome_profile_has_data(profile_dir)
    healthy_prefs = _chrome_profile_is_healthy(profile_dir) if has_data else True
    log_corrupt = _profile_log_tail_has_corruption(log_path, profile_dir)
    corrupt = (has_data and not healthy_prefs) or log_corrupt
    pids = _profile_chrome_main_pids(profile_dir)

    if corrupt and pids:
        verdict = "CORRUPT_IN_USE"
        action = f"DETECTED corrupt profile. Open will kill PIDs {pids}, reset, and relaunch."
    elif corrupt:
        verdict = "CORRUPT"
        action = "DETECTED corrupt profile. Next open will auto-reset to a fresh profile."
    elif pids:
        verdict = "IN_USE"
        action = "Chrome already running; open will add --new-window."
    else:
        verdict = "OK"
        action = "Profile healthy; ready to open."

    return {
        "account": account,
        "profile_dir": profile_dir,
        "verdict": verdict,
        "corrupt": corrupt,
        "healthy_prefs": healthy_prefs,
        "log_corrupt": log_corrupt,
        "chrome_pids": pids,
        "action": action,
        "log_path": log_path,
    }


def preflight_chrome_open(account: str | None = None) -> str:
    """Resolve the profile dir and self-heal corruption before a launch."""
    profile_dir, log_path = resolve_profile(account)
    return _ensure_fresh_profile_if_corrupt(profile_dir, log_path)


def _find_chrome() -> str | None:
    system = platform.system()
    if system == "Darwin":
        path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        return path if os.path.exists(path) else None
    if system == "Windows":
        for path in (
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ):
            if os.path.exists(path):
                return path
        return None
    if system == "Linux":
        return shutil.which("google-chrome") or shutil.which("chrome")
    return None


def _reuse_chrome_window(
    chrome_path: str, profile_arg: str, url: str, *, log_path: str, mains: list[int]
) -> None:
    """Open URL in the existing Chrome profile — always --new-window for visibility."""
    reuse_cmd = [
        chrome_path,
        profile_arg,
        "--profile-directory=Default",
        "--new-window",
        url,
    ]
    _chrome_profile_log(
        log_path,
        "reuse_existing",
        pids=",".join(str(p) for p in mains) if mains else "unknown",
        cmd=" ".join(reuse_cmd),
    )
    subprocess.Popen(reuse_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(
        "[INFO] Chrome tab/window requested. If not visible: Cmd+Tab to Chrome or check Dock.",
        file=sys.stderr,
    )


def launch_browser(url: str, *, account: str | None = None) -> None:
    """Open ``url`` in Chrome under this key's isolated profile.

    Raises ``IdentityError(BROWSER_FAILED)`` when Chrome is missing, the profile
    is contended, or the launch fails. There is no fallback browser.
    """
    profile_dir, log_path = resolve_profile(account)
    _ensure_fresh_profile_if_corrupt(profile_dir, log_path)

    chrome_path = _find_chrome()
    if not chrome_path:
        _chrome_profile_log(log_path, "chrome_not_found")
        _fail_open(log_path, "Google Chrome not found on this machine.")

    _clean_chrome_profile_locks(profile_dir, log_path=log_path)
    profile_arg = f"--user-data-dir={profile_dir}"

    launch_log = None
    spawn_slot = None
    try:
        launch_log = open(log_path, "a", encoding="utf-8")
        spawn_slot = _acquire_profile_spawn_slot(profile_dir, log_path)
        if spawn_slot == "reuse":
            _reuse_chrome_window(
                chrome_path, profile_arg, url,
                log_path=log_path, mains=_profile_chrome_main_pids(profile_dir),
            )
            return
        if spawn_slot == "busy":
            _chrome_profile_log(log_path, "open_busy", url=url)
            _fail_open(log_path, "Chrome profile spawn lock busy after wait — concurrent open race.")

        mains = _profile_chrome_main_pids(profile_dir)
        if mains:
            _reuse_chrome_window(chrome_path, profile_arg, url, log_path=log_path, mains=mains)
            return

        cmd = [
            chrome_path,
            profile_arg,
            "--profile-directory=Default",
            "--no-first-run",
            "--no-default-browser-check",
            "--new-window",
            url,
        ]
        _chrome_profile_log(log_path, "launch", cmd=" ".join(cmd))
        subprocess.Popen(cmd, stdout=launch_log, stderr=subprocess.STDOUT)
    except IdentityError:
        raise
    except Exception as exc:
        _chrome_profile_log(log_path, "launch_failed", error=exc)
        _fail_open(log_path, f"Chrome launch exception: {exc}")
    finally:
        if spawn_slot == "spawn":
            _release_spawn_slot_when_chrome_ready(profile_dir, log_path)
        if launch_log and not launch_log.closed:
            launch_log.flush()
            launch_log.close()


_opened_urls: set[str] = set()


def open_once(url: str, *, account: str | None = None) -> None:
    """Open ``url`` at most once per process; warn and swallow instead of raising.

    Cold-start convenience only: the caller is usually on its way to raising an
    actionable error of its own (e.g. AUTH_NO_ACCOUNT), so BROWSER_FAILED must not
    mask it. ``launch_browser`` stays the strict entry point.
    """
    if url in _opened_urls:
        return
    _opened_urls.add(url)
    try:
        launch_browser(url, account=account)
    except IdentityError as exc:
        print(f"[WARN] Could not open the browser automatically: {exc}", file=sys.stderr)
