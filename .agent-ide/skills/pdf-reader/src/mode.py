"""Which endpoint mode a run uses, and what that mode can actually do.

The mode is not "a flag"; it is a bundle of capabilities that differ in *every*
other layer: how many pages fit in one file, whether links can be batched, whether
the submission returns a ``batch_id`` or a ``task_id``, and whether a zip with
images and block structure exists at all.

Putting that bundle in one place means ``plan`` / ``run`` / ``deliver`` never write
``if mode == ...`` -- they read ``caps.<something>``.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .config import Config


class Mode(str, Enum):
    PRECISION = "precision"
    FLASH = "flash"

    def __str__(self) -> str:  # pragma: no cover - display only
        return self.value


@dataclass(frozen=True)
class Caps:
    """Everything the rest of the pipeline needs to know about the chosen mode."""

    mode: Mode
    page_limit: int
    max_file_mb: int
    link_batch_size: int
    single_file_only: bool
    submit_returns: str          # "batch_id" | "task_id"
    has_zip: bool
    has_images: bool
    has_blocks: bool
    needs_token: bool
    daily_quota_value: int | None
    daily_quota_unit: str        # "pages" | "files"

    @property
    def namespace(self) -> str:
        return self.mode.value


def caps_for(mode: Mode, cfg: Config) -> Caps:
    """Build the capability bundle from the mode's own config namespace."""
    ns = cfg.namespace(mode.value)
    if mode is Mode.PRECISION:
        return Caps(
            mode=mode,
            page_limit=ns.split_page_limit,
            max_file_mb=ns.max_file_mb,
            link_batch_size=ns.link_batch_size,
            single_file_only=False,
            submit_returns="batch_id",
            has_zip=True,
            has_images=True,
            has_blocks=True,
            needs_token=True,
            daily_quota_value=ns.daily_page_quota,
            daily_quota_unit="pages",
        )
    return Caps(
        mode=mode,
        page_limit=ns.split_page_limit,
        max_file_mb=ns.max_file_mb,
        link_batch_size=1,
        single_file_only=True,
        submit_returns="task_id",
        has_zip=False,
        has_images=False,
        has_blocks=False,
        needs_token=False,
        daily_quota_value=cfg.flash.daily_file_quota,
        daily_quota_unit="files",
    )


def decide_mode(requested_flash: bool, has_token: bool) -> Mode:
    """``--flash`` wins; otherwise a token selects precision, its absence flash.

    A missing token is not an error: flash is a legitimate degraded channel (20
    pages, 10MB, markdown only, no images) and the caller is told about the
    difference rather than refused.
    """
    if requested_flash:
        return Mode.FLASH
    return Mode.PRECISION if has_token else Mode.FLASH
