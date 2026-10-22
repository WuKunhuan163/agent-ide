"""Incremental, append-only copies of a skill's `data/` — the public interface.

agent-ide owns this mechanism end to end: where the copies live, what is
included, how they are written and what permissions they get. A skill only
says *when* a copy is due:

    from replicas import Replicator          # <project>/.agent-ide/skills/agent-ide on sys.path
    Replicator.for_skill(pkg_dir).sync_quietly()

`skill.json` decides the rest:

    "replicas": {"root": "~/.agent-ide/replicas", "mode": "append_only",
                 "include": ["data/contact_msg/**"], "exclude": ["data/**/runtime/**"]}

Layout::

    <root>/<project>-<hash>/<skill>/<path relative to the package>

The hash keeps two projects with the same directory name apart. `root` must
lie outside the project: inside it the copies would be committed to git
(leaking every archived reply and token) and would be lost together with the
project — the two reasons the copies exist.
"""
from __future__ import annotations
import fnmatch
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST = "skill.json"
APPEND_ONLY = "append_only"
MIRROR = "mirror"
MODES = (APPEND_ONLY, MIRROR)


class ReplicaError(RuntimeError):
    """A missing or unsafe declaration, or a failed copy. Message is user-facing."""


@dataclass
class Report:
    """What one `status`/`sync` saw; `sync` reports copies, `status` gaps."""

    skill: str
    shard: Path
    copied: int = 0
    updated: int = 0
    missing: int = 0
    drift: int = 0
    conflicts: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.conflicts

    def line(self) -> str:
        """One shell-friendly line: only the counts that are not zero."""
        parts = []
        if self.copied:
            parts.append(f"+{self.copied} copied")
        if self.updated:
            parts.append(f"{self.updated} updated")
        if self.missing:
            parts.append(f"{self.missing} missing")
        if self.drift:
            parts.append(f"{self.drift} to refresh")
        if self.conflicts:
            parts.append(f"{len(self.conflicts)} conflict")
        return f"replicas: {self.skill} {' '.join(parts) or 'ok'}"


class Replicator:
    """One skill's copy job, built from its manifest.

    Construct with `for_skill`; the constructor validates the declaration, so a
    skill that never named a shard fails here instead of silently copying
    nowhere.
    """

    def __init__(self, pkg_dir: Path, manifest: dict) -> None:
        self.pkg_dir = Path(pkg_dir).resolve()
        self.manifest = manifest
        self.block = _block(self.pkg_dir, manifest)
        self.mode = str(self.block.get("mode") or APPEND_ONLY)
        self.shard = self._shard()

    @classmethod
    def for_skill(cls, pkg_dir: Path) -> "Replicator":
        pkg_dir = Path(pkg_dir).resolve()
        return cls(pkg_dir, _load(pkg_dir))

    # ---------------------------------------------------------------- location

    def _shard(self) -> Path:
        text = str(self.block.get("root") or "").strip()
        if not text:
            raise ReplicaError(
                f'{self.pkg_dir.name}: replicas.root is missing; add e.g. '
                '"root": "~/.agent-ide/replicas"'
            )
        root = Path(os.path.expanduser(text))
        if not root.is_absolute():
            raise ReplicaError(
                f"{self.pkg_dir.name}: replicas.root must be absolute: {text}"
            )
        project = _project_root(self.pkg_dir)
        resolved = root.resolve()
        if resolved == project or project in resolved.parents:
            raise ReplicaError(
                f"{self.pkg_dir.name}: replicas.root is inside the project "
                f"({resolved}); git would commit the copies. Point it outside, "
                "e.g. ~/.agent-ide/replicas"
            )
        digest = hashlib.sha1(str(project).encode("utf-8")).hexdigest()[:6]
        return resolved / f"{project.name}-{digest}" / self.pkg_dir.name

    # ------------------------------------------------------------------ files

    def sources(self) -> dict[str, Path]:
        include = [str(p) for p in (self.block.get("include") or []) if str(p).strip()]
        exclude = [str(p) for p in (self.block.get("exclude") or []) if str(p).strip()]
        found: dict[str, Path] = {}
        for pattern in include:
            for path in self._expand(pattern):
                if not path.is_file():
                    continue
                rel = path.relative_to(self.pkg_dir).as_posix()
                if any(fnmatch.fnmatch(rel, rule) for rule in exclude):
                    continue
                found[rel] = path
        return dict(sorted(found.items()))

    def _expand(self, pattern: str):
        """`dir/**` means every file below `dir`, on every Python version.

        `Path.glob("**")` yields only directories before 3.13, so a trailing
        `/**` would silently match nothing on the 3.11 runtime the launchers
        use — and a copy job that copies nothing is worse than none.
        """
        if pattern.endswith("/**"):
            yield from (self.pkg_dir / pattern[: -len("/**")]).rglob("*")
        else:
            yield from self.pkg_dir.glob(pattern)

    # ------------------------------------------------------------------- jobs

    def status(self) -> Report:
        """Nothing is written: `missing`/`stale` is how far the copy has fallen behind."""
        report = Report(skill=self.pkg_dir.name, shard=self.shard)
        for rel, source in self.sources().items():
            target = self.shard / rel
            if not target.exists():
                report.missing += 1
            elif not _same(source, target):
                report.drift += 1
        return report

    def sync(self) -> Report:
        """Copy what is missing.

        `append_only` never overwrites (archives are facts); `mirror` refreshes
        a changed file in place (state has one current value). Neither deletes.
        """
        report = Report(skill=self.pkg_dir.name, shard=self.shard)
        for rel, source in self.sources().items():
            target = self.shard / rel
            if target.exists():
                if _same(source, target):
                    continue
                if self.mode == MIRROR:
                    _ensure(target.parent)
                    shutil.copy2(source, target)
                    report.updated += 1
                else:
                    report.conflicts.append(rel)
                continue
            _ensure(target.parent)
            shutil.copy2(source, target)
            report.copied += 1
        return report

    def sync_quietly(self) -> Report | None:
        """`sync` for a caller whose own job matters more, e.g. a delivered round.

        Any failure is reported on one line and returns None; it never raises,
        so a broken copy can neither hide nor undo the work that triggered it.
        """
        try:
            return self.sync()
        except (ReplicaError, OSError) as exc:
            print(f"{self.pkg_dir.name}: replica sync skipped: {exc}", file=sys.stderr)
            return None


