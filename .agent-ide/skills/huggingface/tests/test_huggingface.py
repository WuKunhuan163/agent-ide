"""Offline checks: per-agent token isolation (`config` / `get`), no network."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
ENTRY = SKILL / "src" / "main.py"
AGENT = "pytest_hf"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ENTRY), "--id", AGENT, *args],
        capture_output=True, text=True, timeout=20,
    )


class TokenTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(SKILL / "data" / "accounts" / AGENT, ignore_errors=True)

    def tearDown(self) -> None:
        shutil.rmtree(SKILL / "data" / "accounts" / AGENT, ignore_errors=True)

    def test_config_writes_per_agent_file(self):
        done = run("config", "--token", "tok-123")
        self.assertEqual(done.returncode, 0, done.stderr)
        saved = SKILL / "data" / "accounts" / AGENT / "config.json"
        self.assertEqual(json.loads(saved.read_text())["token"], "tok-123")

    def test_get_returns_saved_token(self):
        run("config", "--token", "tok-456")
        done = run("get")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), "tok-456")  # stdout carries the value only

    def test_get_without_config_exits_nonzero(self):
        done = run("get")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("no token", done.stderr)
        self.assertEqual(done.stdout, "")

    def test_missing_id_is_rejected(self):
        done = subprocess.run([sys.executable, str(ENTRY), "get"],
                              capture_output=True, text=True, timeout=20)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("--id", done.stderr)


if __name__ == "__main__":
    unittest.main()
