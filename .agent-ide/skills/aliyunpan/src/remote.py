"""The remote tree, addressed the way a person addresses it.

The API takes `file_id`s; people take paths. Every path is resolved by listing one
level at a time, because a cached id can point at a folder that was renamed in the
web UI, and writing to the wrong folder is silent.

Creation is opt-in: `resolve(..., create=True)` is what `mkdir -p` and upload use,
while read paths pass `create=False` and fail with `NotFound` instead of quietly
materialising a typo.
"""
from __future__ import annotations

from .errors import NameTaken, NotFound
from .session import Session

PAGE = 200


def list_dir(session: Session, parent_id: str) -> list[dict]:
    """Every child of one folder, following the marker to the end."""
    items: list[dict] = []
    marker = ""
    while True:
        payload = {"parent_file_id": parent_id, "limit": PAGE}
        if marker:
            payload["marker"] = marker
        body = session.call("list", payload)
        items.extend(body.get("items") or [])
        marker = body.get("next_marker") or ""
        if not body.get("items") or not marker:
            return items


def find_child(session: Session, parent_id: str, name: str) -> dict | None:
    for item in list_dir(session, parent_id):
        if item.get("name") == name:
            return item
    return None


def resolve(session: Session, path: str, *, create: bool = False) -> str:
    """Turn `/a/b/c` into a folder id, creating missing folders only if asked."""
    parent = "root"
    for part in [p for p in str(path).split("/") if p]:
        item = find_child(session, parent, part)
        if item is None:
            if not create:
                raise NotFound(f"no such folder: {path}")
            created = session.call(
                "create",
                {"parent_file_id": parent, "name": part, "type": "folder", "check_name_mode": "refuse"},
            )
            parent = created.get("file_id") or ""
            if not parent:
                raise NotFound(f"could not create folder: {part}")
            continue
        if item.get("type") != "folder":
            raise NotFound(f"{part} is a file, not a folder (in {path})")
        parent = item.get("file_id") or ""
    return parent


def stat(session: Session, path: str) -> dict:
    """The item at `path`; a bare `/` returns the root pseudo-item."""
    if path.strip("/") == "":
        return {"file_id": "root", "name": "/", "type": "folder", "size": 0}
    parent_path, _, name = path.rstrip("/").rpartition("/")
    parent = resolve(session, parent_path or "/", create=False)
    item = find_child(session, parent, name)
    if item is None:
        raise NotFound(f"no such file: {path}")
    return item


def children_of(session: Session, folder: dict) -> list[dict]:
    return list_dir(session, folder.get("file_id") or "root")


def assert_free(session: Session, parent_id: str, names: list[str]) -> None:
    """Refuse before uploading when any target name already exists.

    Overwriting is not a safe default for a backup path: a mistyped destination
    would replace the previous copy silently, and the previous copy is the one
    thing this tool exists to keep.
    """
    existing = {item.get("name") for item in list_dir(session, parent_id)}
    taken = [name for name in names if name in existing]
    if taken:
        raise NameTaken(
            "already present in the destination: " + ", ".join(taken) + "; rename or remove them first"
        )


def mkdir(session: Session, path: str) -> dict:
    parent_path, _, name = path.rstrip("/").rpartition("/")
    parent = resolve(session, parent_path or "/", create=True)
    if find_child(session, parent, name):
        raise NameTaken(f"already exists: {path}")
    return session.call(
        "create",
        {"parent_file_id": parent, "name": name, "type": "folder", "check_name_mode": "refuse"},
    )


def delete(session: Session, path: str) -> dict:
    item = stat(session, path)
    return session.call("delete", {"file_id": item["file_id"]})


def move(session: Session, path: str, destination: str) -> dict:
    item = stat(session, path)
    parent = resolve(session, destination, create=True)
    return session.call(
        "move",
        {"file_id": item["file_id"], "to_parent_file_id": parent, "check_name_mode": "refuse"},
    )


def download_url(session: Session, file_id: str, expire_seconds: int = 3600) -> str:
    body = session.call("getDownloadUrl", {"file_id": file_id, "expire_sec": expire_seconds})
    url = body.get("url") or ""
    if not url:
        raise NotFound("the endpoint returned no download url")
    return url
