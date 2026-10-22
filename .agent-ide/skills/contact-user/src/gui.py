"""The contact window: the user reads the draft, edits, and submits.

It runs in its own process (`python -c "from src.gui import main; main()" <id>`)
and reports through a handshake file, because a crashed window produces no
stdout and no handshake either.

Layout is the one this tool has always had: a small window (the last size the
user dragged, else `window_geometry` from `data/config.json`), the configured
editor font and row count, and at the bottom only two buttons — `Reply again`
and `Submit`, which stays disabled until the text differs from what the window
opened with. Closing is the window's own close button.
"""
from __future__ import annotations
import os
import platform
import re
import sys
import time
import tkinter as tk
from tkinter import scrolledtext

from . import bell, config, handshake
from .paths import autosave, geometry
from .reply_again import compose

GEOMETRY_RE = re.compile(r"^\s*(\d+)x(\d+)(?:([+-]\d+)([+-]\d+))?\s*$")
TITLE_MS = 1000
GEOMETRY_MS = 400


def main() -> int:
    agent_id = sys.argv[1] if len(sys.argv) > 1 else "agent"
    hint = os.environ.get("CONTACT_USER_HINT", "").strip()
    layout = config.window()
    root = tk.Tk()
    root.title(f"Agent {agent_id} - Waiting (0s)")
    _restore_geometry(root, agent_id, layout["geometry"])

    area = scrolledtext.ScrolledText(
        root,
        wrap=tk.WORD,
        height=layout["rows"],
        font=(layout["font"], layout["font_size"]),
        undo=True,
        maxundo=-1,
    )
    area.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    _restore_draft(agent_id, area, hint)
    baseline = area.get("1.0", tk.END).strip()

    submitted = {"value": False}

    def save() -> None:
        _save_draft(agent_id, area)
        _save_geometry(root, agent_id)

    def submit() -> None:
        raw = _reply_text(area.get("1.0", "end"), hint)
        if not raw:
            close()
            return
        submitted["value"] = True
        _save_geometry(root, agent_id)
        _clear_draft(agent_id)
        handshake.write(agent_id, "SUBMITTED", raw)
        root.quit()

    def close() -> None:
        save()
        handshake.write(agent_id, "CLOSED")
        root.quit()

    def reply_again() -> None:
        reply = compose(_reply_text(area.get("1.0", "end"), hint), agent_id)
        submitted["value"] = True
        _save_geometry(root, agent_id)
        _clear_draft(agent_id)
        handshake.write(agent_id, "SUBMITTED", reply.strip())
        root.quit()

    btn_row = tk.Frame(root)
    btn_row.pack(pady=(0, 8), fill=tk.X, padx=8)
    reply_btn = tk.Button(btn_row, text="Reply again", command=reply_again, state=tk.DISABLED)
    reply_btn.pack(side=tk.LEFT, padx=(0, 8))
    submit_btn = tk.Button(btn_row, text="Submit", command=submit, state=tk.DISABLED)
    submit_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def sync_buttons() -> None:
        text = area.get("1.0", tk.END).strip()
        edited = text != baseline
        reply_btn.config(state=tk.NORMAL if edited else tk.DISABLED)
        submit_btn.config(state=tk.NORMAL if (edited and text) else tk.DISABLED)

    def on_change(_event: object | None = None) -> None:
        try:
            area.edit_modified(False)
        except tk.TclError:
            pass
        _save_draft(agent_id, area)
        sync_buttons()

    def on_ctrl_return(_event: object) -> str:
        if str(submit_btn.cget("state")) == str(tk.NORMAL):
            submit()
        return "break"

    def do_undo(_event: object) -> str:
        try:
            area.edit_undo()
        except tk.TclError:
            pass
        sync_buttons()
        return "break"

    def do_redo(_event: object) -> str:
        try:
            area.edit_redo()
        except tk.TclError:
            pass
        sync_buttons()
        return "break"

    sync_buttons()
    root.protocol("WM_DELETE_WINDOW", close)
    area.bind("<Control-Return>", on_ctrl_return)
    area.bind("<KeyRelease>", on_change)
    area.bind("<<Modified>>", on_change)
    if platform.system() == "Darwin":
        area.bind("<Command-z>", do_undo)
        area.bind("<Command-Shift-Z>", do_redo)
        area.bind("<Command-Shift-z>", do_redo)
    else:
        area.bind("<Control-z>", do_undo)
        area.bind("<Control-y>", do_redo)
        area.bind("<Control-Shift-Z>", do_redo)

    def tick_title() -> None:
        root.title(f"Agent {agent_id} - Waiting ({int(time.time() - started)}s)")
        root.after(TITLE_MS, tick_title)

    def tick_autosave() -> None:
        _save_draft(agent_id, area)
        root.after(config.autosave_ms(), tick_autosave)

    def tick_geometry() -> None:
        _save_geometry(root, agent_id)
        root.after(GEOMETRY_MS, tick_geometry)

    started = time.time()
    tick_title()
    tick_geometry()
    if config.autosave_ms():
        tick_autosave()
    _ring(root)
    area.focus_set()
    _raise(root)
    root.mainloop()
    root.destroy()
    return 0 if submitted["value"] else 1


