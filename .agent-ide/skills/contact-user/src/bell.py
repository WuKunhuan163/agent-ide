"""The alert bell: start one sound, do not wait for it.

The bell is played by the parent process that also waits for the GUI, so no
cross-process state file is needed to know whether the user was alerted: the
`Popen` either started or it did not.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

AUDIO = Path("src") / "bell.mp3"


def play() -> bool:
    """Start the alert sound; False when it could not be started at all."""
    from .paths import pkg_dir

    sound = pkg_dir() / AUDIO
    if not sound.is_file():
        return False
    player = "afplay" if sys.platform == "darwin" else None
    commands = [[player, str(sound)]] if player else [["paplay", str(sound)], ["aplay", str(sound)]]
    for command in commands:
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            continue
        return True
    return False
