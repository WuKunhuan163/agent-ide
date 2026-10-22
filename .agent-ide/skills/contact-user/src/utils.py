from __future__ import annotations
from pathlib import Path
import platform, subprocess

def trash(path: Path) -> None:
    if not path.exists(): return
    resolved = str(path.resolve())
    if platform.system() == "Darwin": 
        subprocess.run(
            ['osascript', '-e', f'tell application "Finder" to delete POSIX file "{resolved}"'], 
            check = True, 
        )
        return
    if platform.system() == "Windows": 
        import ctypes
        from ctypes import wintypes
        FO_DELETE, FOF_ALLOWUNDO, FOF_NOCONFIRMATION, FOF_SILENT = 3, 0x40, 0x10, 4
        class _SHOP(ctypes.Structure): 
            _fields_ = [
                ("hwnd", wintypes.HWND), 
                ("wFunc", ctypes.c_uint), 
                ("pFrom", wintypes.LPCWSTR), 
                ("pTo", wintypes.LPCWSTR), 
                ("fFlags", ctypes.c_short), 
                ("fAnyOperationsAborted", wintypes.BOOL), 
                ("hNameMappings", ctypes.c_void_p), 
                ("lpszProgressTitle", wintypes.LPCWSTR), 
            ]
        op = _SHOP(hwnd=None, wFunc=FO_DELETE, pFrom=resolved + "\0\0", pTo = None, 
                   fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT, 
                   fAnyOperationsAborted = False, hNameMappings = None, lpszProgressTitle = None)
        if ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) != 0:  # type: ignore[attr-defined]
            raise OSError(f"Trash failed: {resolved}")
        return
    for cmd in (["trash", resolved], ["gio", "trash", resolved]): 
        try: 
            subprocess.run(cmd, check = True)
            return
        except FileNotFoundError: 
            continue
    raise OSError(f"Trash failed: {resolved}")
