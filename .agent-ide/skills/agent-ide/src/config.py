"""`agent-ide/data/config.json`: the global project pointer and the publish repo.

    {"paths": {"global_home": "<global project>"},
     "github": {"publish_repo": "owner/repo", "host": "github.com"}}

Everything that belongs to a person or a machine — where the global project
lives, which account and repo to publish to — is data here, never a constant in
the code. `data/` is git-ignored and mirrored into the replica shard, so this
file is both private and recoverable.

`global_home` is valid when the path it names holds `.agent-ide/skills`. When it
is absent, the project is its own global project: that is the shape a fresh
project gets, and the reason a self-reference is normal, not a defect.
"""
from __future__ import annotations
import json
from pathlib import Path

from . import paths
from .errors import Exit, fail

CONFIG = "config.json"


def read(project_root: Path) -> dict:
    try:
        doc = json.loads((paths.data_dir(project_root) / CONFIG).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return doc if isinstance(doc, dict) else {}


def write(project_root: Path, cfg: dict) -> None:
    folder = paths.data_dir(project_root)
    folder.mkdir(parents=True, exist_ok=True)
    cfg.setdefault("version", 1)
    (folder / CONFIG).write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _replicate(project_root)


def _replicate(project_root: Path) -> None:
    """Keep the shard's copy of this state current; never block the write.

    The path of the global project and the publish repo live here, so losing
    them means losing the ability to push and publish at all.
    """
    pkg_dir = paths.package_dir(project_root, paths.AGENT_IDE)
    import sys

    sys.path.insert(0, str(pkg_dir))
    try:
        from replicas import ReplicaError, Replicator
    except ImportError:
        return
    try:
        Replicator.for_skill(pkg_dir).sync_quietly()
    except ReplicaError:
        pass


def _section(cfg: dict, key: str) -> dict:
    block = cfg.get(key)
    return block if isinstance(block, dict) else {}


def _expand(raw: str) -> Path:
    return Path(str(raw)).expanduser().resolve()


def valid_global_home(raw: str | None) -> Path | None:
    if not raw or not str(raw).strip():
        return None
    try:
        home = _expand(raw)
    except (OSError, ValueError):
        return None
    return home if paths.skills_dir(home).is_dir() else None


def global_home(project_root: Path, *, seed: bool = False) -> Path:
    """The configured global project, or the project itself when seeding.

    Seeding is what makes a project with no config its own global project, so
    `push`/`publish` still have a well-defined meaning on a fresh checkout.
    """
    raw = _section(read(project_root), "paths").get("global_home")
    home = valid_global_home(raw)
    if home is not None:
        return home
    if not seed:
        raise fail(
            Exit.Config.MISSING_GLOBAL,
            f"paths.global_home is missing or not a project "
            f"({paths.data_dir(project_root) / CONFIG}); "
            "run init-project from the global project, or set it there",
        )
    set_global_home(project_root, project_root)
    return project_root.resolve()


def set_global_home(project_root: Path, home: Path | str) -> None:
    cfg = read(project_root)
    cfg.setdefault("paths", {})["global_home"] = str(home)
    write(project_root, cfg)


def inherit_global_home(launcher_root: Path, target_root: Path) -> None:
    """Give `target_root` the launcher's global home, unless it has its own.

    A self-reference is treated as unset: it is the seeded default, not a choice
    the user made, so a real global home replaces it.
    """
    home = global_home(launcher_root, seed=True)
    raw = _section(read(target_root), "paths").get("global_home")
    existing = valid_global_home(raw)
    if existing is not None and existing != target_root.resolve():
        return
    set_global_home(target_root, home)


def github_host(project_root: Path) -> str:
    """The host `owner/repo` is expanded against; data, with a public default."""
    raw = _section(read(project_root), "github").get("host")
    if raw and str(raw).strip():
        return str(raw).strip()
    home = valid_global_home(_section(read(project_root), "paths").get("global_home"))
    if home is not None:
        raw = _section(read(home), "github").get("host")
        if raw and str(raw).strip():
            return str(raw).strip()
    return "github.com"


def publish_repo(project_root: Path) -> str | None:
    raw = _section(read(project_root), "github").get("publish_repo")
    if raw and str(raw).strip():
        return str(raw).strip()
    home = global_home(project_root, seed=False)
    raw = _section(read(home), "github").get("publish_repo")
    return str(raw).strip() if raw and str(raw).strip() else None
