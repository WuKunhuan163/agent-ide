"""The interactive step: get an authorization URL, hand it over, then wait.

The bundled client prints a URL and then waits for Enter; only after Enter does it
ask the server for a token, and if the phone has not confirmed yet it gives up and
exits. So "press Enter" is not a formality — it is a one-shot request whose timing
the user controls, which is exactly why this cannot be a blind `subprocess.run`:

* `LoginClient.start()` spawns the client and lifts the URL out of its output;
* `LoginClient.confirm()` sends the Enter;
* `LoginClient.valid()` reports whether a usable token has landed on disk;
* after a failed confirm the client is dead, so `restart()` is the only way back.

`login_gui` drives those four calls from a window; `terminal_login` does the same
in a terminal for hosts without a display.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import webbrowser
from pathlib import Path

from . import paths
from .errors import PanError

URL_RE = re.compile(r"https://[^\s\"'<>]+")
WANTED = ("openapi.alipan.com", "passport.aliyundrive.com", "auth.alipan.com")
POLL_SECONDS = 10.0


class LoginClient:
    """One run of the login client, and the three questions asked of it."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.config_dir = paths.ensure_agent_dir(agent_id)
        self.env = dict(os.environ, ALIYUNPAN_CONFIG_DIR=str(self.config_dir))
        self.env.pop("PYTHONHOME", None)
        self.env.pop("PYTHONPATH", None)
        self.process = None
        self.master = None
        self.url = ""

    # -------------------------------------------------------------- lifecycle

    def start(self, wait: float = 25.0) -> str:
        binary = _binary()
        self.stop()
        self.url = ""
        if sys.platform == "win32":
            import subprocess

            self.process = subprocess.Popen(
                [str(binary), "login"], env=self.env, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
            self.url = self._read_pipe(wait)
        else:
            import pty
            import select

            master, slave = pty.openpty()
            self.process = _popen([str(binary), "login"], self.env, slave)
            os.close(slave)
            self.master = master
            self.url = self._read_pty(select, wait)
        if not self.url:
            self.stop()
            raise PanError("the login client printed no authorization url")
        return self.url

    def confirm(self) -> None:
        """Send the Enter that makes the client fetch the token."""
        if self.process is None or self.process.poll() is not None:
            raise PanError("the login client is no longer running")
        try:
            if self.master is not None:
                os.write(self.master, b"\n")
            elif self.process.stdin:
                self.process.stdin.write("\n")
                self.process.stdin.flush()
        except OSError as exc:
            raise PanError(f"cannot answer the login client: {exc}")

    def restart(self) -> str:
        self.stop()
        return self.start()

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                pass
        if self.master is not None:
            try:
                os.close(self.master)
            except OSError:
                pass
            self.master = None
        self.process = None

    # ----------------------------------------------------------------- state

    def valid(self) -> bool:
        return token_valid(self.config_dir)

    def open_browser(self) -> None:
        if self.url:
            webbrowser.open(self.url)

    # ---------------------------------------------------------------- output

    def _read_pty(self, select, wait: float) -> str:
        import time as _time

        deadline = _time.monotonic() + wait
        buffer = ""
        while _time.monotonic() < deadline:
            ready, _, _ = select.select([self.master], [], [], 0.5)
            if ready:
                try:
                    chunk = os.read(self.master, 4096).decode("utf-8", "replace")
                except OSError:
                    break
                buffer += chunk
                url = _extract(buffer)
                if url:
                    return url
            elif self.process and self.process.poll() is not None:
                break
        return ""

    def _read_pipe(self, wait: float) -> str:
        deadline = time.monotonic() + wait
        buffer = ""
        while time.monotonic() < deadline:
            line = self.process.stdout.readline() if self.process.stdout else ""
            if not line:
                break
            buffer += line
            url = _extract(buffer)
            if url:
                return url
        return ""


# -------------------------------------------------------------------- entry


GUI_CODE = "import sys; from src.login_gui import run_gui; sys.exit(0 if run_gui(sys.argv[1]) else 1)"
GUI_ATTEMPTS = 3


def _gui_executable(agent_id: str) -> str:
    """The generated `.app` bundle when it can be built, so the Dock shows the id
    and the skill icon instead of a bare Python interpreter."""
    try:
        from .app_bundle import ensure_agent_app

        bundle = ensure_agent_app(agent_id)
    except (OSError, RuntimeError, ImportError):
        bundle = None
    return str(bundle) if bundle is not None else sys.executable


def login(agent_id: str, *, terminal: bool = False) -> dict:
    """Open the window; fall back to the terminal when there is no display."""
    if terminal:
        return terminal_login(agent_id)

    import subprocess

    exe = _gui_executable(agent_id)
    error = ""
    for _ in range(GUI_ATTEMPTS):
        try:
            proc = subprocess.run(
                [exe, "-c", GUI_CODE, agent_id],
                cwd=str(paths.SKILL_DIR),
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            error = str(exc)
            time.sleep(0.5)
            continue
        if token_valid(paths.agent_dir(agent_id)):
            return {"id": agent_id, "config": str(paths.config_path(agent_id)), "ok": True}
        error = (proc.stderr or "").strip()
        if "TclError" in error or "no display" in error:
            return terminal_login(agent_id)
        if proc.returncode in (0, 1):     # closed cleanly, or the user cancelled
            raise PanError("login cancelled; run it again when you are ready")
        time.sleep(0.5)
    raise PanError(f"the login window could not start: {error or 'unknown error'}")


# ------------------------------------------------------------------ terminal


def terminal_login(agent_id: str) -> dict:
    """No display: print the URL, wait for one line, then poll for the token."""
    client = LoginClient(agent_id)
    try:
        url = client.start()
        print(f"在浏览器打开下面的地址并完成授权：\n{url}\n", file=sys.stderr)
        try:
            client.open_browser()
        except Exception:
            pass
        print("授权完成后回到这里按 Enter 继续 > ", end="", file=sys.stderr, flush=True)
        try:
            sys.stdin.readline()
        except Exception:
            pass
        client.confirm()
        if _await_token(client):
            return {"id": agent_id, "config": str(paths.config_path(agent_id)), "ok": True}
        raise PanError(
            "no token yet; run login again and press Enter after the browser step is finished"
        )
    finally:
        client.stop()


def _await_token(client: LoginClient, seconds: float = POLL_SECONDS) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if client.valid():
            return True
        if client.process is not None and client.process.poll() is not None:
            # The client writes the file just before exiting: one last look.
            time.sleep(0.5)
            return client.valid()
        time.sleep(0.2)
    return client.valid()


# -------------------------------------------------------------------- shared


def token_valid(config_dir: Path) -> bool:
    try:
        data = json.loads((Path(config_dir) / "config.json").read_text(encoding="utf-8"))
        users = data.get("userList") or []
        token = (users[0].get("openapiToken") or {}) if users else {}
        return bool(token.get("accessToken")) and int(token.get("expired") or 0) > int(time.time())
    except (OSError, json.JSONDecodeError, IndexError, ValueError):
        return False


def _extract(text: str) -> str:
    for match in URL_RE.finditer(text):
        url = match.group(0).rstrip(").,;")
        if any(host in url for host in WANTED):
            return url
    return ""


def _binary() -> Path:
    try:
        return paths.binary_path()
    except FileNotFoundError as exc:
        raise PanError(str(exc))


def _popen(argv, env, slave):
    import subprocess

    return subprocess.Popen(argv, env=env, stdin=slave, stdout=slave, stderr=slave, close_fds=True)
