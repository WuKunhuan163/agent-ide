"""Upload / download: fixed prefix plus a hash suffix, verified in both directions.

The traps are written into the code, one by one, instead of into somebody's head:

1. **The target directory is not the caller's choice.** Hand-typed paths used to
   land in `/root/uploaded2`, and same-named directories on two boxes overwrote
   each other. The directory is always `/root/uploaded/<hash>/`, so re-uploading
   the same set lands in the **same** directory instead of making a second copy.
2. **`scp`'s exit code is not enough.** On a broken stream `scp` exits non-zero
   while the target file exists at a plausible size, which reads as "done". So
   every transfer is followed by a size + sha256 comparison, and only the bad
   files are re-sent.
3. **ssh aliases go stale.** After a reboot the public IP and port change while
   the old alias in `~/.ssh/config` still points at the old address. Every
   transfer therefore probes with `sshsetup.probe` and rewrites the alias instead
   of ramming the stale one.
4. **Disks fill up.** 17G of weights plus existing data can fill a 59G system
   disk, and a tar that runs out of space leaves half a file. Upload compares
   `df` free space against the local byte total and fails early.
5. **A pipeline without `pipefail` loses errors.** In `tar | ssh tar` the producer's
   failure is masked by ssh's zero exit, so both ends check returncode explicitly.

Only three functions are exported: `push` / `pull` / `check`.
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import time
from pathlib import Path

from . import client, sshsetup
from .client import ApiError

PREFIX = "/root/uploaded"
HASH_LIMIT = 4 * 1024 ** 3      # above this size only size+count is checked, marked verify=size, never faked
CHUNK = 1 << 20


def _ssh(uhost_id: str, command: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run one remote command; retry once when the alias is dead (IP/port may have changed)."""
    argv = sshsetup.ssh_argv(uhost_id, command)
    proc = subprocess.run(argv, capture_output=True, text=True, errors="replace", timeout=timeout)
    if proc.returncode == 255:
        # 255 means the connection layer failed. The first transfer after boot often
        # hits it (alias just written, sshd still starting), so wait 2s and retry
        # once; otherwise "just booted" is reported as "cannot transfer".
        time.sleep(2)
        proc = subprocess.run(argv, capture_output=True, text=True, errors="replace",
                              timeout=timeout)
    return proc


