"""Copying a skill package under its own whitelist.

Only the manifest's files and directories move. `data/` — archives, caches,
credentials — is never declared, so it never leaves the machine it lives on.
A declared directory is further cut by `exclude`: per-project material that a
package keeps inside its own tree (one project's drafts, a real identifier
next to a template) would otherwise ride along on a whole-directory entry.
Directories are replaced wholesale, so a deleted source file disappears at the
destination too; files are copied, never pruned, because a package's `data/`
must survive a push.

**The copy is read back.** A push that reports success because the copy loop
finished is reporting an intention, not an outcome: `shutil.copy2` returning
normally says nothing about what landed, and the most expensive failure in
this file's history was a skill edited in one project and never arriving in
the global one, with every command exiting 0. So the declared paths are
hashed at both ends and compared, and a difference fails the command with
the file names — the same round-trip rule the report method applies to builds.
"""
from __future__ import annotations
import hashlib
import shutil
from pathlib import Path

from . import manifest as manif, paths
from .errors import Exit, fail

IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", ".git")


_SKIP_NAMES = {"__pycache__", ".DS_Store", ".git"}


def _ignored(path: Path) -> bool:
    """Mirror IGNORE: what the copy leaves out, the check must leave out too."""
    return (
        path.name in _SKIP_NAMES
        or path.suffix == ".pyc"
        or ".git" in path.parts
        or "__pycache__" in path.parts
    )


def _digest(root: Path, spec: dict) -> dict[str, str]:
    """sha256 per declared path, ignoring what IGNORE or `exclude` drops.

    The check has to drop exactly what the copy drops: an excluded path
    counted here would report a missing file the copy was told never to
    write, and the push would fail on a package that is behaving.
    """
    out: dict[str, str] = {}
    patterns = manif.excludes(spec)
    for rel in manif.files(root, spec):
        path = root / rel
        if path.is_file() and not manif.excluded(rel, patterns):
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    for rel in manif.directories(spec):
        base = root / rel
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            rel_path = path.relative_to(root).as_posix()
            if path.is_file() and not _ignored(path) and not manif.excluded(rel_path, patterns):
                out[rel_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _ignore(src: Path, spec: dict):
    """`IGNORE` plus the manifest's `exclude`, for `copytree`.

    `ignore` is asked once per directory, so backtracking the relative path
    here is how a whole subtree is refused without walking it first.
    """
    patterns = manif.excludes(spec)

    def ignore(directory: str, names: list[str]):
        out = set(IGNORE(directory, names))
        if not patterns:
            return out
        here = Path(directory)
        for name in names:
            if name in out:
                continue
            rel = (here / name).relative_to(src).as_posix()
            if manif.excluded(rel, patterns):
                out.add(name)
        return out

    return ignore


def _verify(name: str, src: Path, dest: Path, spec: dict) -> int:
    """Read the destination back and compare; return the number of files proven."""
    want = _digest(src, spec)
    got = _digest(dest, spec)
    missing = sorted(set(want) - set(got))
    differing = sorted(rel for rel in want if rel in got and want[rel] != got[rel])
    if missing or differing:
        sample = ", ".join((missing + differing)[:3])
        raise fail(
            Exit.Package.FAILED,
            f"{name}: push reported copying but the destination disagrees: {sample}"
            f" ({len(missing)} missing, {len(differing)} differing)",
        )
    return len(want)


def package(name: str, src_root: Path, dest_root: Path, *, validate: bool = True) -> int:
    src = src_root / name
    dest = dest_root / name
    if not src.is_dir():
        raise fail(Exit.Package.FAILED, f"skill package not found: {src}")
    if src.resolve() == dest.resolve():
        return 0

    spec = manif.load(src)
    if validate:
        manif.validate(src, spec)

    patterns = manif.excludes(spec)
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for rel in manif.files(src, spec):
            source = src / rel
            if not source.is_file():
                if validate:
                    raise fail(Exit.Package.FAILED, f"{name}: declared file missing: {rel}")
                continue
            if manif.excluded(rel, patterns):
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        for rel in manif.directories(spec):
            source = src / rel
            if not source.is_dir():
                if validate:
                    raise fail(Exit.Package.FAILED, f"{name}: declared directory missing: {rel}")
                continue
            target = dest / rel
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target, symlinks=True, ignore=_ignore(src, spec))
    except OSError as exc:
        # A read-only or full destination is a normal failure, not a crash:
        # the caller gets one line and the exit code the CLI promises.
        raise fail(
            Exit.Package.FAILED, f"{name}: cannot write to {dest}: {exc}"
        ) from exc

    return _verify(name, src, dest, spec)


def batch(names: list[str], src_root: Path, dest_root: Path, verb: str) -> list[str]:
    """Copy every named package; the first failure aborts with its own message."""
    targets = manif.packages(src_root, names)
    verified = 0
    if src_root.resolve() != dest_root.resolve():
        dest_root.mkdir(parents=True, exist_ok=True)
        for name in targets:
            verified += package(name, src_root, dest_root)
    suffix = f" ({verified} files verified)" if verified else ""
    print(f"{verb}: {' '.join(targets)} -> {paths.pretty(dest_root)}{suffix}")
    return targets
