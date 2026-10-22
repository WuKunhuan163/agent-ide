"""The login window: one client process, two buttons, and a state machine.

The client prints an authorization URL and then sits waiting for Enter. So the user
gets two separate acts, and the window must not merge them:

1. **打开浏览器** — unlocks only after the URL has been captured. It can be pressed
   as many times as the user likes, because opening a link is not a state change.
2. **核验** — sends the Enter, then watches the credential file. Success closes the
   window; failure kills the client and starts a fresh one, because the old link is
   spent. The new run prints a new URL and unlocks the button again.

Doing it any other way — auto-opening the browser, a single "done" button, one
blind sleep — loses the step the user is actually responsible for.
"""
from __future__ import annotations

import threading
import traceback
import webbrowser

from .login import LoginClient
from .errors import PanError

POLL_MS = 200
POLL_TRIES = 50          # 50 * 200 ms = 10 s, same budget as the client itself
TICK_MS = 100


def _import_tk():
    import tkinter as tk
    from tkinter import ttk

    return tk, ttk


class LoginWindow:
    def __init__(self, agent_id: str) -> None:
        self.tk, self.ttk = _import_tk()
        self.agent_id = agent_id
        self.client = LoginClient(agent_id)

        self.oauth_url = ""
        self.url_ready = False
        self.unlocked = False
        self.attempts = 0
        self.submitted = False
        self.restarting = False

        tk = self.tk
        self.root = tk.Tk()
        self.root.title("阿里云盘登录")
        self.root.minsize(460, 300)
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.status = tk.StringVar(value="正在启动登录客户端…")
        self._build_ui()
        self.root.after(TICK_MS, self._tick_url_ready)

    # ------------------------------------------------------------------- ui

    def _build_ui(self) -> None:
        tk, ttk = self.tk, self.ttk
        body = tk.Frame(self.root, padx=24, pady=18)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)

        tk.Label(body, text="阿里云盘登录", font=("Helvetica", 18, "bold"),
                 anchor="w").grid(row=0, column=0, sticky="w", pady=(0, 14))

        status_frame = tk.Frame(body)
        status_frame.grid(row=1, column=0, sticky="ew")
        status_frame.columnconfigure(1, weight=1)
        tk.Label(status_frame, text="状态", anchor="w", width=5).grid(
            row=0, column=0, sticky="nw")
        tk.Label(status_frame, textvariable=self.status, fg="#1a5fb4",
                 wraplength=380, justify=tk.LEFT, anchor="w").grid(
            row=0, column=1, sticky="ew", padx=(8, 0))

        buttons = tk.Frame(body)
        buttons.grid(row=2, column=0, sticky="ew", pady=(18, 12))
        buttons.columnconfigure(0, weight=1, uniform="btn")
        buttons.columnconfigure(1, weight=1, uniform="btn")
        self.open_btn = ttk.Button(
            buttons, text="打开浏览器", state=tk.DISABLED, command=self.open_browser
        )
        self.open_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.check_btn = ttk.Button(
            buttons, text="核验", state=tk.DISABLED, command=self.check_token
        )
        self.check_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        tk.Label(
            body,
            text="先点“打开浏览器”并完成授权，再回来点“核验”。\n"
                 "未授权就点“核验”，当前链接会作废并换一条新的。",
            fg="#a51d2d", justify=tk.LEFT, anchor="w", wraplength=380,
        ).grid(row=3, column=0, sticky="w")

    # -------------------------------------------------------------- lifecycle

    def start_login(self) -> None:
        threading.Thread(target=self._run_client, daemon=True).start()

    def _run_client(self) -> None:
        try:
            url = self.client.start()
        except PanError as exc:
            self._say(f"错误：{exc}")
            return
        except Exception:
            traceback.print_exc()
            self._say("错误：登录客户端无法启动")
            return
        self.oauth_url = url
        self.url_ready = True

        # The client now waits for Enter; this thread stays parked until it dies.
        try:
            code = self.client.process.wait()
        except Exception:
            return
        if code == 0:
            self.root.after(100, self.auto_check)
        elif not self.submitted:
            self._say("登录进程在给出链接后退出，请点“核验”重试。")

    def _tick_url_ready(self) -> None:
        if self.url_ready and not self.unlocked:
            self.unlocked = True
            self.open_btn.config(state=self.tk.NORMAL)
            self._say("链接已就绪，点“打开浏览器”。")
        self.root.after(TICK_MS, self._tick_url_ready)

    # ---------------------------------------------------------------- buttons

    def open_browser(self) -> None:
        if not self.oauth_url:
            self._say("还没有链接，请稍等…")
            return
        webbrowser.open(self.oauth_url)
        self.check_btn.config(state=self.tk.NORMAL)
        self._say("已在浏览器打开，请完成授权，然后点“核验”。")

    def check_token(self) -> None:
        self.submitted = True
        self.open_btn.config(state=self.tk.DISABLED)
        self.check_btn.config(state=self.tk.DISABLED)
        self._say("正在核验…")
        try:
            self.client.confirm()
        except PanError:
            self._say("客户端已退出，正在换一条新链接…")
            self.root.after(1500, self.restart_login)
            return
        self.attempts = 0
        self.root.after(POLL_MS, self._poll_token)

    def _poll_token(self) -> None:
        if self.client.valid():
            self._say("授权成功，已取得凭证。")
            self.root.after(1000, self.close)
            return
        self.attempts += 1
        if self.attempts < POLL_TRIES:
            self.root.after(POLL_MS, self._poll_token)
        else:
            self._say("核验超时：链接已作废，正在换一条新的…")
            self.root.after(1500, self.restart_login)

    def auto_check(self) -> None:
        if self.client.valid():
            self._say("授权成功，已取得凭证。")
            self.root.after(1000, self.close)
        else:
            self._say("客户端正常退出但未取得凭证，正在换一条新链接…")
            self.root.after(1500, self.restart_login)

    def restart_login(self) -> None:
        if self.restarting:
            return
        self.restarting = True
        self._say("正在重新获取登录链接…")
        threading.Thread(target=self._restart_worker, daemon=True).start()

    def _restart_worker(self) -> None:
        # Killing the client can block for seconds; the window must stay responsive.
        self.client.stop()
        self.root.after(0, self._after_restart)

    def _after_restart(self) -> None:
        self._reset_state()
        self.start_login()

    def _reset_state(self) -> None:
        self.oauth_url = ""
        self.url_ready = False
        self.unlocked = False
        self.submitted = False
        self.attempts = 0
        self.restarting = False
        self.open_btn.config(state=self.tk.DISABLED)
        self.check_btn.config(state=self.tk.DISABLED)

    # ------------------------------------------------------------------ close

    def _say(self, text: str) -> None:
        self.root.after(0, lambda: self.status.set(text))

    def close(self) -> None:
        self.client.stop()
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def run(self) -> bool:
        self.start_login()
        self.root.mainloop()
        return self.client.valid()


def run_gui(agent_id: str) -> bool:
    window = LoginWindow(agent_id)
    root = window.root
    root.lift()
    root.attributes("-topmost", True)
    root.focus_force()
    root.after(3000, lambda: root.attributes("-topmost", False))
    return window.run()
