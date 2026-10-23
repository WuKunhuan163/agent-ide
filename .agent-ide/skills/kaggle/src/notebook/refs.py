"""Notebook refs: title -> slug, the three ref forms, owner disambiguation.

The event log doubles as the owner directory: a bare ``slug`` that exactly one
account pushed before resolves to that account, an ambiguous one is refused,
and an unknown one is refused with "push first" guidance, so a typo never opens
or monitors somebody else's notebook.
"""
from __future__ import annotations

import json
import os
import re

from src import identity
from src.exit_codes import INPUT_USAGE
from src.paths import require_ctx

PUSH_ACTION = "PUSH_NOTEBOOK"


def slugify(title: str) -> str:
    """Display title -> Kaggle URL slug (cloud-aligned: lowercase, dashes, alnum)."""
    slug = title.lower().strip().replace(" ", "-").replace("_", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def normalize_notebook_ref(ref: str, default_username: str | None = None) -> tuple[str | None, str]:
    """Zero-entropy slug resolver -> ``(username | None, slug)``.

    Accepts the three interchangeable forms: ``user/slug`` (Kaggle API
    canonical), ``user:slug`` (agent shorthand) and bare ``slug`` (falls back to
    ``default_username``). A local directory comes back as ``(None, path)`` so
    the caller can read its metadata title instead.
    """
    ref = ref.strip()
    if os.path.isdir(ref):
        return None, ref
    if ":" in ref and "/" not in ref:
        user, slug = ref.split(":", 1)
    elif "/" in ref:
        user, slug = ref.split("/", 1)
    else:
        user, slug = None, ref
    user = (user or "").strip() or None
    slug = slug.strip()
    if user is None and default_username:
        user = default_username
    return user, slug


def _owners_from_event_log(slug: str) -> list[str]:
    event_log = require_ctx().event_log_file
    if not os.path.exists(event_log):
        return []
    try:
        with open(event_log, encoding="utf-8") as f:
            events = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    owners = {
        event["username"]
        for event in events
        if event.get("action") == PUSH_ACTION
        and event.get("username")
        and str(event.get("target", "")).split("/")[-1] == slug
    }
    return sorted(owners)


def _slug_from_folder(folder: str) -> str | None:
    """Slug derived from a local notebook folder's kernel-metadata.json title."""
    meta_path = os.path.join(folder, "kernel-metadata.json")
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, encoding="utf-8") as f:
            title = (json.load(f) or {}).get("title", "")
    except (json.JSONDecodeError, OSError):
        return None
    if not title:
        raise identity.IdentityError(
            INPUT_USAGE, f"'title' is a required field inside {meta_path}"
        )
    return slugify_title(title)


def resolve_open_target(notebook_arg: str) -> tuple[str, str]:
    """``(username, slug)`` for ``notebook open``, disambiguated via the event log."""
    username, slug = normalize_notebook_ref(notebook_arg)
    if username is None and os.path.isdir(slug):
        slug = _slug_from_folder(slug) or slug
        username, slug = normalize_notebook_ref(slug)
    if username is not None:
        return username, slug

    owners = _owners_from_event_log(slug)
    if len(owners) == 1:
        print(f"Auto-routed to its unique owner: {owners[0]}")
        return owners[0], slug
    if len(owners) > 1:
        raise identity.IdentityError(
            INPUT_USAGE,
            f"Ambiguous name '{slug}'; pushed by {len(owners)} accounts: {', '.join(owners)}.\n"
            f"  Specify it as: username:{slug}",
        )
    raise identity.IdentityError(
        INPUT_USAGE, f"Notebook '{slug}' has no historical push records. Push it first."
    )


def resolve_notebook_args(notebook_arg: str) -> tuple[str, str, str]:
    """``(username, slug, canonical 'user/slug')`` with the bound account as default."""
    username, slug = normalize_notebook_ref(
        notebook_arg, default_username=identity.resolve_username()
    )
    if username is None:
        username = identity.resolve_username()
    return username, slug, f"{username}/{slug}"
