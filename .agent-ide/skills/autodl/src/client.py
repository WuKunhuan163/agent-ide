"""AutoDL 容器实例 Pro API：一个 token，九个端点，一个信封。

这个文件只管三件事：凭证从哪来、请求怎么发、失败怎么分类。

信封是唯一权威：失败也走 HTTP 200，所以「调用成功」不能从状态行读出来。
两个文档坑在这里一次处理掉——`snapshot`/`status` 标 GET 却要带 body，一律改成
query 参数；token 原样放进 `Authorization`，加 `Bearer ` 是这里最常见的 401。
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
# 一个 host，一个 token。官方弹性部署文档开头就写：HOST 是 https://api.autodl.com，
# token 在「控制台 -> 设置 -> 开发者Token」，与 Pro 同一个。实测：同一个 token 既能
# `instance/pro/list`，也能 `machine/region/gpu_stock`；private.autodl.com 不是开发者 API
# （/instance/pro/list 那里是 404，库存路径则回「登陆超时」），别往那儿发。
ELASTIC_BASE_URL = "https://api.autodl.com"   # 名字留着：弹性部署的 base，不是另一朵云
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

# 库存（弹性部署那套，不是实例那套）：按区报每个型号的空闲/总量。两个都在私有云上。
STOCK_REGION = "/api/v1/dev/machine/region/gpu_stock"   # POST，可按区过滤
STOCK_ALL = "/api/v1/dev/machine/gpu_stock"             # GET，无参数，全量

# 算力市场：控制台「算力市场」那张表用的就是它，**不需要 token**（未登录也能看价格）。
# 开发者 API 里没有报价接口，价格只在这里；它按主机返回整机价 + enable_container_pro 标记。
MARKET = "/api/v1/machine/list"

TOKEN_STEPS = "控制台 -> 设置 -> 开发者Token"

# 信封里表示「凭据没通过」的 code：这些才值得在报错里补一句本地诊断
AUTH_CODES = {"AuthorizeFailed", "Unauthorized", "InvalidToken", "TokenExpired"}


class CliError(Exception):
    """一次失败，自带退出码和修复指引。"""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


class ApiError(CliError):
    """信封里 ``code != "Success"``。request_id 是官方支持唯一能追的字段。"""

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
    """`BadRequest: 无当前资源访问权限` —— 账号-产品闸门，不是参数问题，也不是没实名。

    证据链（每条都是实测，顺序就是服务端的判定顺序）：
    1. `{}` 缺必填 → `RequestParameterIsWrong`，`disk 9999` 同样。所以参数校验在最前面。
    2. 不存在的规格 id / 不存在的镜像 / 不存在的区 → 全部回**同一句**。三件不同的事共用
       一句文案，只能是它们之前还有一道统一的闸门，而不是逐个资源的查找失败。
    3. 最关键的一条：`autodl await` 抓到过市场里真实空闲的 Pro `4090D`，立刻下单，仍被
       同一句拒绝。所以也不是「没有可分配容量」。

    结论：这道闸门按账号+产品放行，与实名、与容量、与请求参数都无关。唯一能改它的是
    AutoDL 侧开通（客服 / 控制台）。
    """

    LABEL = "开发API无权限 (NO_ENTITLEMENT)"

    def __init__(self, code_name: str, message: str, request_id: str, path: str) -> None:
        detail = (f"{self.LABEL}: AutoDL 拒绝了 {path}（{code_name}: {message}）；"
                  f"这是账号-产品闸门，不是参数、不是实名、也不是没卡 —— 实测不存在的规格/镜像/区"
                  f"都回同一句，且市场报出空闲 Pro 卡后 create 仍被拒。等卡不会成功："
                  f"需要 AutoDL 为该账号开通「容器实例Pro 开放API」，把 request_id 给客服")
        if request_id:
            detail += f" (request_id {request_id})"
        super().__init__(NO_ENTITLEMENT, detail)
        self.request_id = request_id
        self.code_name = code_name
        self.message = message
        self.path = path


# --------------------------------------------------------------------------- 凭证
# 全部配置都在 data/ 下，只看文件，不读环境变量：data/credentials.json 填 token，
# data/config.json 放一个可选 base_url（默认官方地址）。谁在什么 shell 里跑都一样。

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
    """token / account / defaults，只从 data/credentials.json 来。

    只有一种 token 对开发者 API 有效：控制台的「开发者Token」（`aud=develop_api`）。
    Pro 与弹性部署共用它，差别在**账号权限**而不是凭据种类：

    | 产品线 | 需要 |
    |---|---|
    | 容器实例 Pro | 个人实名或企业认证 |
    | 弹性部署（部署/容器） | 企业认证 |
    | 弹性部署 GPU 库存 | 实测普通 token 即可（本工具正在用） |

    另外两种长得像 token 的东西都不该存：网页登录态（开发者 API 一律拒绝，存下来只会在
    下一次调用里制造一个假的「登录超时」），以及任何别名表。老文件中若有 `tokens.pro`
    或 `tokens.elastic`，读作同一个 token（写盘时会拍平成一个 `token` 字段）。
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
    """认得出来，用不了。"""
    if not token:
        return "(none)"
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}...{token[-4:]}"


