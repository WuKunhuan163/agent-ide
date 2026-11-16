"""AutoDL Container Instance Pro API: one token, nine endpoints, one envelope.

This file is responsible for three things: where the credential comes from, how a request is sent, and how a failure is classified.

The envelope is the only authority: failures also come back as HTTP 200, so "the call succeeded" cannot be read off the status line.
Two documented pitfalls are dealt with here once -- `snapshot`/`status` are marked GET but need a body, so they are always sent as
query parameters; the token goes into `Authorization` verbatim, and adding `Bearer ` is the most common 401 here.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

OK = 0
FAILED = 1
USAGE = 2
NO_TOKEN = 3
AUTH = 4
NOT_FOUND = 5
API = 6
NET = 7
NO_ENTITLEMENT = 8
SSH = 9

DEFAULT_BASE_URL = "https://api.autodl.com"
# One host, one token. The deployment docs say up front: the HOST is https://api.autodl.com,
# and the token is under "console -> settings -> developer token", the same one Pro uses. Measured: one token works for
# `instance/pro/list` and for `machine/region/gpu_stock`; private.autodl.com is not the developer API
# (/instance/pro/list is a 404 there, and the stock path answers "login timed out") -- do not send there.
ELASTIC_BASE_URL = "https://api.autodl.com"   # name kept: this is the deployment base, not another cloud
TIMEOUT = 30.0

CREATE = "/api/v1/dev/instance/pro/create"
SNAPSHOT = "/api/v1/dev/instance/pro/snapshot"
STATUS = "/api/v1/dev/instance/pro/status"
LIST = "/api/v1/dev/instance/pro/list"
POWER_ON = "/api/v1/dev/instance/pro/power_on"
POWER_OFF = "/api/v1/dev/instance/pro/power_off"
RELEASE = "/api/v1/dev/instance/pro/release"
IMAGE_SAVE = "/api/v1/dev/instance/pro/image/save"
IMAGE_LIST = "/api/v1/dev/instance/pro/image/private/list"

# Stock (the deployment side, not the instance side): idle/total per model, by region. Both live on the private cloud.
STOCK_REGION = "/api/v1/dev/machine/region/gpu_stock"   # POST, filterable by region
STOCK_ALL = "/api/v1/dev/machine/gpu_stock"             # GET, no parameters, everything

# The compute market: this is what the console "compute market" table uses, and it **needs no token** (prices are visible signed out).
# The developer API has no quote endpoint; prices exist only here. It returns per host: whole-machine price plus the enable_container_pro flag.
MARKET = "/api/v1/machine/list"

TOKEN_STEPS = "console -> settings -> developer token"

# Envelope codes meaning "the credential did not pass": only these deserve a local diagnosis in the error.
AUTH_CODES = {"AuthorizeFailed", "Unauthorized", "InvalidToken", "TokenExpired"}


class CliError(Exception):
    """One failure, carrying its exit code and a way to fix it."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


class ApiError(CliError):
    """Envelope with ``code != "Success"``. request_id is the only field official support can trace."""

    def __init__(self, code_name: str, message: str, request_id: str, path: str) -> None:
        detail = f"{path} refused: {code_name}: {message or 'no message'}"
        if request_id:
            detail += f" (request_id {request_id})"
        super().__init__(API, detail)
        self.request_id = request_id
        self.code_name = code_name
        self.message = message
        self.path = path


class NoEntitlement(CliError):
    """`BadRequest: no access to the current resource` -- an account-by-product gate, not a parameter problem and not missing verification.

    The evidence chain (each item measured; the order is the order the server decides in):
    1. `{}` with a required field missing -> `RequestParameterIsWrong`; `disk 9999` likewise. So parameter validation runs first.
    2. A spec id that does not exist / an image that does not exist / a region that does not exist -> all return **the same sentence**. Three different
       things sharing one wording can only mean a single gate ahead of them, not a lookup failing per resource.
    3. The decisive one: `autodl await` caught a genuinely idle Pro `4090D` in the market, ordered immediately, and was
       refused with that same sentence. So it is not "no allocatable capacity" either.

    Conclusion: the gate admits by account plus product, and has nothing to do with verification, capacity or request parameters. Only
    AutoDL can change it (support / console).
    """

    LABEL = "no developer-API entitlement (NO_ENTITLEMENT)"

    def __init__(self, code_name: str, message: str, request_id: str, path: str) -> None:
        detail = (f"{self.LABEL}: AutoDL refused {path} ({code_name}: {message}); "
                  f"this is an account-by-product gate -- not parameters, not verification, not a card shortage. "
                  f"A spec, image or region that does not exist all answer with the same sentence, and create is still refused after "
                  f"the market reports an idle Pro card. Waiting for a card will not help: AutoDL has to enable "
                  f"the Container Instance Pro Open API for this account. Give support the request_id")
        if request_id:
            detail += f" (request_id {request_id})"
        super().__init__(NO_ENTITLEMENT, detail)
        self.request_id = request_id
        self.code_name = code_name
        self.message = message
        self.path = path


