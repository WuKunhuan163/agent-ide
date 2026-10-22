"""Process liveness, without the platform zoo.

`os.kill(pid, 0)` is the portable test on POSIX; on Windows it raises for any
probe, so the Windows branch asks the platform API instead. Neither path may
raise: a lock file with a garbage pid simply means "nobody is running".
"""
from __future__ import annotations
import os
import platform


def is_alive(pid: int | str | None) -> bool:
    try:
        pid = int(pid or 0)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if platform.system() == "Windows":
        return _windows_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _windows_alive(pid: int) -> bool:
    try:
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # type: ignore[attr-defined]
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))  # type: ignore[attr-defined]
        ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    except Exception:
        return False


def kill(pid: int | str) -> None:
    try:
        if platform.system() == "Windows":
            os.system(f"taskkill /F /PID {int(pid)} >NUL 2>&1")
        else:
            os.kill(int(pid), 9)
    except (OSError, ValueError):
        pass
