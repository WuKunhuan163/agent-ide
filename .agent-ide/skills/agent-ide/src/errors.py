"""Exit codes and the one exception type this tool raises.

Every failure is an `AgentIdeError` carrying its exit code, so no caller has to
guess a code from the wording of a message.
"""
from __future__ import annotations


class Exit:
    OK = 0

    class Cli:
        USAGE = 2
        MISSING_PROJECT_ROOT = 10

    class Config:
        MISSING_GLOBAL = 20

    class Package:
        FAILED = 40

    class Install:
        FAILED = 50
        MISSING_SKILLS = 51
        DEP_FAILED = 54

    class Inject:
        FAILED = 52

    class Publish:
        FAILED = 55

    class Replica:
        FAILED = 56


class AgentIdeError(RuntimeError):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def fail(code: int, message: str) -> "AgentIdeError":
    return AgentIdeError(code, message)