# --------------------------------------------------------------------------- credentials
# All configuration lives under data/ and is read from files only, never from the environment: data/credentials.json holds the token,
# data/config.json may hold a base_url (official by default). Whichever shell you run from, the answer is the same.

def data_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def credentials_file() -> str:
    return os.path.join(data_dir(), "credentials.json")


def config_file() -> str:
    return os.path.join(data_dir(), "config.json")


def _read_json(path: str, label: str, code: int = NO_TOKEN) -> dict:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise CliError(code, f"{label} is not valid JSON: {path} ({exc})") from None
    except OSError as exc:
        raise CliError(code, f"{label} is unreadable: {path} ({exc})") from None
    if not isinstance(data, dict):
        raise CliError(code, f"{label} must be an object: {path}")
    return data


def _read_file() -> dict:
    return _read_json(credentials_file(), "data/credentials.json")


def load() -> dict:
    """token / account / defaults, taken only from data/credentials.json.

    Only one kind of token works on the developer API: the console "developer token" (`aud=develop_api`).
    Pro and deployment share it; the difference is **account entitlement**, not credential type:

    | Product line | Needs |
    |---|---|
    | Container Instance Pro | personal verification or enterprise certification |
    | Deployment (deployment / container) | enterprise certification |
    | Deployment GPU stock | an ordinary token is enough (measured; this tool relies on it) |

    Two token-shaped things must not be stored either: the web login state (the developer API refuses it outright; storing it only
    manufactures a fake "login timed out" on the next call), and any alias table. An old file with `tokens.pro`
    or `tokens.elastic` reads as the same token (writing flattens it into a single `token` field).
    """
    data = _read_file()
    defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
    token = str(data.get("token") or "").strip()
    if not token and isinstance(data.get("tokens"), dict):
        slots = data["tokens"]
        token = str(slots.get("pro") or slots.get("elastic") or "").strip()
    return {
        "token": token,
        "account": str(data.get("account") or "").strip(),
        "defaults": dict(defaults),
    }


def require_token() -> str:
    token = load()["token"]
    if token:
        return token
    raise CliError(
        NO_TOKEN,
        f"no token in {credentials_file()}; get one at autodl.com -> {TOKEN_STEPS}",
    )


def masked(token: str) -> str:
    """Recognisable, unusable."""
    if not token:
        return "(none)"
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}...{token[-4:]}"


def token_aud(token: str) -> str | None:
    """Read the `aud` of a local JWT: no signature check, nothing printed. Only to tell "wrong credential type" from "credential expired"."""
    parts = token.split(".")
    if len(parts) < 2:
        return None
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, TypeError):
        return None
    aud = claims.get("aud") if isinstance(claims, dict) else None
    return str(aud) if aud else None


def verify_token(token: str) -> None:
    """Make one real read-only call with this token: if it does not pass, nothing is written.

    The instance list is the lowest bar (no Pro verification, no billing action). 401/403 raises AUTH
    (wrong token), an envelope that is not Success raises ApiError (token fine, account refused), an unreachable network raises NET.
    None of the three writes to disk, and "stored" is never taken as "verified".
    """
    Client(token).call("POST", LIST, {"page_index": 1, "page_size": 1})


