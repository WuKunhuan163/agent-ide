"""macOS .app bundle for the login GUI: Dock name (agent id) + skill icon.

The GUI is a Tk process; when it runs the bare standalone ``python3.11`` binary,
macOS shows "python3.11" with the stock Python icon in the Dock. Spawning the GUI
through a generated ``.app`` bundle makes LaunchServices attribute the process to
that bundle, so the Dock shows ``aliyunpan-<agent id>`` and ``src/icon.svg``.

Bundle layout (``<project>/.agent-tools/apps/<agent_id>.app``)::

    Contents/Info.plist
    Contents/MacOS/aliyunpan-<agent_id>   copy of the standalone python interpreter
    Contents/lib                symlink to the standalone interpreter's lib/
    Contents/Resources/AppIcon.icns

Returns ``None`` on non-Darwin or when the interpreter is not a relocatable
standalone build, so callers can fall back to plain ``sys.executable``.
"""
from __future__ import annotations
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

from .paths import project_root

APPS_DIRNAME = "apps"
ICON_FILE = "AppIcon.icns"
_ICON_CACHE_NAME = ".aliyunpan.AppIcon.icns"
_ICON_SVG = Path("src") / "icon.svg"
_ICON_PIXEL_SIZE = 1024
_RENDER_TIMEOUT = 60
_ICONSET_ENTRIES: tuple[tuple[int, int], ...] = (
    (16, 16), (16, 32), (32, 32), (32, 64), (128, 128),
    (128, 256), (256, 256), (256, 512), (512, 512), (512, 1024),
)


def _apps_dir() -> Path:
    return project_root() / ".agent-tools" / APPS_DIRNAME


def _standalone_prefix() -> Path | None:
    """Prefix of the relocatable standalone interpreter hosting this process."""
    try:
        prefix = Path(sys.executable).resolve().parent.parent
    except OSError:
        return None
    lib = prefix / "lib" / f"libpython{sys.version_info.major}.{sys.version_info.minor}.dylib"
    return prefix if lib.is_file() else None


def _app_name(agent_id: str) -> str:
    cleaned = re.sub(r"[/:]", "-", (agent_id or "").strip())
    return f"aliyunpan-{cleaned or 'agent'}"


def _bundle_identifier(agent_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (agent_id or "").strip().lower()).strip("-")
    if not slug:
        slug = f"id{zlib.crc32((agent_id or '').encode('utf-8')):08x}"
    return f"com.agentide.aliyunpan.{slug}"


def _icon_svg() -> Path | None:
    from .paths import pkg_dir
    svg = pkg_dir() / _ICON_SVG
    return svg if svg.is_file() else None


def _run(cmd: list[str]) -> bool:
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=_RENDER_TIMEOUT, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def _render_icns(svg: Path, icns: Path) -> bool:
    with tempfile.TemporaryDirectory(prefix="aliyunpan-icon-") as tmp:
        tmp_dir = Path(tmp)
        png = tmp_dir / "icon.png"
        if not _run(["qlmanage", "-t", "-s", str(_ICON_PIXEL_SIZE), "-o", str(tmp_dir), str(svg)]):
            return False
        rendered = tmp_dir / f"{svg.name}.png"
        if not rendered.is_file():
            return False
        png.write_bytes(rendered.read_bytes())
        iconset = tmp_dir / "AppIcon.iconset"
        iconset.mkdir()
        for size, pixels in _ICONSET_ENTRIES:
            suffix = "@2x" if pixels != size else ""
            out = iconset / f"icon_{size}x{size}{suffix}.png"
            if not _run(["sips", "-z", str(pixels), str(pixels), str(png), "--out", str(out)]):
                return False
        icns.parent.mkdir(parents=True, exist_ok=True)
        if not _run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)]):
            return False
    return icns.is_file()


def _icon_cache() -> Path:
    return _apps_dir() / _ICON_CACHE_NAME


def _ensure_icon() -> Path | None:
    """Render ``src/icon.svg`` to a cached .icns shared by every agent bundle."""
    svg = _icon_svg()
    if svg is None:
        return None
    icns = _icon_cache()
    try:
        fresh = icns.is_file() and icns.stat().st_mtime >= svg.stat().st_mtime
    except OSError:
        fresh = False
    if fresh:
        return icns
    try:
        icns.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    staged = icns.with_name(f".stage.{icns.name}")
    if _render_icns(svg, staged):
        try:
            staged.replace(icns)
            return icns
        except OSError:
            pass
    staged.unlink(missing_ok=True)
    return icns if icns.is_file() else None


def _ensure_interpreter(exe: Path) -> bool:
    """Copy the standalone interpreter into the bundle under the app name."""
    src = Path(sys.executable).resolve()
    try:
        if exe.is_symlink():
            exe.unlink()
        elif (exe.is_file()
              and exe.stat().st_mtime >= src.stat().st_mtime
              and exe.stat().st_size == src.stat().st_size):
            return True
        exe.parent.mkdir(parents=True, exist_ok=True)
        staged = exe.with_name(exe.name + ".tmp")
        staged.unlink(missing_ok=True)
        shutil.copy2(src, staged)
        staged.replace(exe)
        exe.chmod(exe.stat().st_mode | 0o111)
    except OSError:
        return False
    return True


def _ensure_lib_link(link: Path, target: Path) -> bool:
    """``@executable_path/../lib`` must resolve for the copied interpreter."""
    try:
        if link.is_symlink():
            if os.readlink(link) == str(target):
                return True
            link.unlink()
        elif link.exists():
            return True
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
    except OSError:
        return False
    return True


def _ensure_app_icon(resources: Path, icns: Path | None) -> None:
    if icns is None:
        return
    dest = resources / ICON_FILE
    try:
        if dest.exists() and dest.stat().st_mtime >= icns.stat().st_mtime:
            return
        dest.unlink(missing_ok=True)
        shutil.copy2(icns, dest)
    except OSError:
        pass


def _plist(agent_id: str, name: str) -> dict:
    return {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleExecutable": name,
        "CFBundleIdentifier": _bundle_identifier(agent_id),
        "CFBundleName": name,
        "CFBundleDisplayName": name,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1",
        "CFBundleIconFile": "AppIcon",
        "CFBundleInfoDictionaryVersion": "6.0",
        "LSMinimumSystemVersion": "10.13",
        "NSHighResolutionCapable": True,
    }


def _write_plist(plist: Path, agent_id: str, name: str) -> bool:
    try:
        with plist.open("wb") as handle:
            plistlib.dump(_plist(agent_id, name), handle)
    except (OSError, plistlib.InvalidFileException):
        return False
    return True


def ensure_agent_app(agent_id: str) -> Path | None:
    """Create/refresh the agent's macOS bundle; return its executable path."""
    if platform.system() != "Darwin":
        return None
    prefix = _standalone_prefix()
    if prefix is None:
        return None
    name = _app_name(agent_id)
    app = _apps_dir() / f"{name}.app"
    contents = app / "Contents"
    exe = contents / "MacOS" / name
    try:
        contents.mkdir(parents=True, exist_ok=True)
        (contents / "MacOS").mkdir(exist_ok=True)
        resources = contents / "Resources"
        resources.mkdir(exist_ok=True)
    except OSError:
        return None
    if not _ensure_interpreter(exe):
        return None
    if not _ensure_lib_link(contents / "lib", prefix / "lib"):
        return None
    if not _write_plist(contents / "Info.plist", agent_id, name):
        return None
    _ensure_app_icon(resources, _ensure_icon())
    try:
        os.utime(app)
    except OSError:
        pass
    return exe if exe.is_file() else None
