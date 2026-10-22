"""Failures the CLI can explain, and the exit code each one maps to."""
from __future__ import annotations


class PanError(Exception):
    """A failure with a message meant for the user, not a traceback."""

    code = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UsageError(PanError):
    code = 2


class NotLoggedIn(PanError):
    code = 3


class DriveMissing(PanError):
    code = 4


class NotFound(PanError):
    code = 5


class NameTaken(PanError):
    """A file of that name already exists and overwriting is off by design."""

    code = 6


class TransferFailed(PanError):
    code = 7
