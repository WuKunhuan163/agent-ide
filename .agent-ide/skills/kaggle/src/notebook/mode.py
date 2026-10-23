"""Push modes: background (default) and manual.

Background
    The API layer keeps ``enable_gpu=true``; Kaggle allocates the accelerator and
    starts the run itself. Nothing is owed to a human, so a push in this mode
    does not open a browser at all. An editor tab here would be worse than
    useless: it invites the user to click Run All on a session that is already
    running, and a second Run All on a live kernel is how a good run gets killed.

Manual
    The API layer is pushed with ``enable_gpu=false``; the injected GPU check
    marks the CPU session ``AWAITING_GPU_SELECTION``, and a human picks T4 x2 and
    presses Run All. This mode opens the editor, because the editor is where that
    happens.

Both modes run the same gates, mint the same slug, and write the same ledger.
The differences are the fields below, so no call site re-reads the interlock
flag and no branch checks it twice.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PushMode:
    """Everything that differs between a background push and a manual one."""

    name: str
    #: send ``enable_gpu`` through to the API instead of forcing it off
    api_enable_gpu_as_authored: bool
    #: Kaggle starts the run on its own; a human does not have to
    starts_itself: bool
    #: open a browser tab after a successful push
    opens_editor: bool
    #: which Kaggle page a browser tab should land on
    page: str
    #: the run waits for a human pressing Run All
    requires_run_all: bool

    @property
    def is_background(self) -> bool:
        return self.name == "background"


BACKGROUND = PushMode(
    name="background",
    api_enable_gpu_as_authored=True,
    starts_itself=True,
    opens_editor=False,
    page="view",
    requires_run_all=False,
)

MANUAL = PushMode(
    name="manual",
    api_enable_gpu_as_authored=False,
    starts_itself=False,
    opens_editor=True,
    page="edit",
    requires_run_all=True,
)


def current() -> PushMode:
    """The mode the config selects; background unless the interlock is on."""
    from src.config.config import gpu_interlock_enabled

    return MANUAL if gpu_interlock_enabled() else BACKGROUND
