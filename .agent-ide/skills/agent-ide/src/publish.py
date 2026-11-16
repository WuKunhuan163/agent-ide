"""Two steps in one command: this project to the global tree, then the global tree to GitHub.

Step one exists because reading only the global tree published the older global shape of a package
edited here, with the command exiting 0. Step two is a shallow clone in a temporary directory: the
whitelisted packages are copied in, committed, and pushed. `--from-github` reverses step two — the
clone is the source and the global project is the destination — and leaves this project alone.

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

        _carry_from_project(project_root, names, global_skills)
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


def _carry_from_project(project_root: Path, names: list[str], global_skills: Path) -> None:
    """Step one of two: this project's copy goes to the global tree before anything is published.

    `publish` used to read only the global tree, so a package edited here and never pushed was
    published in its older global shape, with the command exiting 0. The two steps are now one
    command: whatever this project holds under the named packages travels to the global tree
    first, and only then is the global tree copied into the clone.

    A name that exists only in the global tree is left alone -- that is a package this project
    never edited, not a mistake -- and a project with no skills directory at all is publishing
    for a global tree it does not own, which is what `--from-github` is for.
    """
    project_skills = paths.skills_dir(project_root)
    if not project_skills.is_dir():
        return
    owned = [n for n in names if (project_skills / n).is_dir()]
    if not owned:
        return
    transfer.batch(owned, project_skills, global_skills, "push")


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
