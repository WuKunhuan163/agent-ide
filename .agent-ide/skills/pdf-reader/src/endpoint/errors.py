"""Two error envelopes, one decision table.

The service answers business failures with HTTP 200 and ``{"code": ..., "msg": ...}``
but authentication failures with **HTTP 401** and
``{"traceId": ..., "msgCode": "A0211", "msg": ..., "success": false}``.  A client
that only parses the first shape reports a raw HTTP exception for the second, which
is exactly why the archived tool's ``AuthError`` never fired.

Here both shapes collapse into one :class:`ApiError`, and every error is mapped to
an :class:`Action` -- what the scheduler is allowed to do about it.
"""
from __future__ import annotations

import json
import re
from enum import Enum
from typing import Any


class Action(str, Enum):
    OK = "ok"
    NETWORK = "network"                    # transport failed before the server answered
    RETRY_BACKOFF = "retry_backoff"        # -60009 queue full, 429 ip-throttled
    SPLIT_REQUIRED = "split_required"      # -60006 page limit
    INPUT_REJECT = "input_reject"          # -60002 bad type, -60005 too large
    QUOTA_STOP = "quota_stop"              # -60018 / -60019 daily quota
    BAD_TOKEN = "bad_token"                # A0202 / A0211
    URL_UNREADABLE = "url_unreadable"      # -60008 foreign url timed out
    FLASH_LIMIT = "flash_limit"            # -30001..-30004
    ALREADY_DONE = "already_done"          # -60012 / -60014 expired or missing
    UNKNOWN = "unknown"


_CODE_ACTIONS: dict[str, Action] = {
    "-60002": Action.INPUT_REJECT,
    "-60005": Action.INPUT_REJECT,
    "-60006": Action.SPLIT_REQUIRED,
    "-60008": Action.URL_UNREADABLE,
    "-60009": Action.RETRY_BACKOFF,
    "-60012": Action.ALREADY_DONE,
    "-60014": Action.ALREADY_DONE,
    "-60018": Action.QUOTA_STOP,
    "-60019": Action.QUOTA_STOP,
    "-10001": Action.RETRY_BACKOFF,
    "A0202": Action.BAD_TOKEN,
    "A0211": Action.BAD_TOKEN,
    "-30001": Action.FLASH_LIMIT,        # the file is too large for flash
    "-30002": Action.FLASH_LIMIT,
    "-30003": Action.SPLIT_REQUIRED,     # too many pages -- fewer pages *would* work
    "-30004": Action.FLASH_LIMIT,
}

#: What the caller should be told, phrased as an instruction rather than a code.
_ADVICE: dict[Action, str] = {
    Action.NETWORK: "no answer from the endpoint; check connectivity and certificates, then retry",
    Action.RETRY_BACKOFF: "server is busy or rate-limiting; backing off",
    Action.SPLIT_REQUIRED: "file exceeds the page limit; splitting by page range and resubmitting",
    Action.INPUT_REJECT: "the endpoint refused this file; fix or drop it (no retry will help)",
    Action.QUOTA_STOP: "daily quota reached; stop submitting and come back tomorrow",
    Action.BAD_TOKEN: "token rejected or expired; run `keys set <token>` (do not loop)",
    Action.URL_UNREADABLE: "the endpoint could not fetch this URL; upload it locally instead",
    Action.FLASH_LIMIT: "flash limit hit; split, convert, or switch to precision with a token",
    Action.ALREADY_DONE: "task is missing or expired on the server side",
    Action.UNKNOWN: "unrecognised error from the endpoint",
}


class ApiError(Exception):
    """One error class for both envelopes, carrying an actionable verdict."""

    def __init__(self, action: Action, code: str, message: str,
                 http_status: int | None = None) -> None:
        self.action = action
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(self.describe())

    def describe(self) -> str:
        parts = [f"{self.action.value}"]
        if self.code:
            parts.append(f"code={self.code}")
        if self.http_status:
            parts.append(f"http={self.http_status}")
        return f"{' '.join(parts)}: {self.message} ({_ADVICE.get(self.action, '')})"

    @property
    def advice(self) -> str:
        return _ADVICE.get(self.action, "")

    @property
    def retryable(self) -> bool:
        return self.action in (Action.RETRY_BACKOFF, Action.NETWORK)

    @property
    def should_split(self) -> bool:
        return should_split(self.action)