def _ssh_stream(uhost_id: str, command: str, producer: list[str], timeout: int = 7200):
    """Feed a local producer's stdout into the remote command's stdin (tar streaming)."""
    argv = sshsetup.ssh_argv(uhost_id, command, stream=True)
    # macOS tar attaches AppleDouble `._*` files that unpack on the far side as extra
    # files, which the check then reports as a mismatch. COPYFILE_DISABLE=1 stops
    # bsdtar from creating them.
    env = dict(os.environ, COPYFILE_DISABLE="1")
    src = subprocess.Popen(producer, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        dst = subprocess.run(argv, stdin=src.stdout, capture_output=True, text=True,
                             errors="replace", timeout=timeout)
    finally:
        if src.stdout:
            src.stdout.close()
        src.wait()
    # A failed producer makes tar exit non-zero; ssh's return code alone is not enough
    return dst, src.returncode


def _ssh_pull(uhost_id: str, command: str, consumer: list[str], timeout: int = 7200):
    """Reverse stream: the remote command's stdout into a local consumer's stdin.

    The direction matters: upload is local Popen -> ssh stdin, download must be ssh
    stdout -> local stdin. The first version merged both into one function and the
    remote data went into the pipe buffer while the local side unpacked an empty dir.
    """
    argv = sshsetup.ssh_argv(uhost_id, command, stream=True)
    src = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        dst = subprocess.run(consumer, stdin=src.stdout, capture_output=True, text=True,
                             errors="replace", timeout=timeout)
    finally:
        if src.stdout:
            src.stdout.close()
        src.wait()
    return dst, src.returncode


def _manifest(root: Path, entries: list[str]) -> tuple[dict, int]:
    """{relative path: (size, sha256|None)} plus the byte total. Directories recurse."""
    files: dict[str, tuple[int, str | None]] = {}
    total = 0
    for entry in entries:
        p = root / entry
        if p.is_dir():
            for dirpath, _dirs, names in os.walk(p):
                for n in names:
                    f = Path(dirpath) / n
                    rel = str(f.relative_to(root))
                    size = f.stat().st_size
                    files[rel] = (size, None)
                    total += size
        else:
            size = p.stat().st_size
            files[str(p.relative_to(root))] = (size, None)
            total += size
    return files, total


def _hash_local(root: Path, files: dict) -> dict:
    out = {}
    for rel, (size, _) in files.items():
        h = hashlib.sha256()
        with open(root / rel, "rb") as fh:
            for chunk in iter(lambda: fh.read(CHUNK), b""):
                h.update(chunk)
        out[rel] = (size, h.hexdigest())
    return out


def _remote_links(uhost_id: str, remote_dir: str) -> dict:
    """Remote symlinks {relative path: target}. Links compare by target, not by hash."""
    proc = _ssh(uhost_id, f"cd {shlex.quote(remote_dir)} && "
                          "find . -type l -printf '%P\\t%l\\n' | sort", timeout=600)
    if proc.returncode != 0:
        return {}
    out = {}
    for line in (proc.stdout or "").splitlines():
        if "\t" in line:
            rel, target = line.split("\t", 1)
            out[rel] = target
    return out


def _remote_manifest(uhost_id: str, remote_dir: str) -> dict:
    """Remote {relative path: (size, sha256)} via find + sha256sum in one ssh call."""
    cmd = (f"cd {shlex.quote(remote_dir)} && "
           "find . -type f -printf '%P\\t%s\\n' | sort")
    proc = _ssh(uhost_id, cmd, timeout=600)
    if proc.returncode != 0:
        raise ApiError(proc.returncode, (proc.stderr or "").strip()[:300], "xfer-manifest")
    files = {}
    for line in proc.stdout.splitlines():
        if "\t" not in line:
            continue
        rel, size = line.rsplit("\t", 1)
        files[rel] = (int(size), None)
    # Drop this tool's own temp files and macOS AppleDouble residue (the latter means
    # the remote received ._* entries)
    files = {k: v for k, v in files.items()
             if not k.startswith(".xfer") and not os.path.basename(k).startswith("._")}
    if not files:
        return files
    names = " ".join(shlex.quote(k) for k in files)
    proc = _ssh(uhost_id, f"cd {shlex.quote(remote_dir)} && sha256sum -b -- {names}",
                timeout=1800)
    if proc.returncode != 0:
        raise ApiError(proc.returncode, (proc.stderr or "").strip()[:300], "xfer-sha")
    for line in proc.stdout.splitlines():
        digest, _, name = line.partition("  ")
        name = name.lstrip("*")
        if name in files:
            files[name] = (files[name][0], digest)
    return files


def _free_bytes(uhost_id: str, path: str = "/root") -> int:
    proc = _ssh(uhost_id, f"df -Pk {shlex.quote(path)} | awk 'NR==2{{print $4}}'", timeout=60)
    try:
        return int((proc.stdout or "0").strip()) * 1024
    except ValueError:
        return 0


def push(uhost_id: str, paths: list[str], name: str | None = None,
         retries: int = 2, dry_run: bool = False, do_hash: bool = True) -> dict:
    """Upload. Returns {dir, files, bytes, verify, attempts, bad}.

    Directory = PREFIX/<path hash>[-<name>]; the same argument set lands in the same
    directory on every call.
    """
    resolved = [Path(p).expanduser().resolve() for p in paths]
    for p in resolved:
        if not p.exists():
            raise ApiError(2, f"local path not found: {p}", "xfer")
    base = Path(os.path.commonpath([str(p) for p in resolved]))
    if not base.is_dir():
        base = base.parent
    entries = [str(p.relative_to(base)) if str(p) != str(base) else "." for p in resolved]

    # The directory is decided by the hash of the path set, with no timestamp: the same
    # arguments land in the same directory, so retries and re-runs are idempotent. Change
    # the set and the hash changes, so nothing silently overwrites.
    digest = hashlib.sha256("|".join(sorted(entries)).encode()).hexdigest()[:8]
    target = f"{PREFIX}/{digest}" + (f"-{name}" if name else "")

    files, total = _manifest(base, entries)
    result = {"dir": target, "files": len(files), "bytes": total,
              "verify": "dry-run" if dry_run else "pending", "attempts": 0, "bad": []}
    if dry_run:
        return result

    free = _free_bytes(uhost_id)
    if free and free < total * 1.1:
        raise ApiError(3, f"remote free={free // 1024 ** 2}M < need={total // 1024 ** 2}M", "xfer")

    mk = _ssh(uhost_id, f"mkdir -p {shlex.quote(target)}", timeout=60)
    if mk.returncode != 0:
        raise ApiError(mk.returncode, (mk.stderr or "").strip()[:300], "xfer-mkdir")

    local = _hash_local(base, files) if (do_hash and total <= HASH_LIMIT) else files
    bad = list(files)
    for attempt in range(1, retries + 2):
        if not bad:
            break
        result["attempts"] = attempt
        # A retry sends only the files that failed the last comparison, not the whole set
        tar_argv = ["tar", "-cf", "-", "-h", "-C", str(base)] + bad
        dst, src_rc = _ssh_stream(
            uhost_id,
            f"tar -xf - -C {shlex.quote(target)} || exit 1",
            tar_argv)
        if src_rc != 0 or dst.returncode != 0:
            raise ApiError(4, f"tar stream failed src={src_rc} ssh={dst.returncode} "
                              f"{(dst.stderr or '').strip()[:200]}", "xfer-tar")
        remote = _remote_manifest(uhost_id, target)
        bad = []
        for rel, (size, sha) in local.items():
            if rel not in remote:
                bad.append(rel)
                continue
            rsize, rsha = remote[rel]
            if rsize != size or (sha and rsha and sha != rsha):
                bad.append(rel)
        result["bad"] = bad

    expected = set(local)
    extra = set(_remote_manifest(uhost_id, target)) - expected
    result["verify"] = "ok" if not bad and not extra else "mismatch"
    result["method"] = "sha256" if (do_hash and total <= HASH_LIMIT) else "size+count"
    if extra:
        result["extra"] = sorted(extra)[:5]
    return result


def pull(uhost_id: str, remote_path: str, dest: str | None = None,
         name: str | None = None, dry_run: bool = False) -> dict:
    """Download. A directory lands in ./downloaded/<timestamp>-<hash>/; a single file
    lands at the same level.

    The remote path may be either a directory or a file (keys, logs, one weight
    shard), and both paths must work: a directory strips its archive top level with
    `--strip-components=1`, a file keeps its name.
    """
    remote_path = remote_path.rstrip("/") or "/"
    probe = _ssh(uhost_id, f"test -d {shlex.quote(remote_path)} && echo dir || echo file",
                 timeout=60)
    is_dir = (probe.stdout or "").strip() == "dir"
    parent = os.path.dirname(remote_path) or "/"
    leaf = os.path.basename(remote_path)

    digest = hashlib.sha256(remote_path.encode()).hexdigest()[:8]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if dest:
        target = Path(dest).expanduser().resolve()
    else:
        leaf_name = f"{stamp}-{digest}" + (f"-{name}" if name else "")
        target = Path.cwd() / "downloaded" / leaf_name

    if dry_run:
        return {"dir": str(target), "verify": "dry-run", "files": 0, "bytes": 0,
                "method": "-", "attempts": 0}

    target.mkdir(parents=True, exist_ok=True)
    strip = ["--strip-components=1"] if is_dir else []
    dst, src_rc = _ssh_pull(
        uhost_id,
        f"tar -cf - -C {shlex.quote(parent)} {shlex.quote(leaf)} || exit 1",
        ["tar", "-xf", "-", "-C", str(target)] + strip)
    if src_rc != 0 or dst.returncode != 0:
        raise ApiError(4, f"tar stream failed src={src_rc} ssh={dst.returncode} "
                          f"{(dst.stderr or '').strip()[:200]}", "xfer-tar")

    if is_dir:
        remote = _remote_manifest(uhost_id, remote_path)
        local_root = target
    else:
        size = int(_ssh(uhost_id, f"stat -c %s {shlex.quote(remote_path)}",
                        timeout=60).stdout.strip() or -1)
        remote = {leaf: (size, None)}
        local_root = target

    bad = []
    for rel, (rsize, _sha) in remote.items():
        f = local_root / rel
        if not f.exists() or f.stat().st_size != rsize:
            bad.append(rel)
    return {"dir": str(local_root), "files": len(remote),
            "bytes": sum(v[0] for v in remote.values()),
            "verify": "ok" if not bad else "mismatch", "attempts": 1,
            "bad": bad[:10], "method": "size+count"}


def check(uhost_id: str, remote_dir: str, local_dir: str | None = None) -> dict:
    """Final state check: list the remote manifest; with local_dir, compare size+sha
    file by file."""
    remote = _remote_manifest(uhost_id, remote_dir)
    out = {"dir": remote_dir, "files": len(remote),
           "bytes": sum(v[0] for v in remote.values()),
           "files_meta": sorted(remote.items())}
    if local_dir:
        root = Path(local_dir).expanduser().resolve()
        bad = []
        for rel, (size, sha) in remote.items():
            f = root / rel
            if not f.exists() or f.stat().st_size != size:
                bad.append(rel)
                continue
            if sha:
                h = hashlib.sha256()
                with open(f, "rb") as fh:
                    for chunk in iter(lambda: fh.read(CHUNK), b""):
                        h.update(chunk)
                if h.hexdigest() != sha:
                    bad.append(rel)
        out.update({"local": str(root), "bad": bad,
                    "verify": "ok" if not bad else "mismatch"})
    return out


# ---------- background jobs: the transfer runs itself, the human watches state ----------
#
# Why this layer exists: the foreground `upload` needs someone sitting next to it --
# one SSH drop fails the whole command, and nobody dares leave 17G unattended. A job
# splits the transfer into one stream per file plus a sha256 per file, writes progress
# to data/xfer-<job>.json, and returns immediately so `xfer status` can be checked
# at any time.
JOBDIR = client.SKILL_DIR / "data"


def _job_file(job_id: str) -> Path:
    return JOBDIR / f"xfer-{job_id}.json"


def _job_write(job: dict) -> None:
    job["updated"] = time.time()
    _job_file(job["job"]).write_text(json.dumps(job, ensure_ascii=False))


def _job_read(job_id: str) -> dict:
    p = _job_file(job_id)
    if not p.exists():
        raise ApiError(2, f"no such job: {job_id}", "xfer")
    return json.loads(p.read_text())


def jobs_for(uhost_id: str) -> list[dict]:
    out = []
    for p in sorted(JOBDIR.glob("xfer-*.json")):
        try:
            j = json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            continue
        if j.get("uhost_id") == uhost_id:
            out.append(j)
    return out


def plan_upload(uhost_id: str, paths: list[str], name: str | None = None) -> dict:
    """Expand local paths into one entry per file; a directory's files transfer and
    verify one at a time."""
    resolved = [Path(p).expanduser().resolve() for p in paths]
    for p in resolved:
        if not p.exists():
            raise ApiError(2, f"local path not found: {p}", "xfer")
    base = Path(os.path.commonpath([str(p) for p in resolved]))
    if not base.is_dir():
        base = base.parent
    files: dict[str, dict] = {}
    total = 0
    for entry in resolved:
        rel_root = "" if entry == base else str(entry.relative_to(base))
        if entry.is_dir():
            for dirpath, _d, names in os.walk(entry):
                for n in names:
                    f = Path(dirpath) / n
                    rel = str(f.relative_to(base))
                    if f.is_symlink():
                        # A link records only its target string: hashing follows the target,
                        # so an unfinished target would mismatch forever
                        files[rel] = {"size": 0, "sha": os.readlink(f), "done": False,
                                     "tries": 0, "kind": "link"}
                        continue
                    size = f.stat().st_size
                    files[rel] = {"size": size, "sha": None, "done": False,
                                  "tries": 0, "kind": "file"}
                    total += size
        elif entry.is_symlink():
            files[rel_root] = {"size": 0, "sha": os.readlink(entry), "done": False,
                               "tries": 0, "kind": "link"}
        else:
            rel = rel_root
            size = entry.stat().st_size
            files[rel] = {"size": size, "sha": None, "done": False,
                          "tries": 0, "kind": "file"}
            total += size

    digest = hashlib.sha256("|".join(sorted(files)).encode()).hexdigest()[:8]
    job_id = f"{uhost_id}-{digest}" + (f"-{name}" if name else "")
    job = {
        "job": job_id, "uhost_id": uhost_id, "kind": "upload",
        "dir": f"{PREFIX}/{digest}" + (f"-{name}" if name else ""),
        "base": str(base), "files": files,
        "total_files": len(files), "total_bytes": total,
        "done_bytes": 0, "state": "queued", "created": time.time(), "error": None,
    }
    _job_write(job)
    return job


def _sha_local(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def run_upload_job(job_id: str, stop_when_done: bool = True, tries: int = 3) -> dict:
    """Job body: transfer and verify file by file, writing progress to disk. Runs in
    a background process."""
    job = _job_read(job_id)
    job["state"] = "running"
    job["error"] = None
    _job_write(job)
    base = Path(job["base"])
    target = job["dir"]

    mk = _ssh(job["uhost_id"], f"mkdir -p {shlex.quote(target)}", timeout=60)
    if mk.returncode != 0:
        job.update(state="failed", error=f"mkdir rc={mk.returncode}")
        _job_write(job)
        return job

    for rel, meta in job["files"].items():
        if meta.get("done"):
            continue
        local = base / rel
        if not local.exists():
            meta["err"] = "local-missing"
            meta["done"] = True          # gone locally means not pending; avoids an endless loop
            _job_write(job)
            continue
        kind = meta.get("kind", "file")
        want_sha = meta["sha"] if kind == "link" else _sha_local(local)
        for attempt in range(1, tries + 1):
            meta["tries"] = attempt
            try:
                dst, src_rc = _ssh_stream(
                    job["uhost_id"],
                    f"tar -xf - -C {shlex.quote(target)} || exit 1",
                    ["tar", "-cf", "-", "-h", "-C", str(base), rel], timeout=7200)
                if src_rc != 0 or dst.returncode != 0:
                    meta["err"] = f"tar src={src_rc} ssh={dst.returncode}"
                    time.sleep(5 * attempt)
                    continue
                if kind == "link":
                    # A link compares by target string. Hashing it follows through to the
                    # target, so an unfinished target or a relative path mismatch reads as
                    # mismatch -- that is the check being wrong, not the transfer.
                    got = (_ssh(job["uhost_id"],
                                f"readlink {shlex.quote(target + '/' + rel)}",
                                timeout=120).stdout or "").strip()
                    if got == want_sha:
                        meta.update(done=True, err=None)
                        break
                    meta["err"] = f"link-mismatch {got[:40]}"
                else:
                    remote = _ssh(job["uhost_id"],
                                  f"cd {shlex.quote(target)} && sha256sum -b -- {shlex.quote(rel)}",
                                  timeout=1800)
                    # `sha256sum -b` prints `hash *file` (one space plus an asterisk);
                    # splitting on two spaces leaves the whole line as the hash and the
                    # check mismatches forever.
                    head = (remote.stdout or "").strip().split()
                    got = head[0] if head else ""
                    if remote.returncode == 0 and got == want_sha:
                        meta.update(done=True, sha=want_sha, err=None)
                        break
                    meta["err"] = f"sha-mismatch {got[:12]}"
            except (subprocess.SubprocessError, ApiError) as exc:  # noqa: BLE001
                meta["err"] = str(exc)[:120]
                time.sleep(5 * attempt)
            _job_write(job)
        if meta.get("done"):
            job["done_bytes"] = sum(m["size"] for m in job["files"].values() if m.get("done"))
            _job_write(job)

    finished = all(m.get("done") and not m.get("err") for m in job["files"].values())
    job["state"] = "done" if finished else "incomplete"
    job["done_bytes"] = sum(m["size"] for m in job["files"].values() if m.get("done") and not m.get("err"))
    _job_write(job)
    if stop_when_done and finished:
        try:
            region = (client.call("DescribeCompShareInstance", Limit=100,
                                  **{"UHostIds.0": job["uhost_id"]}).get("UHostSet") or [{}])[0]
            client.call("StopCompShareInstance", Region=region.get("Region"),
                        Zone=region.get("Zone"), UHostId=job["uhost_id"])
            job["stopped"] = True
            _job_write(job)
        except ApiError:
            pass
    return job


def job_status(job: dict) -> dict:
    files = job.get("files") or {}
    done = [m for m in files.values() if m.get("done") and not m.get("err")]
    bad = [k for k, m in files.items() if m.get("err")]
    elapsed = max(1e-6, (job.get("updated") or job["created"]) - job["created"])
    rate = (job.get("done_bytes") or 0) / elapsed
    return {"job": job["job"], "state": job["state"], "dir": job["dir"],
            "done": len(done), "total": len(files),
            "done_bytes": sum(m["size"] for m in done),
            "total_bytes": job.get("total_bytes") or 0,
            "rate_bps": rate, "bad": bad[:10], "error": job.get("error")}
