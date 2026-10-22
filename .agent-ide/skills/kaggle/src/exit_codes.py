OK = 0

INPUT_MISSING_ID = 10
INPUT_USAGE = 11
BLOCKED_BY_CONTRACT = 12

AUTH_NO_ACCOUNT = 20
AUTH_TOKEN_MISSING = 21
AUTH_REJECTED = 22

PUSH_OWNER_MISMATCH = 31
PUSH_FAILED = 32
DATASET_TOO_LARGE = 33
QUOTA_EXCEEDED = 34
KERNEL_FAILED = 35

BROWSER_FAILED = 40
BROWSER_PROFILE_CORRUPT = 41

EXEC_CLI_MISSING = 50
EXEC_TIMEOUT = 51
EXEC_FAILED = 52


class IdentityError(Exception):
    """CLI failure carrying the exit code the router must return."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
