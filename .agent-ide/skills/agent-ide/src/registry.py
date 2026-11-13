"""Machine-wide register of the projects that share one global project.

`push` moves a package from a project into the global project. Before this
module existed, every other project had to learn about that copy by hand: one
`push --from-global` plus one `install` per project, remembered by the user.

The register answers "which other projects are on this machine" once, and the
answer lives outside every project (`~/.agent-ide/projects.json`), because a
project cannot own a list of projects — the first `git clone` of it would ship
paths that are wrong on every other machine.

    {"version": 1,
     "projects": [{"path": "/abs/project", "name": "example-project",
                   "global_home": "/abs/global",
                   "updated": "2026-11-11T09:00:00Z"}]}

Rules that keep the file trustworthy:

- A path is stored resolved and is only ever a *hint*: every consumer checks
  that `.agent-ide/skills` is still there and skips the entry when it is not.
  Machines get reorganised, and a register that fails a push because a laptop
  folder moved would be worse than no register at all.
- Writing is best-effort. A read-only home directory must not break `push`, so
  `remember` swallows its own errors and the caller never sees them.
- `AGENT_IDE_REGISTRY` overrides the location, which is how the tests keep
  their register out of the developer's home.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import install, paths, transfer

ENV = "AGENT_IDE_REGISTRY"
FILE = "projects.json"


# ---------------------------------------------------------------- file access


def location() -> Path:
    """The register file: `$AGENT_IDE_REGISTRY`, else `~/.agent-ide/projects.json`."""
    raw = os.environ.get(ENV)
    if raw and raw.strip():
        return Path(raw).expanduser().resolve()
    return (Path.home() / paths.IDE_DIR / FILE).resolve()


def load() -> dict:
    """The register as a dict; a missing or unreadable file is an empty one."""
    try:
        doc = json.loads(location().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "projects": []}
    if not isinstance(doc, dict) or not isinstance(doc.get("projects"), list):
        return {"version": 1, "projects": []}
    doc.setdefault("version", 1)
    return doc


def save(doc: dict) -> None:
    target = location()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def entries() -> list[dict]:
    """Every stored entry that still holds `.agent-ide/skills`."""
    found: list[dict] = []
    for item in load()["projects"]:
        if not isinstance(item, dict):
            continue
        raw = item.get("path")
        if not raw:
            continue
        path = Path(str(raw)).expanduser()
        if paths.skills_dir(path).is_dir():
            found.append({**item, "path": str(path.resolve())})
    return found


def _normal(project: Path) -> Path:
    return project.expanduser().resolve()


def _entry(project: Path, global_home: Path | None) -> dict:
    entry = {
        "path": str(_normal(project)),
        "name": _normal(project).name,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if global_home is not None:
        entry["global_home"] = str(_normal(global_home))
    return entry


# ------------------------------------------------------------------- mutation


def add(project: Path, global_home: Path | None = None) -> dict:
    """Register `project`, replacing an entry that names the same path."""
    target = _normal(project)
    if not paths.skills_dir(target).is_dir():
        raise ValueError(f"not a project (no {paths.IDE_DIR}/skills): {target}")
    doc = load()
    kept = [
        item for item in doc["projects"]
        if isinstance(item, dict) and str(item.get("path", "")) != str(target)
    ]
    entry = _entry(target, global_home)
    doc["projects"] = kept + [entry]
    save(doc)
    return entry


def remove(project: Path) -> bool:
    """Drop the entry for `project`; False when it was not registered."""
    target = str(_normal(project))
    doc = load()
    kept = [
        item for item in doc["projects"]
        if not (isinstance(item, dict) and str(item.get("path", "")) == target)
    ]
    if len(kept) == len(doc["projects"]):
        return False
    doc["projects"] = kept
    save(doc)
    return True


def remember(project: Path, global_home: Path | None = None) -> None:
    """Register `project`, silently.

    Called from every command that resolves a project, so the register fills
    itself from normal use. A failure here must not fail that command: the
    register is a convenience, and `push` is the thing the user asked for.
    """
    try:
        add(project, global_home)
    except (OSError, ValueError, TypeError):
        return


# -------------------------------------------------------------------- fan-out


def partners(source: Path, global_home: Path) -> list[Path]:
    """Registered projects other than `source` and `global_home`."""
    skip = {str(_normal(source)), str(_normal(global_home))}
    return [Path(item["path"]) for item in entries() if item["path"] not in skip]


def fanout(source: Path, global_home: Path, names: list[str]) -> list[tuple[Path, str]]:
    """Copy `names` from the global project into every registered partner.

    Returns `[(project, status)]` with status `copied` or a one-line reason.
    A partner that fails is reported and skipped: one broken sibling must not
    turn the push the user asked for into a failure.
    """
    results: list[tuple[Path, str]] = []
    for project in partners(source, global_home):
        try:
            transfer.batch(names, paths.skills_dir(global_home), paths.skills_dir(project),
                           "pull")
            install.run(project, names)
            remember(project, global_home)
            results.append((project, "copied"))
        except Exception as exc:  # noqa: BLE001 — a partner is not our failure to raise
            reason = getattr(exc, "message", None) or str(exc).splitlines()[0]
            results.append((project, reason))
    return results


def report(results: list[tuple[Path, str]]) -> None:
    """One line per partner: where it went, and whether it did."""
    for project, status in results:
        print(f"registry: {paths.pretty(project)}: {status}")


def fanout_names(source: Path, global_home: Path) -> list[str]:
    """Package names the global project offers that a partner may be missing."""
    home = paths.skills_dir(global_home)
    if not home.is_dir():
        return []
    return sorted(p.name for p in home.iterdir() if (p / paths.MANIFEST).is_file())


IDE_DIR = paths.IDE_DIR
MANIFEST = paths.MANIFEST
