"""Turn SSH into an object: one local alias plus a private key carried in-package.

Motivation: the caller (agent) used to dig the password out of
data/instance-*.json and assemble sshpass -p "$PW" ssh -o ... root@IP, which is
long, brittle, and puts the password in the process table. Here the password
becomes a key and IP/port/user become a Host alias, leaving the caller one name.

Three constraints:
1. The private key lives only under this skill's data/, mode 600, never in
   ~/.ssh where it would pollute other tools.
2. ~/.ssh/config gets one marked block; not a byte outside it is touched.
3. Authorization is append semantics (deduplicated append); existing remote
   authorized_keys are left alone.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
KEY_PATH = DATA / "id_ed25519"
PUB_PATH = DATA / "id_ed25519.pub"
SSH_DIR = Path.home() / ".ssh"
SSH_CONFIG = SSH_DIR / "config"
MARK_BEGIN = "# >>> compshare (managed) >>>"
MARK_END = "# <<< compshare (managed) <<<"
KEY_COMMENT = "compshare@skill"


def alias_for(uhost_id: str) -> str:
    """Host alias. The prefix makes it obvious in `ssh <TAB>` which skill owns it."""
    return f"cs-{uhost_id}"


def ensure_key() -> tuple[Path, str]:
    """Generate if absent, returning (private key path, public key text). An existing
    key is returned unchanged."""
    DATA.mkdir(parents=True, exist_ok=True)
    if not KEY_PATH.exists():
        ssh_keygen = shutil.which("ssh-keygen")
        if not ssh_keygen:
            raise RuntimeError("ssh-keygen not found")
        KEY_PATH.unlink(missing_ok=True)
        subprocess.run(
            [ssh_keygen, "-t", "ed25519", "-N", "", "-C", KEY_COMMENT, "-f", str(KEY_PATH)],
            check=True, capture_output=True, text=True, errors="replace",
        )
    os.chmod(KEY_PATH, 0o600)
    pub = PUB_PATH.read_text(encoding="utf-8").strip()
    return KEY_PATH, pub


def authorize(pub: str, run_password) -> tuple[bool, str]:
    """Append the public key to the remote root's authorized_keys.

    run_password is a callable(command) -> CompletedProcess executed over the
    password channel, so this module never needs to know where the password comes
    from. Returns (installed, note).
    """
    marker = pub.split()[-1]
    script = (
        "set -e; mkdir -p ~/.ssh; chmod 700 ~/.ssh; touch ~/.ssh/authorized_keys; "
        f"grep -q '{marker}' ~/.ssh/authorized_keys || "
        f"echo '{pub}' >> ~/.ssh/authorized_keys; "
        "chmod 600 ~/.ssh/authorized_keys; grep -c . ~/.ssh/authorized_keys"
    )
    proc = run_password(script)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "authorize failed").strip()[:200]
    return True, f"authorized ({proc.stdout.strip().splitlines()[-1]} keys on host)"


def write_alias(uhost_id: str, host: str, port: int, user: str) -> Path:
    """Write one Host into the managed block of ~/.ssh/config. Nothing outside it
    is touched."""
    SSH_DIR.mkdir(mode=0o700, exist_ok=True)
    block_body = (
        f"Host {alias_for(uhost_id)}\n"
        f"    HostName {host}\n"
        f"    Port {port}\n"
        f"    User {user}\n"
        f'    IdentityFile "{KEY_PATH}"\n'
        "    IdentitiesOnly yes\n"
        "    StrictHostKeyChecking accept-new\n"
    )
    text = SSH_CONFIG.read_text(encoding="utf-8") if SSH_CONFIG.exists() else ""
    pattern = re.compile(re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END) + r"\n?", re.S)
    match = pattern.search(text)
    entries = ""
    if match:
        # Keep the other instances' entries in the block; replace only the Host
        # section carrying the same alias.
        old = match.group(0)
        body = old.split(MARK_BEGIN, 1)[1].split(MARK_END, 1)[0]
        chunks = re.split(r"(?m)^(?=Host )", body)
        kept = [c for c in chunks if c.strip() and not c.lstrip().startswith(f"Host {alias_for(uhost_id)}\n")]
        entries = "".join(kept)
        text = text[: match.start()] + text[match.end():]
    new_block = f"{MARK_BEGIN}\n{entries}{block_body}{MARK_END}\n"
    text = text.rstrip("\n") + ("\n\n" if text.strip() else "") + new_block
    SSH_CONFIG.write_text(text, encoding="utf-8")
    os.chmod(SSH_CONFIG, 0o600)
    return SSH_CONFIG


def ssh_argv(uhost_id: str, command: str | None, interactive: bool = False,
             stream: bool = False) -> list[str]:
    """Prefer the alias (read from ~/.ssh/config); point at the key directly only
    when the alias does not exist."""
    base = ["ssh", "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=10"]
    if interactive:
        base.append("-t")
    elif not stream:
        base.append("-n")          # the remote command must not read local stdin, or a background run hangs
    # with stream=True the remote has to read stdin (tar streaming); otherwise the data is lost
    argv = base + [alias_for(uhost_id)]
    if command:
        argv.append(command)
    return argv


def probe(uhost_id: str) -> tuple[bool, str]:
    """Skip the password entirely: one `true` hop with the key only."""
    try:
        proc = subprocess.run(ssh_argv(uhost_id, "true"), capture_output=True, text=True, errors="replace", timeout=20)
    except subprocess.SubprocessError as exc:
        return False, str(exc)[:200]
    if proc.returncode == 0:
        return True, "ok"
    return False, (proc.stderr or "failed").strip().splitlines()[-1][:200]