def should_split(action: Action) -> bool:
    """Whether asking for a smaller page window can rescue this failure.

    A page-limit refusal can be rescued that way obviously.  A flash *size* refusal
    can too: the page count is unknown precisely when the file arrived whole (a URL,
    or no PyMuPDF), so asking for one window is the only honest way to find out how
    much of it the lightweight channel will take.
    """
    return action in (Action.SPLIT_REQUIRED, Action.FLASH_LIMIT)


def classify(code: str, http_status: int | None = None) -> Action:
    if code in _CODE_ACTIONS:
        return _CODE_ACTIONS[code]
    if http_status == 429:
        return Action.RETRY_BACKOFF
    if http_status in (401, 403):
        return Action.BAD_TOKEN
    if http_status is not None and http_status >= 500:
        return Action.RETRY_BACKOFF
    return Action.UNKNOWN


def parse(status: int, body: bytes) -> dict[str, Any]:
    """Return the ``data`` payload of a successful reply, or raise :class:`ApiError`.

    Never raises for an HTTP error status -- the body is the interesting part, so it
    is read and classified instead of being turned into a transport exception.
    """
    text = body.decode("utf-8", "replace") if body else ""
    payload: Any = None
    if text.strip():
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None

    if not isinstance(payload, dict):
        if 200 <= status < 300:
            return {}
        raise ApiError(classify("", status), "", (text[:300] or "empty reply"), status)

    code = str(payload.get("code", "")) if "code" in payload else ""
    msg_code = str(payload.get("msgCode", "")) if "msgCode" in payload else ""
    message = str(payload.get("msg") or payload.get("message") or "").strip()

    if 200 <= status < 300 and code in ("", "0"):
        data = payload.get("data")
        return data if isinstance(data, dict) else {"data": data}

    # authentication envelope: HTTP 401 + msgCode, no `code` field at all
    effective = msg_code or code
    action = classify(effective, status)
    if effective and effective not in _CODE_ACTIONS and 200 <= status < 300:
        # a business failure: honour its own code even if we do not know it
        action = classify(effective, None)
    raise ApiError(action, effective, message or f"request failed with {effective!r}", status)


def network_error(exc: Exception, what: str) -> ApiError:
    return ApiError(Action.NETWORK, "network", f"{what}: {type(exc).__name__}: {exc}")


_CODE_IN_TEXT = re.compile(r"(-?\d{5}|A\d{4})")


def action_from_message(message: str) -> Action:
    """Classify a per-file failure reported as free text.

    Batch results carry only ``{file_name, state, err_msg, full_zip_url}`` -- there is
    no error *code* per file, so the code has to be recovered from the message when the
    service happens to include one, and otherwise from the wording.  Order matters
    here: a page-limit message that also happens to say "上限" must stay a split, and
    a quota refusal must be recognised as fatal even though it says nothing about
    "quota" -- its published wording is a count of tasks, not of pages.
    """
    if not message:
        return Action.UNKNOWN
    match = _CODE_IN_TEXT.search(message)
    if match:
        return classify(match.group(1), None)
    lowered = message.lower()
    if "page" in lowered and ("limit" in lowered or "exceed" in lowered) or "页数" in message:
        return Action.SPLIT_REQUIRED
    if "size" in lowered and ("limit" in lowered or "large" in lowered) or "大小" in message:
        return Action.INPUT_REJECT
    if "queue" in lowered or "busy" in lowered or "队列" in message or "稍后" in message:
        return Action.RETRY_BACKOFF
    if "quota" in lowered or "额度" in message or "已达上限" in message or "明日再来" in message:
        return Action.QUOTA_STOP
    if "url" in lowered or "链接" in message:
        return Action.URL_UNREADABLE
    if "token" in lowered or "auth" in lowered or "鉴权" in message or "登录" in message:
        return Action.BAD_TOKEN
    return Action.UNKNOWN
