"""The contact window: the user reads the draft, edits, and submits.

It runs in its own process (`python -c "from src.gui import main; main()" <id>`).
The parent learns the outcome from a handshake file rather than from stdout,
because a window that crashes produces neither.
"""
from __future__ import annotations
import re
import sys
import time
import tkinter as tk
from tkinter import scrolledtext

from . import handshake
from .paths import autosave, geometry

DEFAULT_GEOMETRY = "520x420"
GEOMETRY_RE = re.compile(r"^(\d+)x(\d+)(?:([+-]\d+)([+-]\d+))?$")
AUTOSAVE_MS = 1000
TITLE_MS = 1000
GEOMETRY_MS = 400


# --------------------------------------------------------------------- window


def main() -> int:
    from .reply_again import compose

    agent_id = sys.argv[1] if len(sys.argv) > 1 else "agent"
    root = tk.Tk()
    root.title(f"Contact · {agent_id}")

    area = scrolledtext.ScrolledText(
        root, wrap=tk.WORD, undo=True, maxundo=-1, font=("Helvetica", 14)
    )
    area.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    _restore_geometry(root, agent_id)
    _restore_draft(agent_id, area)

    submitted = {"value": False}

    def submit() -> None:
        reply = area.get("1.0", "end").strip()
        if not reply:
            return
        submitted["value"] = True
        _save_state(root, agent_id, area)
        _clear_draft(agent_id)
        handshake.write(agent_id, "SUBMITTED", reply)
        root.destroy()

    def close() -> None:
        _save_state(root, agent_id, area)
        handshake.write(agent_id, "CLOSED")
        root.destroy()

    def reply_again() -> None:
        area.delete("1.0", "end")
        area.insert("1.0", compose(agent_id))

    buttons = tk.Frame(root)
    buttons.pack(fill=tk.X, padx=8, pady=(0, 8))
    tk.Button(buttons, text="Reply again", command=reply_again).pack(side=tk.LEFT)
    tk.Button(buttons, text="Submit", command=submit).pack(
        side=tk.LEFT, fill=tk.X, expand=True, padx=8
    )
    tk.Button(buttons, text="Close", command=close).pack(side=tk.LEFT)

    root.protocol("WM_DELETE_WINDOW", close)
    for sequence in ("<Control-Return>", "<Command-Return>"):
        area.bind(sequence, lambda _event: submit())

    started = time.time()

    def tick_title() -> None:
        root.title(f"Contact · {agent_id} · {int(time.time() - started)}s")
        root.after(TITLE_MS, tick_title)

    def tick_autosave() -> None:
        _save_draft(agent_id, area)
        root.after(AUTOSAVE_MS, tick_autosave)

    def schedule_geometry(_event=None) -> None:
        pending = getattr(root, "_geometry_job", None)
        if pending:
            root.after_cancel(pending)
        root._geometry_job = root.after(GEOMETRY_MS, lambda: _save_geometry(root, agent_id))

    root.bind("<Configure>", schedule_geometry, add="+")
    tick_title()
    tick_autosave()
    area.focus_set()
    root.mainloop()
    return 0 if submitted["value"] else 1


def _save_state(root, agent_id: str, area) -> None:
    _save_draft(agent_id, area)
    _save_geometry(root, agent_id)


# ---------------------------------------------------------------------- draft


def _restore_draft(agent_id: str, area) -> None:
    try:
        draft = autosave(agent_id).read_text(encoding="utf-8")
    except OSError:
        return
    if draft.strip():
        area.insert("1.0", draft)


def _save_draft(agent_id: str, area) -> None:
    draft = area.get("1.0", "end").strip()
    path = autosave(agent_id)
    try:
        if draft:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(draft, encoding="utf-8")
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


def _restore_geometry(root, agent_id: str) -> None:
    """Reuse the last size and position, but only if it lands on this screen."""
    root.geometry(DEFAULT_GEOMETRY)
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


def _save_geometry(root, agent_id: str) -> None:
    try:
        current = root.wm_geometry()
    except tk.TclError:
        return
    if not current:
        return
    try:
        path = geometry(agent_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(current, encoding="utf-8")
    except OSError:
        pass
