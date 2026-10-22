"""Download and unpack the server's product.

This is the *only* place a result zip is touched, and it is called at most once per
job.  Mixing this with the status probe is what made the archived client download
~0.94MB on every poll; here the probe is a bare query and this module is reached
only when products are actually wanted.

The zip already contains the cropped figures (``images/*.jpg``), so the old
PyMuPDF 300dpi cropping pass is gone -- it was re-doing the server's work.
"""
from __future__ import annotations

import io
import json
import zipfile

from ..endpoint.client import EndpointClient


CONTENT_LIST_SUFFIX = "_content_list.json"
IMAGE_PREFIX = "images/"


def download(client: EndpointClient, url: str) -> dict[str, bytes]:
    """Fetch a result zip into ``{member_name: bytes}``."""
    raw = client.download(url)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        return {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}


def pick(members: dict[str, bytes]) -> dict:
    """Choose the public products out of a zip.

    ``*_content_list.json`` is the documented block structure.  The ``_v2`` variant
    is deliberately ignored: the official client ignores it too, and its schema is
    not published.  ``layout.json`` / ``*_model.json`` are skipped for the same
    reason -- the archived tool read them through a private field and broke the moment
    the SDK changed.
    """
    markdown = members.get("full.md", b"").decode("utf-8", "replace")
    content_list = None
    for name, payload in sorted(members.items()):
        if name.endswith(CONTENT_LIST_SUFFIX):
            try:
                content_list = json.loads(payload.decode("utf-8", "replace"))
            except json.JSONDecodeError:
                content_list = None
            break
    images = {name: payload for name, payload in members.items() if name.startswith(IMAGE_PREFIX)}
    return {"markdown": markdown, "content_list": content_list, "images": images}


def fetch_zip(client: EndpointClient, url: str) -> dict:
    return pick(download(client, url))


def fetch_markdown(client: EndpointClient, url: str) -> dict:
    """Flash returns nothing but a markdown URL -- no zip, no images, no blocks."""
    return {"markdown": client.download(url).decode("utf-8", "replace"),
            "content_list": None, "images": {}}
