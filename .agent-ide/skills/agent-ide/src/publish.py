"""Publishing the global whitelist to GitHub, or fetching it back.

The remote is a shallow clone in a temporary directory: the whitelisted packages
are copied in, committed, and pushed. `--from-github` reverses it — the clone is
the source and the global project is the destination.

`github.publish_repo` is either `owner/repo` (GitHub over SSH) or a git URL or
path, which is what makes the mechanism testable without a network.
"""
from __future__ import annotations
import subprocess
import tempfile
from pathlib import Path

from . import config, paths, transfer
from .errors import Exit, fail

IDENTITY = ("-c", "user.name=agent-ide", "-c", "user.email=agent-ide@localhost")


def run(project_root: Path, names: list[str], *, from_github: bool) -> None:
    repo = config.publish_repo(project_root)
    if not repo:
        looked = "\n".join(f"  {p}" for p in config.publish_repo_sources(project_root))
        raise fail(
            Exit.Publish.FAILED,
            "publish: no github.publish_repo in any config this project reads.\n"
            f"Looked in:\n{looked}\n"
            'Add {"github": {"publish_repo": "owner/repo"}} to the first of those, '
            "and `publish` needs nothing else: the clone, the copy, the commit and "
            "the push are all derived from that one string.",
        )
    if not names:
        raise fail(Exit.Publish.FAILED, "publish: pass at least one skill name")

    home = config.global_home(project_root, seed=False)
    global_skills = paths.skills_dir(home)

    with tempfile.TemporaryDirectory(prefix="agent-ide-publish-") as tmp:
        clone = Path(tmp)
        _clone(_remote(repo), clone)
        skills_in_repo = clone / paths.IDE_DIR / "skills"

        if from_github:
            if not skills_in_repo.is_dir():
                raise fail(
                    Exit.Publish.FAILED,
                    f"publish --from-github: {repo} has no {paths.IDE_DIR}/skills directory",
                )
            transfer.batch(names, skills_in_repo, global_skills, "publish --from-github")
            return

        transfer.batch(names, global_skills, skills_in_repo, "publish")
        summary = " ".join(names)
        if _git("add", "-A", cwd=clone).returncode != 0:
            raise fail(Exit.Publish.FAILED, "publish: git add failed in the clone")
        if not _git("status", "--porcelain", cwd=clone).stdout.strip():
            print(f"publish: up to date ({summary})")
            return
        commit = _git("commit", "-m", f"agent-ide publish: {summary}", cwd=clone)
        if commit.returncode != 0:
            raise fail(Exit.Publish.FAILED, f"publish: git commit failed: {_tail(commit)}")
        push = _git("push", "origin", "HEAD", cwd=clone)
        if push.returncode != 0:
            raise fail(
                Exit.Publish.FAILED,
                f"publish: git push failed: {_tail(push)}\n"
                "If the remote moved, re-run, or fetch it with --from-github first.",
            )
        head = _git("rev-parse", "--short", "HEAD", cwd=clone).stdout.strip()
        print(f"publish: {summary} -> {repo} ({head})")


def _remote(repo: str) -> str:
    """`owner/repo` becomes `git@github.com:owner/repo.git`; anything else is used as-is."""
    raw = repo.strip()
    if raw.startswith(("/", "./", "../", "~")) or "://" in raw or "@" in raw:
        return raw
    return f"git@github.com:{raw}.git"


def _clone(remote: str, into: Path) -> None:
    done = _git("clone", "--depth", "1", remote, str(into), cwd=into.parent)
    if done.returncode != 0:
        raise fail(Exit.Publish.FAILED, f"git clone {remote} failed: {_tail(done)}")


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *IDENTITY, *args], cwd=cwd, capture_output=True, text=True)


def _tail(done: subprocess.CompletedProcess) -> str:
    """The last few lines: the remote's own reason often precedes git's summary."""
    lines = (done.stderr or done.stdout or "").strip().splitlines()
    return " / ".join(lines[-3:]) if lines else f"exit {done.returncode}"
