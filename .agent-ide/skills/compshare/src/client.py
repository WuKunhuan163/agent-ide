"""Compshare (UCloud) API client: UCloud v1 signing, one function per action.

Signing rules (UCloud-wide):
  1. Drop empty params (Action and PublicKey included), sort the rest by key
  2. Concatenate key1value1key2value2..., append PrivateKey at the end
  3. Lowercase hex SHA1 of that string is the Signature

The request body is form-urlencoded, not JSON. Every response carries RetCode and
0 means success. On non-zero, Message is the only useful field: it is raised as
is, with no second-guessing.

## Return codes seen in practice

Only these have actually been observed. Anything else surfaces as
`RetCode + Message`, verbatim, with no speculative translation.

| RetCode | Message fragment | Trigger | Correct response |
|---|---|---|---|
| 170 | `Missing Signature` | request carried no Signature | signing never ran, or params were empty |
| 171 | `Signature VerifyAC Error` | wrong public or private key | check `data/credentials.json`; a single `sk-` key is not this credential set |
| 161 | `Action [X] not found` | misspelled Action | the image list is plural `DescribeCompShareImages`; rename is `ModifyCompShareInstanceName` (`ModifyUHostInstanceName` exists but only returns 8433); pricing is `GetCompShareInstancePrice` (any `Describe*` prefix lands on 161) |
| 210 | `Missing params [X]` | required param missing, or an array was not indexed | arrays are always `X.0`, `X.1` |
| 230 | `Params [X] not available` | param present but wrongly typed; sometimes comes with **200 + empty body** | index `Disks` / `UHostIds`; never pass a JSON string |
| 8333 | `cpu memory ratio not in 2:1 - 1:12` | CPU:memory out of range | use the combinations `types` returns |
| 8314 | `password must contain uppercase and lowercase letters, ...` | password policy | upper + lower + digit + symbol |
| 8433 | `Service error, please retry or contact technical support` | generic reply for an action aimed at the wrong layer (base UCloud vs CompShare) | confirm the Action belongs to the CompShare layer |
| — | `machine type not configured for zone` | that zone does not sell that card | not an error; `stock` skips it silently |
| — | `InstanceOperationInProgress` | the 10-minute per-instance lock is still held | wait for the lock; do not retry-hammer |

## An empty body is a trap

Passing `Disks` as a JSON string makes the server answer **HTTP 200 with an empty
body**. Reading the code alone suggests success; nothing happened. So any 200
whose body does not parse as JSON is raised as a failure (see `call()`) rather
than swallowed into an empty result.

## `RetCode -1 network: read timed out` -- suspect the timeout first

`DescribeCompShareInstance` was measured at **20.6 seconds** on an account with 13
instances, and the client default used to be 20s, so "a list request that would
have succeeded" was judged a network failure, after which every command blamed
the API. The default is 60s now (`COMPSHARE_TIMEOUT` overrides it). On a fresh
`-1 network`: first check whether this particular call was slow, then rule the
network out with `curl -o /dev/null -w "%{http_code}" --max-time 20 https://api.compshare.cn`.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.compshare.cn"
SKILL_DIR = Path(__file__).resolve().parent.parent
CRED_FILE = SKILL_DIR / "data" / "credentials.json"

CRED_URL = "https://console.compshare.cn/uaccount/api_manage"
CRED_HELP = ("put {\"public_key\": \"...\", \"private_key\": \"...\"} into "
             f"{CRED_FILE} (from console.compshare.cn -> Account Center -> API Keys)")


class ApiError(Exception):
    def __init__(self, code, message, action=""):
        super().__init__(f"{action or 'api'}: RetCode {code} {message}".strip())
        self.code = code
        self.message = message
        self.action = action


class NoCredentials(Exception):
    pass


def open_cred_page() -> bool:
    """Bring the key-creation page to the front when credentials are missing.
    Returns False on failure and never changes the exit code.

    Nothing opens when COMPSHARE_NO_OPEN=1: the panel and watch polling would
    trigger it over and over and steal focus each time.
    """
    if os.environ.get("COMPSHARE_NO_OPEN") == "1":
        return False
    try:
        import subprocess
        subprocess.run(["open", CRED_URL] if sys.platform == "darwin"
                       else ["xdg-open", CRED_URL],
                       check=False, timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def credentials() -> tuple[str, str]:
    env_pub, env_priv = os.environ.get("COMPSHARE_PUBLIC_KEY"), os.environ.get("COMPSHARE_PRIVATE_KEY")
    if env_pub and env_priv:
        return env_pub, env_priv
    if CRED_FILE.exists():
        try:
            d = json.loads(CRED_FILE.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise NoCredentials(f"{CRED_FILE} is unreadable ({exc}); {CRED_HELP}") from None
        if d.get("public_key") and d.get("private_key"):
            return d["public_key"], d["private_key"]
    raise NoCredentials(f"no API key; {CRED_HELP}")


def has_credentials() -> bool:
    try:
        credentials()
        return True
    except NoCredentials:
        return False


def sign(params: dict, private_key: str) -> str:
    items = sorted((k, v) for k, v in params.items() if v not in (None, ""))
    raw = "".join(f"{k}{v}" for k, v in items) + private_key
    return hashlib.sha1(raw.encode()).hexdigest()


DEFAULT_TIMEOUT = float(os.environ.get("COMPSHARE_TIMEOUT") or 60.0)


def call(action: str, *, public_key: str | None = None, private_key: str | None = None,
         timeout: float = DEFAULT_TIMEOUT, **params) -> dict:
    """Issue one request and return the `data` part. RetCode != 0 raises ApiError.

    The default timeout is 60s, not 20s: `DescribeCompShareInstance` was measured at
    20.6s on an account with 13 instances, and a 20s default turned a successful
    list request into a network failure, after which every command blamed the API.
    Use `COMPSHARE_TIMEOUT` for anything shorter or longer.
    """
    if public_key is None or private_key is None:
        public_key, private_key = credentials()
    payload = {k: v for k, v in params.items() if v is not None}
    payload["Action"] = action
    payload["PublicKey"] = public_key
    payload["Signature"] = sign(payload, private_key)

    body = urllib.parse.urlencode(payload, doseq=True).encode()
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ApiError(-1, f"network: {exc}", action) from None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ApiError(-1, f"not json: {raw[:200]!r}", action) from None

    code = data.get("RetCode")
    if code != 0:
        raise ApiError(code, data.get("Message") or "", action)
    return data
