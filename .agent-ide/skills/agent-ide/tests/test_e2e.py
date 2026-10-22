"""The real CLI, end to end: push --from-global -> install -> push -> publish."""
from __future__ import annotations
import subprocess
import unittest

from helpers import PY, SKILL_DIR, Base, make_runtime

from src import config, paths, transfer
from src.errors import Exit


class EndToEndTests(Base):
    def setUp(self) -> None:
        super().setUp()
        # this very package becomes the global project's agent-ide, whitelist only
        transfer.package("agent-ide", SKILL_DIR.parent, paths.skills_dir(self.global_root))
        make_runtime(self.global_root)
        config.set_global_home(self.global_root, self.global_root)
        self.cli = paths.skills_dir(self.global_root) / "agent-ide" / "agent-ide.py"

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [PY, str(self.cli), *args], capture_output=True, text=True, cwd=str(self.tmp)
        )

    def bootstrap(self) -> subprocess.CompletedProcess:
        """Join the ecosystem the way a user does: name the global, then import."""
        pushed = self.run_cli("push", "--from-global", "--global", str(self.global_root),
                              "--project", str(self.local), "agent-ide")
        if pushed.returncode == 0:
            pushed = self.run_cli("install", "--project", str(self.local), "agent-ide")
        return pushed

    def test_named_global_imports_and_installs(self):
        marker = paths.data_dir(self.global_root) / "secret.txt"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("x", encoding="utf-8")

        done = self.bootstrap()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((paths.skills_dir(self.local) / "agent-ide" / "src" / "install.py").is_file())
        self.assertFalse(
            (paths.data_dir(self.local) / "secret.txt").exists(), "data/ pulled"
        )
        self.assertEqual(config.global_home(self.local), self.global_root.resolve())
        launcher = paths.tools_dir(self.local) / "agent-ide"
        help_done = subprocess.run([str(launcher), "--help"], capture_output=True, text=True)
        self.assertEqual(help_done.returncode, 0, help_done.stderr)

    def test_invalid_global_is_rejected(self):
        done = self.run_cli("push", "--from-global", "--global", str(self.tmp / "nowhere"),
                            "--project", str(self.local), "agent-ide")
        self.assertEqual(done.returncode, Exit.Config.MISSING_GLOBAL, done.stdout)
        self.assertIn("--global is not a project", done.stderr)
        self.assertFalse(paths.skills_dir(self.local).joinpath("agent-ide").exists())

    def test_global_without_from_global_is_a_usage_error(self):
        done = self.run_cli("push", "--global", str(self.global_root), "agent-ide")
        self.assertEqual(done.returncode, Exit.Cli.USAGE, done.stdout)
        self.assertIn("--from-global", done.stderr)

    def test_named_global_keeps_an_existing_pointer(self):
        self.assertEqual(self.bootstrap().returncode, 0)
        other = self.tmp / "other"
        (other / ".agent-ide" / "skills").mkdir(parents=True)
        config.set_global_home(self.local, other)

        done = self.run_cli("push", "--from-global", "--global", str(self.global_root),
                            "--project", str(self.local), "agent-ide")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(config.global_home(self.local), other.resolve())

    def test_push_local_to_global(self):
        self.assertEqual(self.bootstrap().returncode, 0)
        local_cli = paths.tools_dir(self.local) / "agent-ide"
        local_pkg = paths.skills_dir(self.local) / "agent-ide"
        marker = local_pkg / "SKILL.md"
        marker.write_text("# LOCAL EDIT 7f21\n", encoding="utf-8")
        # data/ must never travel, even though it exists next to the package
        (local_pkg / "data").mkdir(exist_ok=True)
        (local_pkg / "data" / "secret.txt").write_text("x", encoding="utf-8")

        done = subprocess.run([str(local_cli), "push", "agent-ide"], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        global_pkg = paths.skills_dir(self.global_root) / "agent-ide"
        self.assertIn("LOCAL EDIT 7f21", (global_pkg / "SKILL.md").read_text(encoding="utf-8"))
        self.assertFalse((global_pkg / "data" / "secret.txt").exists(), "data/ pushed")

    def test_push_from_global_restores_local(self):
        self.assertEqual(self.bootstrap().returncode, 0)
        local_cli = paths.tools_dir(self.local) / "agent-ide"
        marker = paths.skills_dir(self.local) / "agent-ide" / "SKILL.md"
        marker.write_text("# LOCAL BROKEN 9f3\n", encoding="utf-8")

        done = subprocess.run(
            [str(local_cli), "push", "--from-global", "agent-ide"], capture_output=True, text=True
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("LOCAL BROKEN 9f3", marker.read_text(encoding="utf-8"))

    def test_publish_to_bare_remote(self):
        remote = self.tmp / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        cfg = config.read(self.global_root)
        cfg["github"] = {"publish_repo": str(remote)}
        config.write(self.global_root, cfg)

        first = self.run_cli("publish", "agent-ide")
        self.assertEqual(first.returncode, 0, first.stderr)

        clone = self.tmp / "verify"
        subprocess.run(["git", "clone", "-q", str(remote), str(clone)], check=True)
        published = clone / ".agent-ide" / "skills" / "agent-ide"
        self.assertTrue((published / "SKILL.md").is_file())
        self.assertTrue((published / "src" / "install.py").is_file())
        self.assertFalse((published / "data").exists(), "data/ published")
        self.assertFalse((published / "src" / "__pycache__").exists(), "cache published")

        again = self.run_cli("publish", "agent-ide")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("up to date", again.stdout)

    def test_publish_reports_push_failure(self):
        remote = self.tmp / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        cfg = config.read(self.global_root)
        cfg["github"] = {"publish_repo": str(remote)}
        config.write(self.global_root, cfg)
        self.assertEqual(self.run_cli("publish", "agent-ide").returncode, 0)

        # a read-only remote is the deterministic form of "push rejected"
        for path in sorted(remote.rglob("*"), reverse=True):
            path.chmod(0o555 if path.is_dir() else 0o444)
        remote.chmod(0o555)
        self.addCleanup(lambda: [p.chmod(0o755 if p.is_dir() else 0o644) for p in [remote, *remote.rglob("*")]])

        marker = paths.skills_dir(self.global_root) / "agent-ide" / "SKILL.md"
        marker.write_text("# CHANGED 4c1\n", encoding="utf-8")
        blocked = self.run_cli("publish", "agent-ide")
        self.assertEqual(blocked.returncode, Exit.Publish.FAILED, blocked.stdout)
        self.assertIn("git push failed", blocked.stderr)

    def test_publish_keeps_unrelated_remote_files(self):
        remote = self.tmp / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        seed = self.tmp / "seed"
        subprocess.run(["git", "clone", "-q", str(remote), str(seed)], check=True)
        (seed / "README.md").write_text("keep me\n", encoding="utf-8")
        for args in (["add", "."], ["commit", "-qm", "seed"], ["push", "-q", "origin", "HEAD"]):
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                           cwd=seed, check=True)
        cfg = config.read(self.global_root)
        cfg["github"] = {"publish_repo": str(remote)}
        config.write(self.global_root, cfg)

        self.assertEqual(self.run_cli("publish", "agent-ide").returncode, 0)
        verify = self.tmp / "verify"
        subprocess.run(["git", "clone", "-q", str(remote), str(verify)], check=True)
        self.assertTrue((verify / "README.md").is_file(), "publish wiped unrelated files")
        self.assertTrue((verify / ".agent-ide" / "skills" / "agent-ide" / "SKILL.md").is_file())

    def test_publish_without_repo(self):
        done = self.run_cli("publish", "agent-ide")
        self.assertEqual(done.returncode, Exit.Publish.FAILED)
        self.assertIn("no repo configured", done.stderr)

    def test_publish_from_github(self):
        remote = self.tmp / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        cfg = config.read(self.global_root)
        cfg["github"] = {"publish_repo": str(remote)}
        config.write(self.global_root, cfg)
        self.assertEqual(self.run_cli("publish", "agent-ide").returncode, 0)

        # someone edits the published copy
        other = self.tmp / "editor"
        subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
        remote_md = other / ".agent-ide" / "skills" / "agent-ide" / "SKILL.md"
        remote_md.write_text("# from github\n", encoding="utf-8")
        for args in (["add", "."], ["commit", "-qm", "edit"], ["push", "-q", "origin", "HEAD"]):
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                           cwd=other, check=True)

        pulled = self.run_cli("publish", "--from-github", "agent-ide")
        self.assertEqual(pulled.returncode, 0, pulled.stderr)
        self.assertIn(
            "from github",
            (paths.skills_dir(self.global_root) / "agent-ide" / "SKILL.md").read_text(
                encoding="utf-8"
            ),
        )

    def test_publish_unknown_skill(self):
        remote = self.tmp / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
        cfg = config.read(self.global_root)
        cfg["github"] = {"publish_repo": str(remote)}
        config.write(self.global_root, cfg)
        done = self.run_cli("publish", "ghost")
        self.assertEqual(done.returncode, Exit.Package.FAILED, done.stdout)


if __name__ == "__main__":
    unittest.main()
