"""`skill.json`: the whitelist that defines what a skill package *is*.

Transfers copy exactly this set, so a package's contents travel identically
local -> global -> GitHub:

* always `SKILL.md` and `skill.json`;
* `<name>.py` when `install.kind` is `python` (the launcher's entry);
* every path in `files`;
* every whole directory in `directories`.
"""
from __future__ import annotations
import json
from pathlib import Path

from . import paths
from .errors import Exit, fail

IMPLICIT = ("SKILL.md", "skill.json")


def load(pkg_dir: Path) -> dict:
    path = pkg_dir / paths.MANIFEST
    if not path.is_file():
        raise fail(Exit.Package.FAILED, f"missing {paths.MANIFEST}: {pkg_dir}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise fail(Exit.Package.FAILED, f"invalid {paths.MANIFEST}: {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise fail(Exit.Package.FAILED, f"{paths.MANIFEST} must be an object: {path}")
    return manifest


def install_kind(manifest: dict) -> str | None:
    block = manifest.get("install")
    return str(block.get("kind")) if isinstance(block, dict) and block.get("kind") else None


def entry_name(pkg_dir: Path, manifest: dict) -> str | None:
    """Python packages are entered as `<package name>.py` beside the manifest."""
    return pkg_dir.name if install_kind(manifest) == "python" else None


def files(pkg_dir: Path, manifest: dict) -> list[str]:
    declared = manifest.get("files") or []
    if not isinstance(declared, list):
        raise fail(Exit.Package.FAILED, f"{pkg_dir.name}: files must be a list")
    out = {str(item).strip() for item in declared if str(item).strip()}
    out.update(IMPLICIT)
    entry = entry_name(pkg_dir, manifest)
    if entry:
        out.add(f"{entry}.py")
    return sorted(out)


def directories(manifest: dict) -> list[str]:
    declared = manifest.get("directories") or []
    if not isinstance(declared, list):
        raise fail(Exit.Package.FAILED, f"{pkg_dir.name}: directories must be a list")
    return [str(item).strip() for item in declared if str(item).strip()]


def validate(pkg_dir: Path, manifest: dict | None = None) -> dict:
    """Every declared path must exist: a whitelist that lies hides broken pushes."""
    manifest = manifest if manifest is not None else load(pkg_dir)
    for rel in files(pkg_dir, manifest):
        if not (pkg_dir / rel).is_file():
            raise fail(Exit.Package.FAILED, f"{pkg_dir.name}: declared file missing: {rel}")
    for rel in directories(manifest):
        if not (pkg_dir / rel).is_dir():
            raise fail(Exit.Package.FAILED, f"{pkg_dir.name}: declared directory missing: {rel}")
    _check_replicas(pkg_dir, manifest)
    return manifest


def _check_replicas(pkg_dir: Path, manifest: dict) -> None:
    """A declared `replicas` block must name a usable shard, or transfer stops."""
    if "replicas" not in manifest:
        return
    from replicas import ReplicaError, Replicator

    try:
        Replicator(pkg_dir, manifest)
    except ReplicaError as exc:
        raise fail(Exit.Package.FAILED, str(exc)) from exc


def packages(skills_root: Path, requested: list[str]) -> list[str]:
    """Requested skill names, de-duplicated, existing, with a manifest."""
    names: list[str] = []
    for raw in requested:
        name = str(raw).strip().rstrip("/")
        if not name:
            continue
        if name in (".", "..") or "/" in name or "\\" in name:
            raise fail(Exit.Package.FAILED, f"invalid skill name: {raw!r}")
        if name in names:
            continue
        pkg = skills_root / name
        if not pkg.is_dir():
            raise fail(Exit.Package.FAILED, f"skill package not found: {pkg}")
        load(pkg)
        names.append(name)
    if not names:
        raise fail(Exit.Package.FAILED, "no skill names given")
    return names


# ------------------------------------------------------------------ python block


def python_block(manifest: dict) -> dict:
    block = manifest.get("python")
    return block if isinstance(block, dict) else {}


def _string_list(manifest: dict, key: str, what: str) -> list[str]:
    raw = python_block(manifest).get(key) or []
    if not isinstance(raw, list):
        raise fail(Exit.Install.FAILED, f"python.{key} must be a list of {what}")
    return [str(item).strip() for item in raw if str(item).strip()]


def requirements(manifest: dict) -> list[str]:
    return _string_list(manifest, "requirements", "pip specs")


def stdlib(manifest: dict) -> list[str]:
    return _string_list(manifest, "stdlib", "module names")


def runtime_name(manifest: dict) -> str:
    """Directory name of the interpreter prefix: `python3.11`."""
    runtime = python_block(manifest).get("runtime")
    version = str(runtime.get("version", "")).strip() if isinstance(runtime, dict) else ""
    parts = version.split(".")
    return f"python{parts[0]}.{parts[1]}" if len(parts) >= 2 else "python3.11"
