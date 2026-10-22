"""Stable error codes and the single data-plane exception type."""
from __future__ import annotations

# --- public contract: these strings are stable and referenced by CLI / tests ---
PROJECT_EXISTS = "PROJECT_EXISTS"
PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
TEMPLATE_VERSION_MISMATCH = "TEMPLATE_VERSION_MISMATCH"
BLOCK_NOT_FOUND = "BLOCK_NOT_FOUND"
BLOCK_TYPE_UNKNOWN = "BLOCK_TYPE_UNKNOWN"
CONTENT_INVALID = "CONTENT_INVALID"
CONTENT_ID_INVALID = "CONTENT_ID_INVALID"
CONTENT_PATH_NOT_FOUND = "CONTENT_PATH_NOT_FOUND"
ORDER_CONFLICT = "ORDER_CONFLICT"
CHILD_NOT_ALLOWED = "CHILD_NOT_ALLOWED"
LEAF_CANNOT_HAVE_CHILDREN = "LEAF_CANNOT_HAVE_CHILDREN"
PATH_UNSAFE = "PATH_UNSAFE"
CITATION_UNDEFINED = "CITATION_UNDEFINED"
LABEL_UNDEFINED = "LABEL_UNDEFINED"
METADATA_INCOMPLETE = "METADATA_INCOMPLETE"
SECTION_LIMIT = "SECTION_LIMIT"

# --- format / codec level ---
MALFORMED_FILE = "MALFORMED_FILE"
SCHEMA_UNSUPPORTED = "SCHEMA_UNSUPPORTED"

# --- disk level ---
WRITE_FAILED = "WRITE_FAILED"

CODES = frozenset(
    {
        PROJECT_EXISTS,
        PROJECT_NOT_FOUND,
        TEMPLATE_NOT_FOUND,
        TEMPLATE_VERSION_MISMATCH,
        BLOCK_NOT_FOUND,
        BLOCK_TYPE_UNKNOWN,
        CONTENT_INVALID,
        CONTENT_ID_INVALID,
        CONTENT_PATH_NOT_FOUND,
        ORDER_CONFLICT,
        CHILD_NOT_ALLOWED,
        LEAF_CANNOT_HAVE_CHILDREN,
        PATH_UNSAFE,
        CITATION_UNDEFINED,
        LABEL_UNDEFINED,
        METADATA_INCOMPLETE,
        SECTION_LIMIT,
        MALFORMED_FILE,
        SCHEMA_UNSUPPORTED,
        WRITE_FAILED,
    }
)


class DataError(Exception):
    """Every data-plane failure is raised as a DataError with a stable code."""

    def __init__(
        self,
        code: str,
        path: str | None = None,
        detail: str = "",
        *,
        field: str | None = None,
    ) -> None:
        if code not in CODES:
            raise ValueError(f"unknown error code: {code!r}")
        self.code = code
        self.path = path
        self.detail = detail
        self.field = field
        super().__init__(self._render())

    def _render(self) -> str:
        parts = [self.code]
        if self.path:
            parts.append(f"path={self.path}")
        if self.field:
            parts.append(f"field={self.field}")
        if self.detail:
            parts.append(self.detail)
        return ": ".join(parts)
