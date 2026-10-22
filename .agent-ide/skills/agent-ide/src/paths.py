"""Filesystem layout of the ecosystem.

    <project>/.agent-ide/skills/<skill>/…      skill packages
    <project>/.agent-ide/skills/agent-ide/data/config.json
    <global>/.agent-ide/runtime/standalone/python/<platform>/<pythonX.Y>/
    <project>/.agent-tools/<skill>            generated launchers
"""
from __future__ import annotations
import os
import platform
from pathlib import Path

IDE_DIR = ".agent-ide"
SKILL_MD = "SKILL.md"
MANIFEST = "skill.json"
AGENT_IDE = "agent-ide"


def project_root(anchor: Path | None = None) -> Path:
    """Nearest ancestor of `anchor` that holds `.agent-ide/skills`."""
    script = (anchor or Path(__file__)).resolve()
    for parent in script.parents:
        if skills_dir(parent).is_dir():
            return parent
    from .errors import missing_root

    raise missing_root()


def skills_dir(project_root: Path) -> Path:
    return project_root / IDE_DIR / "skills"


def package_dir(project_root: Path, name: str) -> Path:
    return skills_dir(project_root) / name


def data_dir(project_root: Path) -> Path:
    return package_dir(project_root, AGENT_IDE) / "data"


def tools_dir(project_root: Path) -> Path:
    return project_root / ".agent-tools"


def runtime_root(global_home: Path) -> Path:
    return global_home / IDE_DIR / "runtime" / "standalone" / "python"


def pretty(path: Path | str) -> str:
    """`~/…` instead of the full home path, so lines stay readable in a shell."""
    text = str(path)
    home = str(Path.home())
    return "~" + text[len(home):] if text.startswith(home + os.sep) else text


def platform_tag() -> str:
    system = platform.system()
    machine = platform.machine().lower()
    arch = {
        ("Darwin", "arm64"): "darwin-arm64",
        ("Darwin", "x86_64"): "darwin-x86_64",
        ("Linux", "aarch64"): "linux-aarch64",
        ("Linux", "x86_64"): "linux-x86_64",
    }.get((system, "aarch64" if machine == "aarch64" else machine))
    if arch:
        return arch
    return f"{system.lower()}-{machine}" if system and machine else "unknown-unknown"
