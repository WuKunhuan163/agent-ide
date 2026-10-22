"""`init-project`: make a target project a working member of the ecosystem.

Order matters. The global pointer is inherited first, so a bad pointer is
repaired even when the transfer fails; `agent-ide` must be among the pulled
packages, because everything afterwards is launched by it; the `.gitignore` is
seeded last, and only when the target has none.
"""
from __future__ import annotations
import sys
from pathlib import Path

from . import config, install, paths, transfer
from .errors import Exit, fail

DEFAULT_SKILLS = ("agent-ide", "contact-user", "collaboration")
ESSENTIAL = "agent-ide"

GITIGNORE = """**/tmp/
**/data/
**/build/
**/dist/
**/__pycache__/
*.spec
.agent-tools/
quick_access/
"""


def run(launcher_root: Path, target: Path, skills: list[str] | None = None) -> None:
    project = target.expanduser().resolve()
    project_skills = paths.skills_dir(project)
    project_skills.mkdir(parents=True, exist_ok=True)

    home = config.global_home(launcher_root, seed=True)
    global_skills = paths.skills_dir(home)
    requested = list(dict.fromkeys(skills or DEFAULT_SKILLS))
    available = [name for name in requested if (global_skills / name).is_dir()]
    for name in requested:
        if name not in available:
            print(
                f"[WARN] init-project: {name!r} not in the global project, skipped "
                f"({global_skills / name})",
                file=sys.stderr,
            )

    config.inherit_global_home(launcher_root, project)
    if ESSENTIAL not in available:
        raise fail(
            Exit.Package.FAILED,
            f"global project is unusable: no {ESSENTIAL} under {global_skills}",
        )

    transfer.batch(available, global_skills, project_skills, "init-project")
    install.run(project, available)
    _seed_gitignore(project)


def _seed_gitignore(project: Path) -> None:
    path = project / ".gitignore"
    if not path.is_file():
        path.write_text(GITIGNORE, encoding="utf-8")
