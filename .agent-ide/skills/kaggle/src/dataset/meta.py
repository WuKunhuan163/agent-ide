"""``dataset-metadata.json`` helpers (domain layer, no CLI surface).

Behaviour kept from the legacy tool: the file always carries ``id`` =
``<username>/<slug>`` and is forced private, and ``--dir-mode zip`` uploads rely
on this file existing in the folder.
"""
from __future__ import annotations

import json
import os

from src import identity
from src.exit_codes import INPUT_USAGE

METADATA_NAME = "dataset-metadata.json"
DEFAULT_LICENSE = "CC0-1.0"


def metadata_path(local_dir: str) -> str:
    return os.path.join(local_dir, METADATA_NAME)


def has_metadata(local_dir: str) -> bool:
    return os.path.isfile(metadata_path(local_dir))


def slugify(title: str) -> str:
    """Kaggle slug convention: lower-case, spaces and underscores become dashes."""
    return title.lower().replace(" ", "-").replace("_", "-")


def read_metadata(local_dir: str) -> dict:
    path = metadata_path(local_dir)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise identity.IdentityError(
            INPUT_USAGE, f"No {METADATA_NAME} in {local_dir}."
        ) from None
    except (json.JSONDecodeError, OSError) as exc:
        raise identity.IdentityError(
            INPUT_USAGE, f"Unreadable {METADATA_NAME} in {local_dir} ({exc})"
        ) from None
    return data if isinstance(data, dict) else {}


def write_metadata(local_dir: str, data: dict) -> None:
    with open(metadata_path(local_dir), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ensure_metadata(local_dir: str, username: str, title: str | None = None) -> str:
    """Create or repair ``dataset-metadata.json``; return the title slug.

    Missing file -> write a fresh private one. Existing file -> repair ``id`` to
    the current account and force ``isPrivate`` (legacy did exactly this so a
    folder can be re-uploaded under another account).
    """
    fallback = slugify(title or os.path.basename(os.path.normpath(local_dir)))
    if not has_metadata(local_dir):
        write_metadata(
            local_dir,
            {
                "title": fallback,
                "id": f"{username}/{fallback}",
                "licenses": [{"name": DEFAULT_LICENSE}],
                "isPrivate": True,
            },
        )
        return fallback

    data = read_metadata(local_dir)
    slug = data.get("title") or fallback
    data["title"] = slug
    data["id"] = f"{username}/{slug}"
    data["isPrivate"] = True
    write_metadata(local_dir, data)
    return slug


def metadata_owner(local_dir: str) -> str | None:
    """Username prefix of the metadata ``id`` (owner gate), or None when absent."""
    dataset_id = read_metadata(local_dir).get("id")
    if isinstance(dataset_id, str) and "/" in dataset_id:
        return dataset_id.split("/", 1)[0]
    return None