def token_aud(token: str) -> str | None:
    """本地读 JWT 的 aud：不验签，也不打印任何内容。只为区分「凭据类型错」和「凭据已失效」。"""
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
    """拿这个 token 真打一次只读接口：过不了就不让写盘。

    实例列表是最低门槛（不需要 Pro 的实名，也不碰任何计费动作）。401/403 抛 AUTH
    （token 不对），信封非 Success 抛 ApiError（token 对但账号被拒），网络不通抛 NET。
    三种都不写盘，也不把「存下了」当成验证。
    """
    Client(token).call("POST", LIST, {"page_index": 1, "page_size": 1})


def store_token(token: str) -> str:
    """写入 0600，保留人写的其余字段。调用前必须先 verify_token。"""
    token = token.strip()
    if not token:
        raise CliError(NO_TOKEN, "refusing to store an empty token")
    path = credentials_file()
    data = _read_file() or {"account": "",
                            "defaults": {"gpu_spec": "", "image": "", "cuda": 118, "region": ""}}
    data.pop("tokens", None)   # 拍平：曾经按云分过槽，现在只有一种 token
    data["token"] = token
    os.makedirs(data_dir(), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.chmod(path, 0o600)
    return path


def default(key: str, fallback=None):
    return load()["defaults"].get(key) or fallback


# --------------------------------------------------------------------------- 请求

def base_url() -> str:
    # data/config.json 的 base_url：把地址指向代理或本地桩服务，没有就用官方地址
    data = _read_json(config_file(), "data/config.json", USAGE)
    return str(data.get("base_url") or DEFAULT_BASE_URL).rstrip("/")


def setting(key: str, fallback=None):
    """data/config.json 的顶层键：非机密、可提交、跨 shell 一致。"""
    data = _read_json(config_file(), "data/config.json", USAGE)
    value = data.get(key)
    return fallback if value is None or value == "" else value


def stock_base_url() -> str:
    """库存在同一个 host 上（官方弹性部署文档的 HOST 就是 api.autodl.com）。

    保留 stock_base_url 这个覆盖点，只为把它指到代理或本地桩；不要用它切「另一朵云」，
    因为不存在另一朵云。
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
        """发一次请求，返回信封里的 data。base 只用来把地址指到代理或桩服务。"""
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
            # AuthorizeFailed 的 msg 是「登录超时，请重新登录」，看不出到底哪一层错了。
            # 本地能读 aud：同一种报错下，凭据类型错和凭据失效要给的下一步完全不同。
            if exc.code_name in AUTH_CODES:
                raise ApiError(exc.code_name, f"{exc.message}; {self._hint(token)}", exc.request_id, path) from None
            if "无当前资源访问权限" in exc.message:
                # token 有效（余额、库存都能通）但账号层没通过：Pro 要个人实名或企业认证，
                # 弹性部署的部署/容器要企业认证。跟卡、区、规格都无关，换着试没有意义。
                # 单独一个退出码 8，应用层据此直接说「没有实名认证」，不必转述服务端原句。
                raise NoEntitlement(exc.code_name, exc.message, exc.request_id, path) from None
            raise

    def _hint(self, token: str) -> str:
        aud = token_aud(token)
        if not aud:
            return f"not a signed token (no aud claim): copy the string itself from {TOKEN_STEPS}"
        if aud == "develop_api":
            # 官方文档写明：Pro 需要个人实名/企业认证；未认证的账号拿着有效 token 也一样被拒，
            # 而服务端给的就是这句「登录超时」，看不出是认证问题。
            return (f"aud={aud} (Pro 开发者Token), right type but rejected: regenerate it at {TOKEN_STEPS}; "
                    f"a fresh one failing the same way means the account is not verified "
                    f"(Pro 需个人实名或企业认证)")
        return (f"aud={aud}: not a developer-API token; a browser login token looks the same shape "
                f"but is refused here — take the string from {TOKEN_STEPS}")


def anonymous_json(path: str, body: dict) -> dict:
    """不带 token 地 POST 一次，返回信封里的 data。只给公开接口用（算力市场）。

    市场接口是控制台同源的公开接口：未登录也能读，所以这里既不读 token 也不发
    Authorization —— 拿一个坏 token 去问反而可能被 401。
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
