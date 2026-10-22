"""The single network exit of the skill.

Deliberate choices, each one paid for by an earlier failure:

* **No official SDK.**  The SDK's ``get_batch`` re-downloads the whole zip every
  time it sees ``done`` (~0.94MB per call), and its error handling calls
  ``raise_for_status()`` before looking at the body, so a 401 escapes as a raw
  ``httpx`` exception.  Both are avoided by speaking to the documented endpoints.
* **stdlib only.**  ``urllib.request`` keeps the skill dependency-free, which
  matters because the endpoint packages are gone from this machine.
* **PUT carries no ``Content-Type``.**  The upload URL is an Aliyun OSS presigned
  URL whose signature does not cover that header; sending it yields
  ``403 SignatureDoesNotMatch``.  The docs say so explicitly and a test pins it.
* **State probes are cheap.**  ``poll_batch`` hits the bare batch endpoint; the zip
  is downloaded only when products are actually wanted.
"""
from __future__ import annotations

import http.client
import json
import os
import ssl
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from ..util import log
from . import errors
from .errors import ApiError
from .models import FlashState, ItemState, LinkBatch


PRECISION_BASE = "https://mineru.net/api/v4"
FLASH_BASE = "https://mineru.net/api/v1/agent"


@lru_cache(maxsize=1)
def ssl_context() -> ssl.SSLContext:
    """A verifying context that actually finds a CA bundle.

    A stock homebrew/python.org interpreter on this machine has no usable default
    trust store, so a bare ``urlopen`` fails every HTTPS call with
    ``CERTIFICATE_VERIFY_FAILED``.  Order: an explicit env override, then certifi
    (already present as a dependency of the HTTP libraries we do not use), then the
    interpreter's own default.  Verification is never disabled.
    """
    for env_var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        candidate = os.environ.get(env_var)
        if candidate and os.path.exists(candidate):
            return ssl.create_default_context(cafile=candidate)
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        log.debug("certifi not installed; relying on the interpreter's default trust store")
        return ssl.create_default_context()


class EndpointClient(Protocol):
    """The seam that makes the adaptive scheduler testable without a network."""

    def request_links(self, body: dict[str, Any]) -> LinkBatch: ...

    def upload(self, url: str, path: Path) -> int: ...

    def upload_bytes(self, url: str, data: bytes) -> int: ...

    def poll_batch(self, batch_id: str) -> list[ItemState]: ...

    def create_flash_task(self, payload: dict[str, Any]) -> tuple[str, str]: ...

    def poll_flash(self, task_id: str) -> FlashState: ...

    def request_url_batch(self, body: dict[str, Any]) -> str: ...

    def create_flash_url_task(self, payload: dict[str, Any]) -> str: ...

    def download(self, url: str) -> bytes: ...


