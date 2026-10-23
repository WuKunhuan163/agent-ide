"""`agent-ide/data/config.json`: the global project pointer and the publish repo.

    {"paths": {"global_home": "<global project>"},
     "github": {"publish_repo": "owner/repo"}}

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


def _section(cfg: dict, key: str) -> dict:
    block = cfg.get(key)
    return block if isinstance(block, dict) else {}


def _expand(raw: str) -> Path:
    """A configured path: `~` and absolute pass through; a relative one is read
    against this tool's own project, never the shell's cwd."""
    path = Path(str(raw)).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (paths.project_root() / path).resolve()


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
    if raw and str(raw).strip():
        # A configured path that is not a project is a typo or a moved folder.
        # Seeding here would silently rewrite the config and turn `push` into a
        # no-op, which is the one outcome the caller cannot notice.
        raise fail(
            Exit.Config.MISSING_GLOBAL,
            f"paths.global_home points at something that is not a project: {raw} "
            f"(no {paths.IDE_DIR}/skills there); fix it with "
            "`agent-ide push` after restoring the folder, or set it explicitly",
        )
    if not seed:
        raise fail(
            Exit.Config.MISSING_GLOBAL,
            f"paths.global_home is missing or not a project "
            f"({paths.data_dir(project_root) / CONFIG}); "
            "name it with `agent-ide push --from-global --global <path> <skill>`",
        )
    set_global_home(project_root, project_root)
    return project_root.resolve()


def set_global_home(project_root: Path, home: Path | str) -> None:
    cfg = read(project_root)
    cfg.setdefault("paths", {})["global_home"] = str(home)
    write(project_root, cfg)


def adopt_global_home(project_root: Path, home: Path) -> None:
    """Record `home` as the project's global project, unless it has one already.

    A self-reference is treated as unset: it is the seeded default, not a choice
    the user made, so a real global home replaces it. A project that already
    points at a different, existing global project keeps its own pointer.
    """
    existing = valid_global_home(_section(read(project_root), "paths").get("global_home"))
    if existing is not None and existing != project_root.resolve():
        return
    set_global_home(project_root, home)


def publish_repo(project_root: Path) -> str | None:
    raw = _section(read(project_root), "github").get("publish_repo")
    return str(raw).strip() if raw and str(raw).strip() else None
