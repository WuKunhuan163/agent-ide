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


def kind(manifest: dict) -> str | None:
    """The package's `install.kind`, or None when it installs nothing."""
    block = manifest.get("install")
    return str(block.get("kind")) if isinstance(block, dict) and block.get("kind") else None


def _listed(manifest: dict, key: str) -> list[str]:
    raw = manifest.get(key) or []
    if not isinstance(raw, list):
        raise fail(Exit.Package.FAILED, f"{key} must be a list")
    return [str(item).strip() for item in raw if str(item).strip()]


def files(pkg_dir: Path, manifest: dict) -> list[str]:
    out = set(_listed(manifest, "files")) | set(IMPLICIT)
    if kind(manifest) == "python":
        out.add(f"{pkg_dir.name}.py")
    return sorted(out)


def directories(manifest: dict) -> list[str]:
    return _listed(manifest, "directories")


def validate(pkg_dir: Path, manifest: dict | None = None) -> dict:
    """Every declared path must exist: a whitelist that lies hides broken pushes."""
    manifest = manifest if manifest is not None else load(pkg_dir)
    for rel in files(pkg_dir, manifest):
        if not (pkg_dir / rel).is_file():
            raise fail(Exit.Package.FAILED, f"{pkg_dir.name}: declared file missing: {rel}")
    for rel in directories(manifest):
        if not (pkg_dir / rel).is_dir():
            raise fail(Exit.Package.FAILED, f"{pkg_dir.name}: declared directory missing: {rel}")
    return manifest


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


def python_spec(manifest: dict) -> dict:
    """The `python` block, normalised: requirements and the runtime name.

    `python.runtime.version` is a version such as `3.11.9`; the directory that
    holds the interpreter is named after major.minor (`python3.11`).
    """
    block = manifest.get("python")
    block = block if isinstance(block, dict) else {}
    raw = block.get("requirements") or []
    if not isinstance(raw, list):
        raise fail(Exit.Install.FAILED, "python.requirements must be a list of pip specs")
    runtime = block.get("runtime")
    version = str(runtime.get("version", "")).strip() if isinstance(runtime, dict) else ""
    parts = version.split(".")
    return {
        "requirements": [str(item).strip() for item in raw if str(item).strip()],
        "runtime": f"python{parts[0]}.{parts[1]}" if len(parts) >= 2 else "python3.11",
    }
