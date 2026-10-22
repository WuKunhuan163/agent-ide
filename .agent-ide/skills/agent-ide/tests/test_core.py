"""Boundaries of the four primitives: manifest, transfer, install, config, inject, init."""
from __future__ import annotations
import json
import os
import subprocess
import tarfile
import unittest

from helpers import PY, Base, make_package, make_runtime

from src import config, init, inject, install, manifest as manif, paths
from src.errors import Exit


class ManifestTests(Base):
    def test_missing_manifest(self):
        pkg = self.skills / "demo"
        pkg.mkdir(parents=True)
        self.expect(Exit.Package.FAILED, manif.load, pkg)

    def test_broken_json(self):
        pkg = self.skills / "demo"
        pkg.mkdir(parents=True)
        (pkg / "skill.json").write_text("{not json", encoding="utf-8")
        self.expect(Exit.Package.FAILED, manif.load, pkg)

    def test_manifest_must_be_object(self):
        pkg = self.skills / "demo"
        pkg.mkdir(parents=True)
        (pkg / "skill.json").write_text("[]", encoding="utf-8")
        self.expect(Exit.Package.FAILED, manif.load, pkg)

    def test_implicit_files(self):
        pkg = make_package(self.skills, files=["notes.txt"])
        (pkg / "notes.txt").write_text("x", encoding="utf-8")
        self.assertEqual(
            manif.files(pkg, manif.load(pkg)),
            ["SKILL.md", "demo.py", "notes.txt", "skill.json"],
        )

    def test_files_must_be_list(self):
        pkg = make_package(self.skills, manifest={"files": "SKILL.md"})
        self.expect(Exit.Package.FAILED, manif.files, pkg, manif.load(pkg))

    def test_declared_file_missing(self):
        pkg = make_package(self.skills, files=["ghost.txt"])
        self.expect(Exit.Package.FAILED, manif.validate, pkg)

    def test_declared_directory_missing(self):
        pkg = make_package(self.skills, directories=["nope"])
        self.expect(Exit.Package.FAILED, manif.validate, pkg)

    def test_name_traversal_rejected(self):
        make_package(self.skills)
        for bad in ("../demo", "a/b", "..", "."):
            self.expect(Exit.Package.FAILED, manif.packages, self.skills, [bad])

    def test_names_deduped_and_empty_rejected(self):
        make_package(self.skills)
        self.assertEqual(manif.packages(self.skills, ["demo", "demo ", ""]), ["demo"])
        self.expect(Exit.Package.FAILED, manif.packages, self.skills, [])

    def test_runtime_name(self):
        self.assertEqual(manif.runtime_name({"python": {"runtime": {"version": "3.12.1"}}}), "python3.12")
        self.assertEqual(manif.runtime_name({}), "python3.11")


class TransferTests(Base):
    def test_whitelist_only(self):
        pkg = make_package(self.skills)
        (pkg / "data").mkdir()
        (pkg / "data" / "secret.txt").write_text("x", encoding="utf-8")
        (pkg / "src" / "__pycache__").mkdir()
        (pkg / "src" / "__pycache__" / "junk.pyc").write_text("x", encoding="utf-8")
        (pkg / "extra.txt").write_text("x", encoding="utf-8")

        from src import transfer

        dest = paths.skills_dir(self.local)
        transfer.package("demo", self.skills, dest)
        out = dest / "demo"
        for rel in ("SKILL.md", "skill.json", "demo.py", "src/lib.py"):
            self.assertTrue((out / rel).is_file(), rel)
        self.assertFalse((out / "data").exists(), "data/ must never travel")
        self.assertFalse((out / "src" / "__pycache__").exists(), "caches filtered")
        self.assertFalse((out / "extra.txt").exists(), "undeclared file copied")

    def test_unwritable_destination_fails_cleanly(self):
        """A read-only destination is a reported failure, not a traceback."""
        from src import transfer

        make_package(self.skills)
        dest = paths.skills_dir(self.local)
        dest.chmod(0o555)
        try:
            self.expect(Exit.Package.FAILED, transfer.package, "demo", self.skills, dest)
        finally:
            dest.chmod(0o755)

    def test_directory_replaced(self):
        from src import transfer

        make_package(self.skills)
        dest = paths.skills_dir(self.local) / "demo"
        (dest / "src").mkdir(parents=True)
        (dest / "src" / "stale.py").write_text("old", encoding="utf-8")
        transfer.package("demo", self.skills, dest.parent)
        self.assertFalse((dest / "src" / "stale.py").exists())

    def test_missing_declared_file_fails(self):
        from src import transfer

        make_package(self.skills, files=["ghost.txt"])
        self.expect(
            Exit.Package.FAILED, transfer.package, "demo", self.skills,
            paths.skills_dir(self.local),
        )

    def test_same_root_is_noop(self):
        from src import transfer

        make_package(self.skills)
        self.quiet(transfer.batch, ["demo"], self.skills, self.skills, "push")