def _ring(root) -> None:
    """Ring once, then every `bell_interval` seconds while the window waits."""
    bell.play()
    interval = config.bell_interval()
    if interval:
        root.after(interval * 1000, lambda: _ring(root))


def _raise(root) -> None:
    """Ask for the front once mapped; a background process is often refused."""
    try:
        root.deiconify()
        root.lift()
        root.attributes("-topmost", True)
        root.focus_force()
        root.after(3000, lambda: root.attributes("-topmost", False))
    except tk.TclError:
        pass


def _reply_text(text: str, hint: str) -> str:
    """What the user actually wrote: the hint is context, not part of the reply."""
    body = text.strip()
    lead = (hint or "").strip()
    if lead and body.startswith(lead):
        body = body[len(lead):].strip()
    return body


# ---------------------------------------------------------------------- draft


def _restore_draft(agent_id: str, area, hint: str = "") -> None:
    """Open with the user's unsaved draft if there is one, else the agent's text.

    The draft wins because it is the user's own words; the hint is what the agent
    just wrote, and without it the window would open empty.
    """
    try:
        draft = autosave(agent_id).read_text(encoding="utf-8")
    except OSError:
        draft = ""
    text = draft.strip() or hint
    if text:
        area.insert("1.0", text)


def _save_draft(agent_id: str, area) -> None:
    text = area.get("1.0", tk.END).strip()
    path = autosave(agent_id)
    try:
        if text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        else:
            path.unlink(missing_ok=True)
    except OSError:
        pass


def _clear_draft(agent_id: str) -> None:
    try:
        autosave(agent_id).unlink(missing_ok=True)
    except OSError:
        pass


# ------------------------------------------------------------------- geometry


def _restore_geometry(root, agent_id: str, default: str) -> None:
    """Open at the top of the screen, then reuse the last size and position.

    The window appears where the user looks first: horizontally centred and
    flush with the top edge, unless `window_geometry` names a position or the
    user has already placed the window (that position is reused when it still
    lands on this screen).
    """
    root.geometry(_top_of_screen(root, default))
    try:
        saved = geometry(agent_id).read_text(encoding="utf-8").strip()
    except OSError:
        return
    match = GEOMETRY_RE.match(saved or "")
    if not match:
        return
    width, height = int(match.group(1)), int(match.group(2))
    if match.group(3) is not None:
        left, top = int(match.group(3)), int(match.group(4))
        if (left < 0 or top < 0
                or left + width > root.winfo_screenwidth()
                or top + height > root.winfo_screenheight()):
            return
    try:
        root.geometry(saved)
    except tk.TclError:
        pass


def _top_of_screen(root, default: str) -> str:
    """`WxH` becomes `WxH+X+0`, horizontally centred; an explicit `+X+Y` wins."""
    match = GEOMETRY_RE.match(default.strip())
    if not match:
        return default
    width, height = int(match.group(1)), int(match.group(2))
    if match.group(3) is not None:
        return default
    left = max(0, (root.winfo_screenwidth() - width) // 2)
    return f"{width}x{height}+{left}+0"


def _save_geometry(root, agent_id: str) -> None:
    """Remember this window's size and position under its agent id.

    Polled while the window lives and called once more before it closes, so a
    resize is remembered whether the user submits, closes, or wanders off.
    """
    try:
        current = root.wm_geometry()
    except tk.TclError:
        return
    if not current:
        return
    match = GEOMETRY_RE.match(current)
    if not match or int(match.group(1)) < 50 or int(match.group(2)) < 50:
        return  # not mapped yet: the first poll must not poison the memory
    path = geometry(agent_id)
    try:
        if path.read_text(encoding="utf-8").strip() == current:
            return
    except OSError:
        pass
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(current, encoding="utf-8")
    except OSError:
        pass
