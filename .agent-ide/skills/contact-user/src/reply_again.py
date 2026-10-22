"""The text behind the window's "Reply again" button.

The user presses it when the agent's last contact broke the collaboration
contract. The text is a fixed checklist: it names what to check, what to fix,
and that the fix must arrive as a new contact round.
"""
from __future__ import annotations

CHECKLIST = (
    "(1) Unapproved state change: files were edited or commands were run without "
    "the user's approval.",
    "(2) Stale snapshot: paths or line numbers were cited without reading the "
    "current file in the same turn.",
    "(3) Not actionable: the guidance is a vague plan, not steps the user can "
    "follow, or its line ranges are wrong.",
    "(4) User sovereignty: existing partial work (naming, structure, style) was "
    "ignored, or a whole-file rewrite was pushed where a patch was expected.",
    "(5) Invisible context: the message refers to something only you can see "
    "(earlier chat, option labels you invented).",
)

FOOTER = (
    "Match the first item above that applies, fix it, then re-contact via "
    "contact-user — do not answer in the IDE chat.\n"
    "  (1) inspect `git log -30 --oneline`, pick the last good checkpoint, "
    "`git reset --hard <sha>`, and re-contact with only the approved changes.\n"
    "  (2)-(5) re-read the disk state, rewrite the message so it stands alone, "
    "and re-contact.\n"
    "If none applies, say what you think went wrong and re-contact."
)


def compose(extra: str, agent_id: str = "") -> str:
    """Wrap whatever the user typed into the checklist (empty text is fine)."""
    lines = ["Contract violation in the previous contact round."]
    if extra.strip():
        lines += ["", "The user's message:", "「", extra.strip(), "」"]
    lines += ["", "Check, in this order:", *CHECKLIST, "", FOOTER]
    return "\n".join(lines)
