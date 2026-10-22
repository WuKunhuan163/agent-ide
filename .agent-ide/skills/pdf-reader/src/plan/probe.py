"""Make an input local, then find out what it is and how big it is.

A ``-u`` input is fetched into ``data/sources/<url hash>/<name>`` before anything
else happens, because the plan rests on the page count: only a local file can be
measured (PyMuPDF), and only a measured file can have its page windows computed up
front.  Leaving the URL with the endpoint instead means pushing the file's whole
size at a service that refuses it after the fact -- which is how a URL used to end
up as a blind submission that no split could rescue.

Page counts are still unavailable when PyMuPDF is absent; the execution layer then
walks the file window by window (``planner.window_at``) as before.  The same library
also *cuts* a window here, in memory, so a windowed job can upload the pages it stands
for instead of asking the endpoint to read a range of the whole file.
"""
from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from ..endpoint.models import Source
from ..util import log, paths

if TYPE_CHECKING:
    from ..endpoint.client import EndpointClient


def looks_like_url(value: str) -> bool:
    return urlparse(value).scheme in ("http", "https")


@lru_cache(maxsize=1)
def _fitz():
    """The optional PDF library, or ``None`` when it is not installed."""
    try:
        import pymupdf as fitz               # modern import name
    except ImportError:
        try:
            import fitz
        except ImportError:                  # pragma: no cover - older wheels
            log.debug("pymupdf not installed; page measurement and slicing unavailable")
            return None
    return fitz


def page_count(path: Path) -> int | None:
    """Best-effort page count; ``None`` when PyMuPDF is unavailable or unreadable."""
    fitz = _fitz()
    if fitz is None:
        return None
    try:
        with fitz.open(str(path)) as doc:
            return int(doc.page_count)
    except Exception as exc:
        log.warn(f"could not read page count of {path.name}: {exc}")
        return None


def page_sizes(path: Path) -> list[int] | None:
    """The serialized size of every page, or ``None`` when it cannot be measured.

    Each page is measured on its own, which makes the sum over a range an *upper* bound
    for that range's own size: resources a window shares are counted once inside it and
    once per page here.  Planning prefers that direction -- a window above the byte
    limit is refused by the endpoint, while an under-filled one only costs a request.
    """
    fitz = _fitz()
    if fitz is None:
        return None
    try:
        with fitz.open(str(path)) as doc:
            return [len(_crop(fitz, doc, page, page))
                    for page in range(1, int(doc.page_count) + 1)]
    except Exception as exc:
        log.warn(f"could not measure the page sizes of {path.name}: {exc}")
        return None


def window_bytes(path: Path, pages: list[int]) -> bytes | None:
    """The equivalent PDF of ``pages``: an ordinary document of exactly those pages.

    ``pages`` is the mapping table (see ``planner.window_map``): page 1 of the result is
    ``pages[0]`` of the original, page 2 is ``pages[1]``, and so on.  A contiguous run is
    cut in one operation -- which is also how ``page_sizes`` measured it, so measuring and
    uploading agree -- while a selection that jumps (``2,4-6``) is assembled page by page.
    Nothing is written to disk; an empty mapping has no document to return.
    """
    if not pages:
        return None
    fitz = _fitz()
    if fitz is None:
        return None
    try:
        with fitz.open(str(path)) as doc:
            first = pages[0]
            if pages == list(range(first, first + len(pages))):
                return _crop(fitz, doc, first, pages[-1])
            out = fitz.open()
            try:
                for page in pages:
                    out.insert_pdf(doc, from_page=page - 1, to_page=page - 1)
                return out.tobytes(deflate=True, garbage=3)
            finally:
                out.close()
    except Exception as exc:
        log.warn(f"could not cut pages {pages} out of {path.name}: {exc}")
        return None


def _crop(fitz, doc, start: int, end: int) -> bytes:
    """One page range of an already-open document, serialized.

    ``deflate`` and ``garbage=3`` are the flags the planner's own measurements were
    taken with, and they only ever shrink what travels, so measuring and uploading
    agree byte for byte.
    """
    out = fitz.open()
    try:
        out.insert_pdf(doc, from_page=start - 1, to_page=end - 1)
        return out.tobytes(deflate=True, garbage=3)
    finally:
        out.close()


def pdf_name(name: str) -> str:
    """A name the endpoint accepts as a PDF.

    It reads the file type off the name it is handed, so a source called ``2308.04079``
    comes back as ``unsupported file type`` however PDF-shaped its bytes are.  The name
    is also what the job materialises as, so normalising here fixes both at once.
    """
    return name if name.lower().endswith(".pdf") else f"{name}.pdf"


def probe(value: str) -> Source:
    if looks_like_url(value):
        name = os.path.basename(urlparse(value).path) or "download"
        return Source(value=value, kind="url", name=pdf_name(name))
    path = Path(value).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"no such file: {value}")
    size_mb = path.stat().st_size / (1024 * 1024)
    pages = page_count(path)
    log.debug(f"probed {path.name}: {pages if pages is not None else '?'} pages, {size_mb:.2f} MB")
    return Source(value=str(path), kind="file", name=pdf_name(path.name),
                  pages=pages, size_mb=size_mb)


def materialise(client: EndpointClient, value: str) -> str:
    """Return a local path for ``value``; a URL is fetched once and kept there.

    The file is named after the URL's own basename, so a ``-u`` run and a run on
    the downloaded path produce the same job and product names; the hash directory
    keeps two URLs that share a basename apart.
    """
    if not looks_like_url(value):
        return value
    name = os.path.basename(urlparse(value).path) or "download"
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
    target = paths.ensure(paths.sources_dir() / digest / name)
    log.info(f"fetching {value}")
    raw = client.download(value)
    target.write_bytes(raw)
    log.info(f"saved {len(raw) / (1024 * 1024):.1f} MB -> {target}")
    return str(target)
