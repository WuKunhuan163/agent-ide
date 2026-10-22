"""Shared fixtures: a throwaway global project, packages, and a fake runtime."""
from __future__ import annotations
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR))

from src import paths  # noqa: E402
from src.errors import AgentIdeError  # noqa: E402

PY = sys.executable


def make_project(root: Path) -> Path:
    (root / ".agent-ide" / "skills").mkdir(parents=True, exist_ok=True)
    return root


def make_package(
    skills_root: Path,
    name: str = "demo",
    *,
    kind: str | None = "python",
    files: list[str] | None = None,
    directories: list[str] | None = None,
    entry: bool = True,
    manifest: dict | None = None,
) -> Path:
    pkg = skills_root / name
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    if manifest is None:
        doc: dict = {
            "files": files if files is not None else [],
            "directories": directories if directories is not None else ["src"],
        }
        if kind:
            doc["install"] = {"kind": kind}
            doc["python"] = {
                "requirements": [],
                "stdlib": [],
                "runtime": {"version": "3.11.9"},
            }
    else:
        doc = manifest
    (pkg / "skill.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    if entry:
        (pkg / f"{name}.py").write_text(f"print('{name} ok')\n", encoding="utf-8")
    (pkg / "src").mkdir(exist_ok=True)
    (pkg / "src" / "lib.py").write_text("VALUE = 1\n", encoding="utf-8")
    return pkg


def make_runtime(home: Path, name: str = "python3.11") -> Path:
    """A shim interpreter exactly where install expects one."""
    prefix = paths.runtime_root(home) / paths.platform_tag() / name
    binary = prefix / "bin" / name
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text(f'#!/bin/sh\nexec "{PY}" "$@"\n', encoding="utf-8")
    binary.chmod(0o755)
    return binary


class Base(unittest.TestCase):
    """A temp dir with a `global` project and a `local` project."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-ide-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        # Replica shards hang off `~`; a test run must not litter the real one.
        self._home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.tmp / "home")
        self.addCleanup(self._restore_home)
        self.global_root = make_project(self.tmp / "global")
        self.skills = paths.skills_dir(self.global_root)
        self.local = make_project(self.tmp / "local")

    def _restore_home(self) -> None:
        if self._home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._home

    def expect(self, code: int, fn, *args, **kwargs) -> AgentIdeError:
        with self.assertRaises(AgentIdeError) as caught:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code, caught.exception.message)
        return caught.exception

    def quiet(self, fn, *args, **kwargs):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = fn(*args, **kwargs)
        return result, out.getvalue(), err.getvalue()