def store_token(token: str) -> str:
    """Write with 0600, keeping the other hand-written fields. verify_token must run first."""
    token = token.strip()
    if not token:
        raise CliError(NO_TOKEN, "refusing to store an empty token")
    path = credentials_file()
    data = _read_file() or {"account": "",
                            "defaults": {"gpu_spec": "", "image": "", "cuda": 118, "region": ""}}
    data.pop("tokens", None)   # flatten: there used to be a slot per cloud, now there is one token
    data["token"] = token
    os.makedirs(data_dir(), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.chmod(path, 0o600)
    return path


def default(key: str, fallback=None):
    return load()["defaults"].get(key) or fallback


# --------------------------------------------------------------------------- requests

def base_url() -> str:
    # base_url from data/config.json: point the address at a proxy or a local stub; otherwise the official one.
    data = _read_json(config_file(), "data/config.json", USAGE)
    return str(data.get("base_url") or DEFAULT_BASE_URL).rstrip("/")


def setting(key: str, fallback=None):
    """Top-level keys of data/config.json: non-secret, committable, identical across shells."""
    data = _read_json(config_file(), "data/config.json", USAGE)
    value = data.get(key)
    return fallback if value is None or value == "" else value


def stock_base_url() -> str:
    """Stock lives on the same host (the deployment docs give api.autodl.com as the HOST).

    stock_base_url is still readable only to point at a proxy or a local stub; do not use it to switch "another cloud",
    because there is no other cloud.
    """
    return str(setting("stock_base_url", base_url())).rstrip("/")


class Client:
    def __init__(self, token: str, transport=None) -> None:
        token = (token or "").strip()
        if not token:
            raise CliError(AUTH, "empty token")
        self.token = token
        self._transport = transport or _urllib_transport

    def call(self, method: str, path: str, body: dict | None = None, base: str | None = None):
        """Send one request and return the envelope data. base only points the address at a proxy or a stub."""
        method = method.upper()
        url = (base or base_url()) + path
        token = self.token
        payload: bytes | None = None
        if body:
            if method == "GET":
                url += ("&" if "?" in url else "?") + urllib.parse.urlencode(body)
            else:
                payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"Authorization": token, "Content-Type": "application/json",
                   "Accept": "application/json"}
        status, text = self._transport(method, url, headers, payload)
        try:
            return _interpret(method, path, status, text)
        except ApiError as exc:
            # AuthorizeFailed carries "login timed out, please sign in again", which does not say which layer failed.
            # The aud is readable locally: under one and the same error, a wrong credential type and an expired one need completely different next steps.
            if exc.code_name in AUTH_CODES:
                raise ApiError(exc.code_name, f"{exc.message}; {self._hint(token)}", exc.request_id, path) from None
            if "no access to the current resource" in exc.message or "无当前资源访问权限" in exc.message:
                # Token is valid (balance and stock both answer) but the account layer did not pass: Pro needs personal verification or enterprise
                # certification, and deployment containers need enterprise certification. Nothing to do with cards, regions or specs, so retrying is pointless.
                # A separate exit code 8 lets the caller say "not verified" instead of relaying the server sentence.
                raise NoEntitlement(exc.code_name, exc.message, exc.request_id, path) from None
            raise

    def _hint(self, token: str) -> str:
        aud = token_aud(token)
        if not aud:
            return f"not a signed token (no aud claim): copy the string itself from {TOKEN_STEPS}"
        if aud == "develop_api":
            # The docs state: Pro needs personal verification or enterprise certification; an unverified account is refused even with a valid token,
            # and the server says "login timed out", which does not reveal that it is a verification problem.
            return (f"aud={aud} (Pro developer token), right type but rejected: regenerate it at {TOKEN_STEPS}; "
                    f"a fresh one failing the same way means the account is not verified "
                    f"(Pro needs personal verification or enterprise certification)")
        return (f"aud={aud}: not a developer-API token; a browser login token looks the same shape "
                f"but is refused here — take the string from {TOKEN_STEPS}")


def anonymous_json(path: str, body: dict) -> dict:
    """POST once without a token and return the envelope data. Public endpoints only (the compute market).

    The market endpoint is public, the same one the console uses: readable signed out, so no token is read and no
    Authorization is sent -- asking with a bad token can get you a 401 instead.
    """
    status, text = _urllib_transport(
        "POST", base_url() + path, {"Content-Type": "application/json"},
        json.dumps(body, ensure_ascii=False).encode("utf-8"))
    try:
        envelope = json.loads(text or "{}")
    except json.JSONDecodeError:
        raise CliError(API, f"POST {path} returned non-JSON (HTTP {status}): {text[:120]}") from None
    if envelope.get("code") != "Success":
        raise CliError(API, f"POST {path} refused: {envelope.get('code')}: {envelope.get('msg')}")
    return envelope.get("data") or {}


def _urllib_transport(method: str, url: str, headers: dict, payload: bytes | None):
    request = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        raise CliError(NET, f"{method} {url} could not reach AutoDL: {getattr(exc, 'reason', exc)}") from None
    except TimeoutError:
        raise CliError(NET, f"{method} {url} timed out after {TIMEOUT:.0f}s") from None


def _interpret(method: str, path: str, status: int, text: str):
    if status in (401, 403):
        raise CliError(
            AUTH,
            f"{method} {path} rejected the token (HTTP {status}); "
            "paste it verbatim, without a 'Bearer ' prefix, and regenerate it if it is old",
        )
    if status == 404:
        raise CliError(NOT_FOUND, f"{method} {path} is not an endpoint on this host (HTTP 404)")
    if status >= 400:
        raise CliError(API, f"{method} {path} failed with HTTP {status}: {text[:300].strip()}")
    try:
        envelope = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        raise CliError(API, f"{method} {path} returned something that is not JSON: {text[:200]!r}") from None
    if not isinstance(envelope, dict):
        raise CliError(API, f"{method} {path} returned {type(envelope).__name__}")
    if envelope.get("code") != "Success":
        raise ApiError(str(envelope.get("code") or "unknown"), str(envelope.get("msg") or ""),
                       str(envelope.get("request_id") or ""), f"{method} {path}")
    return envelope.get("data")
