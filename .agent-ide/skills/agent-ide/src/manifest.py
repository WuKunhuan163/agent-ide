"""`skill.json`: the whitelist that defines what a skill package *is*.

Transfers copy exactly this set, so a package's contents travel identically
local -> global -> GitHub:

* always `SKILL.md` and `skill.json`;
* `<name>.py` when `install.kind` is `python` (the launcher's entry);
* every path in `files`;
* every directory in `directories`, minus every path in `exclude`.

`directories` names a whole tree because a package is mostly code and docs;
it does not follow that everything grown under that tree is package content.
A skill that keeps per-project material inside its own tree — one project's
drafts, one project's ledger, a real identifier next to a template — declares
that tree in `exclude`, or the tree ships to every project that pulls the
package. A whitelist that can only say yes to a directory is not a whitelist
for anything that lives inside one.
"""
from __future__ import annotations
import fnmatch
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


def excludes(manifest: dict) -> list[str]:
    """The `exclude` patterns: what a declared directory does *not* carry."""
    return _listed(manifest, "exclude")


def excluded(rel: str, patterns: list[str]) -> bool:
    """Whether `rel` stays out of a transfer, under the manifest's `exclude`.

    A pattern is matched against the path and against each parent directory,
    in list order; the **last** pattern that matches decides, and a leading
    `!` puts the path back in. That shape is what a package with per-project
    material needs: one line drops the whole `data/` tree, the next few name
    the directories inside it that are templates rather than somebody's work.
    Matching is `fnmatch`, so `*` crosses `/` — write the whole path, not just
    the leaf name.
    """
    rel = rel.replace("\\", "/").strip("/")
    if not rel:
        return False
    parts = rel.split("/")
    chain = ["/".join(parts[:n]) for n in range(1, len(parts) + 1)]
    state = False
    for raw in patterns:
        pattern = raw.replace("\\", "/").strip()
        negate = pattern.startswith("!")
        if negate:
            pattern = pattern[1:].strip()
        pattern = pattern.strip("/")
        if not pattern:
            continue
        if any(fnmatch.fnmatchcase(path, pattern) for path in chain):
            state = not negate
    return state


def validate(pkg_dir: Path, manifest: dict | None = None) -> dict:
    """Every declared path must exist, and no declared path may be excluded.

    A whitelist that lies hides broken pushes: an `exclude` that swallows an
    entry is the same lie written the other way round, and it would ship
    nothing where the manifest says something travels.
    """
    manifest = manifest if manifest is not None else load(pkg_dir)
    patterns = excludes(manifest)
    for rel in files(pkg_dir, manifest):
        if not (pkg_dir / rel).is_file():
            raise fail(Exit.Package.FAILED, f"{pkg_dir.name}: declared file missing: {rel}")
        if excluded(rel, patterns):
            raise fail(
                Exit.Package.FAILED,
                f"{pkg_dir.name}: {rel} is listed in `files` and matched by `exclude`",
            )
    for rel in directories(manifest):
        if not (pkg_dir / rel).is_dir():
            raise fail(Exit.Package.FAILED, f"{pkg_dir.name}: declared directory missing: {rel}")
        if excluded(rel, patterns):
            raise fail(
                Exit.Package.FAILED,
                f"{pkg_dir.name}: {rel} is listed in `directories` and matched by `exclude`",
            )
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