class HttpEndpoint:
    """HTTP implementation of :class:`EndpointClient`."""

    def __init__(
        self,
        token: str | None = None,
        request_timeout: int = 60,
        upload_timeout: int = 300,
        precision_base: str = PRECISION_BASE,
        flash_base: str = FLASH_BASE,
    ) -> None:
        self.token = token
        self.request_timeout = request_timeout
        self.upload_timeout = upload_timeout
        self.precision_base = precision_base.rstrip("/")
        self.flash_base = flash_base.rstrip("/")

    # -- low level --------------------------------------------------------- #
    def _open(self, url: str, data: bytes | None, headers: dict[str, str], timeout: int,
              method: str) -> tuple[int, bytes]:
        if method == "PUT" and data is not None:
            return self._put_raw(url, data, timeout)
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=ssl_context()) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()
        except Exception as exc:  # URLError, timeout, socket errors
            raise errors.network_error(exc, f"{method} {url.split('?')[0]}") from None

    def _put_raw(self, url: str, data: bytes, timeout: int) -> tuple[int, bytes]:
        """PUT with byte-exact control over the request headers.

        ``urllib`` silently appends ``Content-Type: application/x-www-form-urlencoded``
        to any request that carries a body.  The signed upload URL does not cover that
        header, so the upload comes back ``403 SignatureDoesNotMatch`` -- observed, and
        the reason the docs say "do not set Content-Type when uploading".  ``http.client``
        sends exactly what it is given, so the header never appears.
        """
        parts = urlsplit(url)
        path = parts.path + (f"?{parts.query}" if parts.query else "")
        if parts.scheme == "https":
            connection: http.client.HTTPConnection = http.client.HTTPSConnection(
                parts.netloc, timeout=timeout, context=ssl_context())
        else:
            connection = http.client.HTTPConnection(parts.netloc, timeout=timeout)
        try:
            connection.request("PUT", path, body=data,
                               headers={"Content-Length": str(len(data))})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def _json(self, url: str, method: str, payload: dict[str, Any] | None,
              auth: bool, timeout: int | None = None) -> dict[str, Any]:
        headers = {"Accept": "*/*"}
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if auth:
            if not self.token:
                raise ApiError(errors.Action.BAD_TOKEN, "", "no token available for precision endpoints")
            headers["Authorization"] = f"Bearer {self.token}"
        status, raw = self._open(url, body, headers, timeout or self.request_timeout, method)
        return errors.parse(status, raw)

    # -- precision --------------------------------------------------------- #
    def request_links(self, body: dict[str, Any]) -> LinkBatch:
        """Ask for signed upload URLs. One request carries at most 50 files.

        ``body`` is the whole request payload (``{"files": [...], ...}``) -- the
        endpoint rejects a doubly nested ``files`` field with ``-10002 type mismatch``,
        so the caller builds the body and this method only transports it.
        """
        data = self._json(f"{self.precision_base}/file-urls/batch", "POST", body, auth=True)
        batch_id = str(data.get("batch_id", ""))
        urls = [str(u) for u in (data.get("file_urls") or [])]
        expected = len(body.get("files") or [])
        if not batch_id or len(urls) != expected:
            raise ApiError(errors.Action.UNKNOWN, "",
                           f"link request returned {len(urls)} url(s) for {expected} file(s)")
        log.debug(f"{len(urls)} upload link(s) issued for batch {batch_id}")
        return LinkBatch(batch_id=batch_id, file_urls=urls)

    def request_url_batch(self, body: dict[str, Any]) -> str:
        """Submit URLs for the server to fetch itself -- no upload involved.

        A URL input never touches ``file-urls/batch``: the server downloads it, which
        is why foreign hosts that time out produce ``-60008`` instead of an error at
        submission time.  Like ``request_links``, this transports a body the caller
        built -- nesting ``files`` twice earns ``-10002 type mismatch``.
        """
        data = self._json(f"{self.precision_base}/extract/task/batch", "POST", body, auth=True)
        batch_id = str(data.get("batch_id", ""))
        if not batch_id:
            raise ApiError(errors.Action.UNKNOWN, "", "url batch submission returned no batch_id")
        return batch_id

    def poll_batch(self, batch_id: str) -> list[ItemState]:
        data = self._json(
            f"{self.precision_base}/extract-results/batch/{batch_id}", "GET", None, auth=True)
        items = data.get("extract_result") or []
        out: list[ItemState] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            out.append(ItemState(
                file_name=str(item.get("file_name", "")),
                state=str(item.get("state", "")),
                err_msg=str(item.get("err_msg") or ""),
                zip_url=item.get("full_zip_url") or None,
            ))
        return out

    # -- flash ------------------------------------------------------------- #
    def create_flash_task(self, payload: dict[str, Any]) -> tuple[str, str]:
        data = self._json(f"{self.flash_base}/parse/file", "POST", payload, auth=False)
        task_id = str(data.get("task_id", ""))
        file_url = str(data.get("file_url", ""))
        if not task_id or not file_url:
            raise ApiError(errors.Action.UNKNOWN, "", "flash task creation returned an unexpected payload")
        return task_id, file_url

    def create_flash_url_task(self, payload: dict[str, Any]) -> str:
        """Flash equivalent for a URL: the server fetches it, we only get a task id."""
        data = self._json(f"{self.flash_base}/parse/url", "POST", payload, auth=False)
        task_id = str(data.get("task_id", ""))
        if not task_id:
            raise ApiError(errors.Action.UNKNOWN, "", "flash url task creation returned no task_id")
        return task_id

    def poll_flash(self, task_id: str) -> FlashState:
        data = self._json(f"{self.flash_base}/parse/{task_id}", "GET", None, auth=False)
        return FlashState(
            task_id=task_id,
            state=str(data.get("state", "")),
            markdown_url=data.get("markdown_url") or None,
            err_msg=str(data.get("err_msg") or ""),
            err_code=str(data.get("err_code") or ""),
        )

    # -- transfer ---------------------------------------------------------- #
    def upload(self, url: str, path: Path) -> int:
        """PUT a file's bytes. No ``Content-Type`` -- see the module docstring."""
        return self.upload_bytes(url, path.read_bytes())

    def upload_bytes(self, url: str, data: bytes) -> int:
        """PUT bytes that are already in hand -- a page window, never a file on disk."""
        body = data
        status, raw = self._open(url, body, {}, self.upload_timeout, "PUT")
        if status >= 300:
            text = raw[:300].decode("utf-8", "replace")
            if "SignatureDoesNotMatch" in text:
                raise ApiError(errors.Action.UNKNOWN, "oss-signature",
                               "the signed upload URL rejected the request signature "
                               "(a header outside the signature was sent)", status)
            raise ApiError(errors.classify("", status), "", text, status)
        return len(body)

    def download(self, url: str) -> bytes:
        status, raw = self._open(url, None, {}, self.upload_timeout, "GET")
        if status >= 300:
            raise ApiError(errors.classify("", status), "", "download failed", status)
        return raw