# ----------------------------------------------------------------- reporting


def targets(skills_root: Path) -> list[Path]:
    """Every package under `skills_root` that declares a replicas block."""
    out = []
    for pkg_dir in sorted(Path(skills_root).iterdir()):
        if not (pkg_dir / MANIFEST).is_file():
            continue
        try:
            manifest = _load(pkg_dir)
            _block(pkg_dir, manifest)
        except (ReplicaError, OSError):
            continue
        out.append(pkg_dir)
    return out


# ------------------------------------------------------------------- helpers


def _load(pkg_dir: Path) -> dict:
    path = Path(pkg_dir) / MANIFEST
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReplicaError(f"{Path(pkg_dir).name}: unreadable {path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ReplicaError(f"{path}: must be a JSON object")
    return manifest


def _block(pkg_dir: Path, manifest: dict) -> dict:
    raw = manifest.get("replicas")
    if not isinstance(raw, dict):
        raise ReplicaError(
            f"{Path(pkg_dir).name}: skill.json declares no replicas block, so "
            "this skill's data/ has no disaster-recovery copy"
        )
    mode = str(raw.get("mode") or APPEND_ONLY)
    if mode not in MODES:
        raise ReplicaError(
            f"{Path(pkg_dir).name}: unsupported replicas.mode {mode!r} "
            f"(expected {' or '.join(MODES)})"
        )
    return raw


def _project_root(pkg_dir: Path) -> Path:
    for parent in Path(pkg_dir).parents:
        if (parent / ".agent-ide" / "skills").is_dir():
            return parent
    raise ReplicaError(f"{pkg_dir}: no project root above the package")


def _ensure(path: Path) -> None:
    """Create `path` owner-only: copies hold replies and credentials."""
    if path.is_dir():
        return
    _ensure(path.parent)
    path.mkdir(exist_ok=True)
    os.chmod(path, 0o700)


def _same(source: Path, target: Path) -> bool:
    try:
        if source.stat().st_size != target.stat().st_size:
            return False
        return source.read_bytes() == target.read_bytes()
    except OSError:
        return False