class InstallTests(Base):
    def test_missing_names(self):
        self.expect(Exit.Install.MISSING_SKILLS, install.run, self.local, [])

    def test_unknown_package(self):
        self.expect(Exit.Install.FAILED, install.run, self.local, ["ghost"])

    def test_unsupported_kind(self):
        from src import transfer

        make_package(self.skills, kind="node")
        transfer.package("demo", self.skills, paths.skills_dir(self.local))
        self.expect(Exit.Install.FAILED, install.run, self.local, ["demo"])

    def test_missing_entry(self):
        # transfer would reject the package, so place it by hand to reach install
        pkg = make_package(self.skills, entry=False)
        import shutil

        shutil.copytree(pkg, paths.skills_dir(self.local) / "demo")
        self.expect(Exit.Install.FAILED, install.run, self.local, ["demo"])

    def test_runtime_missing_falls_back_when_nothing_to_install(self):
        """A fresh checkout has no bundled runtime; the launcher still gets made."""
        from src import transfer

        make_package(self.skills)
        transfer.package("demo", self.skills, paths.skills_dir(self.local))
        install.run(self.local, ["demo"])
        self.assertTrue((self.local / ".agent-tools" / "demo").is_file())

    def test_runtime_missing_with_requirements_fails(self):
        from src import transfer

        make_package(
            self.skills,
            manifest={
                "files": [],
                "directories": ["src"],
                "install": {"kind": "python"},
                "python": {
                    "requirements": ["requests"],
                    "stdlib": [],
                    "runtime": {"version": "3.11.9"},
                },
            },
        )
        transfer.package("demo", self.skills, paths.skills_dir(self.local))
        self.expect(Exit.Install.DEP_FAILED, install.run, self.local, ["demo"])

    def test_launcher_written_and_runs(self):
        from src import transfer

        make_runtime(self.global_root)
        config.set_global_home(self.local, self.global_root)
        make_package(self.skills)
        transfer.package("demo", self.skills, paths.skills_dir(self.local))

        _, out, _ = self.quiet(install.run, self.local, ["demo"])
        self.assertIn("install: demo", out)
        launcher = paths.tools_dir(self.local) / "demo"
        self.assertTrue(os.access(launcher, os.X_OK))
        body = launcher.read_text(encoding="utf-8")
        self.assertIn(str(paths.runtime_root(self.global_root)), body)
        self.assertNotIn("python3 -", body, "launcher must not parse JSON itself")

        done = subprocess.run([str(launcher)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("demo ok", done.stdout)

    def test_install_is_idempotent(self):
        from src import transfer

        make_runtime(self.global_root)
        config.set_global_home(self.local, self.global_root)
        make_package(self.skills)
        transfer.package("demo", self.skills, paths.skills_dir(self.local))
        self.quiet(install.run, self.local, ["demo"])
        launcher = paths.tools_dir(self.local) / "demo"
        first = launcher.read_text(encoding="utf-8")
        self.quiet(install.run, self.local, ["demo"])
        self.assertEqual(first, launcher.read_text(encoding="utf-8"))

    def test_archive_is_unpacked(self):
        from src import transfer

        make_package(self.skills)
        transfer.package("demo", self.skills, paths.skills_dir(self.local))
        prefix = paths.runtime_root(self.global_root) / paths.platform_tag() / "python3.11"
        staging = self.tmp / "stage" / "python3.11" / "bin"
        staging.mkdir(parents=True)
        shim = staging / "python3.11"
        shim.write_text(f'#!/bin/sh\nexec "{PY}" "$@"\n', encoding="utf-8")
        shim.chmod(0o755)
        prefix.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(prefix.parent / "python3.11.gz", "w:gz") as tar:
            tar.add(self.tmp / "stage" / "python3.11", arcname="python3.11")

        config.set_global_home(self.local, self.global_root)
        self.quiet(install.run, self.local, ["demo"])
        self.assertTrue((prefix / "bin" / "python3.11").is_file())


class ConfigTests(Base):
    def test_missing_global_is_error(self):
        self.expect(Exit.Config.MISSING_GLOBAL, config.global_home, self.local)

    def test_seed_self(self):
        self.assertEqual(config.global_home(self.local, seed=True), self.local.resolve())
        self.assertEqual(config.global_home(self.local), self.local.resolve())

    def test_configured_but_missing_global_is_error(self):
        """A typo must fail loudly; seeding would silently rewrite the config."""
        gone = self.tmp / "gone"
        config.set_global_home(self.local, gone)
        self.expect(Exit.Config.MISSING_GLOBAL, config.global_home, self.local, seed=True)
        self.assertEqual(config.read(self.local)["paths"]["global_home"], str(gone))

    def test_inherit_copies_launcher_home(self):
        config.set_global_home(self.global_root, self.global_root)
        config.inherit_global_home(self.global_root, self.local)
        self.assertEqual(config.global_home(self.local), self.global_root.resolve())

    def test_inherit_keeps_own_home(self):
        other = self.tmp / "other"
        third = self.tmp / "third"
        for project in (other, third):
            (project / ".agent-ide" / "skills").mkdir(parents=True)
        config.set_global_home(other, third)
        config.inherit_global_home(self.global_root, other)
        self.assertEqual(config.global_home(other), third.resolve())

    def test_inherit_overwrites_self_reference(self):
        config.set_global_home(self.local, self.local)
        config.inherit_global_home(self.global_root, self.local)
        self.assertEqual(config.global_home(self.local), self.global_root.resolve())

    def test_publish_repo_falls_back_to_global(self):
        config.set_global_home(self.local, self.global_root)
        config.set_global_home(self.global_root, self.global_root)
        cfg = config.read(self.global_root)
        cfg["github"] = {"publish_repo": "owner/repo"}
        config.write(self.global_root, cfg)
        self.assertEqual(config.publish_repo(self.local), "owner/repo")


class InjectTests(Base):
    def test_add_and_remove(self):
        from src import transfer

        make_package(self.skills)
        transfer.package("demo", self.skills, paths.skills_dir(self.local))
        self.quiet(inject.run, self.local, ".cursor", "add-skill", ["demo"])
        link = self.local / ".cursor" / "skills" / "demo" / "SKILL.md"
        self.assertTrue(link.is_symlink())
        self.assertTrue(link.resolve().is_file())

        self.quiet(inject.run, self.local, ".cursor", "remove-skill", ["demo"])
        self.assertFalse((self.local / ".cursor" / "skills" / "demo").exists())

    def test_remove_leaves_unmanaged(self):
        from src import transfer

        make_package(self.skills)
        transfer.package("demo", self.skills, paths.skills_dir(self.local))
        foreign = self.local / ".cursor" / "skills" / "foreign"
        foreign.mkdir(parents=True)
        (foreign / "SKILL.md").write_text("# foreign", encoding="utf-8")
        self.quiet(inject.run, self.local, ".cursor", "remove-skill", [])
        self.assertTrue((foreign / "SKILL.md").is_file())

    def test_domain_outside_project(self):
        self.expect(Exit.Inject.FAILED, inject.run, self.local, "../outside", "add-skill", [])

    def test_canonical_tree_rejected(self):
        self.expect(Exit.Inject.FAILED, inject.run, self.local, ".agent-ide", "add-skill", [])

    def test_unknown_skill(self):
        self.expect(Exit.Inject.FAILED, inject.run, self.local, ".cursor", "add-skill", ["ghost"])

    def test_no_packages(self):
        self.expect(Exit.Inject.FAILED, inject.run, self.local, ".cursor", "add-skill", [])

    def test_unknown_action(self):
        self.expect(Exit.Inject.FAILED, inject.run, self.local, ".cursor", "bogus", [])


class InitTests(Base):
    def test_missing_essential(self):
        config.set_global_home(self.global_root, self.global_root)
        make_package(self.skills, name="contact-user")
        self.expect(Exit.Package.FAILED, init.run, self.global_root, self.local)

    def test_optional_missing_warns_only(self):
        make_runtime(self.global_root)
        make_package(self.skills, name="agent-ide")
        config.set_global_home(self.global_root, self.global_root)
        _, _, err = self.quiet(init.run, self.global_root, self.local)
        self.assertIn("[WARN] init-project", err)
        self.assertTrue((paths.skills_dir(self.local) / "agent-ide").is_dir())
        self.assertTrue((paths.tools_dir(self.local) / "agent-ide").is_file())

    def test_gitignore_seeded_once(self):
        make_runtime(self.global_root)
        make_package(self.skills, name="agent-ide")
        config.set_global_home(self.global_root, self.global_root)
        self.quiet(init.run, self.global_root, self.local)
        first = (self.local / ".gitignore").read_text(encoding="utf-8")
        self.quiet(init.run, self.global_root, self.local)
        self.assertEqual(first, (self.local / ".gitignore").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
