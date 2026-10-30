"""每个动作一个动词，一一对应官方端点。

输出规则：数据走 stdout（一条记录一行，无表头无前缀），诊断走 stderr
（前缀 ``autodl: ``，一条一行）。``create`` / ``image-save`` 只打印新 id，
``start`` / ``stop`` / ``release`` 成功时不说话，退出码就是回执。
``credentials --set-token`` 先拿该 token 真打一次 list，验不过不写盘。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from src import client, watchdog
from src.client import (
    API, FAILED, NOT_FOUND, OK, SSH, USAGE,
    CliError,
)

# 官方附录的规格表。表外 id 照样发出去：AutoDL 上新卡比这个文件更新得快。
GPU_SPECS = {
    "h800": ("H800-80G", "通用型"),
    "v-48g": ("4090-48G", "通用型"),
    "pro6000-p": ("PRO6000-96G", "性能型"),
    "v-32g-p": ("4080(S)-32G", "性能型"),
    "v-48g-350w": ("3090-48G", "通用型"),
    "5090-p": ("5090-32G", "性能型"),
    "4090D": ("4090D", "通用型"),
}

PUBLIC_IMAGES = {
    "base-image-l2t43iu6uk": ("PyTorch", "cuda11.8-cudnn8-devel-ubuntu20.04-py38-torch2.0.0"),
    "base-image-l374uiucui": ("PyTorch", "cuda11.3-cudnn8-devel-ubuntu20.04-py38-torch1.11.0"),
    "base-image-u9r24vthlk": ("PyTorch", "cuda11.3-cudnn8-devel-ubuntu20.04-py38-torch1.10.0"),
    "base-image-12be412037": ("PyTorch", "cuda11.1-cudnn8-devel-ubuntu18.04-py38-torch1.9.0"),
    "base-image-mbr2n4urrc": ("Miniconda", "cuda11.6-cudnn8-devel-ubuntu20.04-py38"),
    "base-image-l2843iu23k": ("TensorRT", "cuda11.8-cudnn8-devel-ubuntu20.04-py38-trt8.5.1"),
}

REGIONS = {"westDC3": "西北区", "beijingDC2": "北京区"}

# 市场里的卡名 -> 开发者 API 的规格 id。只列能对上的：RTX 5090 D / RTX 6000D 那 27 台
# Pro 机器在文档里没有对应 id，`await` 也不会去碰它们——传不进去的 id 等于租不到。
SPEC_BY_MARKET_NAME = {
    "vGPU-32GB": "v-32g-p",
    "vGPU-48GB": "v-48g",
    "vGPU-48GB-350W": "v-48g-350w",
    "RTX 4090D": "4090D",
    "RTX 5090": "5090-p",
    "RTX PRO 6000": "pro6000-p",
    "H800": "h800",
}

# 弹性部署库存的 region_sign 是必填的，所以默认把附录里的区都问一遍。
# 这是地区标识码（官方附录原文），不是卡名映射：这里没有任何「4090 等于什么」的对照。
ESD_REGIONS = (
    "westDC2", "westDC3", "beijingDC1", "beijingDC2", "beijingDC3", "beijingDC4",
    "neimengDC1", "neimengDC3", "foshanDC1", "chongqingDC1", "yangzhouDC1",
)


# --------------------------------------------------------------------------- 输出
# bash 契约：数据走 stdout，别人可以管道接；诊断走 stderr，带工具名，一行一条。
# 会改状态的动作成功后不说话——像 mkdir、rm 那样，退出码就是回执。

def out(message: str) -> None:
    print(message, file=sys.stdout, flush=True)


def err(message: str) -> None:
    print(f"autodl: {message}", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- 格式化

def money(fen) -> str:
    """价格单位是分：4090 报 268，正是公开价 ¥2.68/h。"""
    try:
        return f"¥{int(fen) / 100:.2f}/h"
    except (TypeError, ValueError):
        return "-"


def size(num_bytes) -> str:
    try:
        value = float(num_bytes)
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return "-"


def field(value) -> str:
    return "-" if value in (None, "", {}, []) else str(value).strip()


def card(spec_uuid) -> str:
    return GPU_SPECS.get(spec_uuid, (field(spec_uuid), ""))[0]


def instance_line(item: dict) -> str:
    """一条实例一行，单空格，不用补空格对齐。"""
    bits = [field(item.get("uuid")), field(item.get("status")), card(item.get("gpu_spec_uuid")),
            field(item.get("region_name") or item.get("region_sign"))]
    if item.get("payg_price") is not None:
        bits.append(money(item.get("payg_price")))
    if item.get("name"):
        bits.append(field(item.get("name")))
    return " ".join(bits)


def snapshot_lines(data: dict) -> list[str]:
    usage = data.get("usage_info") or {}
    lines = [f"gpu {field(data.get('snapshot_gpu_alias_name'))} ({field(data.get('chip_corp'))})",
             f"region {field(data.get('region_sign'))}"]
    payg, origin = data.get("payg_price"), data.get("origin_pay_price")
    if payg is not None:
        lines.append(f"price {money(payg)}" + (f" (原价 {money(origin)})" if origin and origin != payg else ""))
    if data.get("ssh_command"):
        lines.append(f"ssh {data['ssh_command']}")
    if data.get("root_password"):
        lines.append(f"password {data['root_password']}")
    if data.get("jupyter_domain"):
        token = data.get("jupyter_token")
        lines.append(f"jupyter https://{data['jupyter_domain']}" + (f" (token {token})" if token else ""))
    for port in (6006, 6008):
        domain = data.get(f"service_{port}_domain")
        if domain:
            lines.append(f"port {port} {data.get(f'service_{port}_port_protocol') or 'http'}://{domain}")
    if usage:
        lines.append(f"cpu {usage.get('cpu_usage_percent', 0):.1f}% "
                     f"mem {usage.get('mem_usage_percent', 0):.1f}% "
                     f"({size(usage.get('mem_usage'))} / {size(usage.get('mem_limit'))})")
        lines.append(f"disk {size(usage.get('root_fs_used_size'))} / {size(usage.get('root_fs_total_size'))}")
    return lines


# --------------------------------------------------------------------------- 参数

class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        err(message)
        raise SystemExit(USAGE)


def build_parser() -> _Parser:
    parser = _Parser(
        prog="autodl",
        description="AutoDL API from a terminal: one host (api.autodl.com), one 开发者Token, several product lines.",
        epilog=(
            "examples:\n"
            "  autodl credentials                      which token is in force\n"
            "  autodl gpus                             spec ids for `create --gpu`\n"
            "  autodl stock                            every identifier, idle/total per region\n"
            "  autodl stock --gpu 'RTX 4090'           where that exact identifier is free\n"
            "  autodl ls                               every instance on the account\n"
            "  autodl create --gpu v-48g --image base-image-l2t43iu6uk --yes\n"
            "  autodl ssh  pro-76576c61fdf1            the ssh command and password\n"
            "  autodl exec pro-76576c61fdf1 nvidia-smi\n"
            "  autodl stop pro-76576c61fdf1            billing stops here\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subs = parser.add_subparsers(dest="command", metavar="<command>")

    p = subs.add_parser("credentials", help="show or store the 开发者Token")
    p.add_argument("--set-token", metavar="TOKEN", help="store it in data/credentials.json (0600)")
    p.set_defaults(handler=cmd_credentials)

    p = subs.add_parser("gpus", help="spec ids, public images, regions")
    p.set_defaults(handler=cmd_gpus)

    p = subs.add_parser("stock", help="idle/total GPUs per region (弹性部署 stock API)")
    p.add_argument("--region", metavar="A,B",
                   help="only these region codes (default: every region in the docs appendix)")
    p.add_argument("--gpu", metavar="ID",
                   help="exact identifier from column 1, e.g. 'RTX 4090' (no alias, no substring)")
    p.set_defaults(handler=cmd_stock)

    p = subs.add_parser("watch", help="report the moment a machine has an idle card, for a human to grab")
    p.add_argument("--gpu", metavar="TEXT", help="substring of the model name, e.g. 4090")
    p.add_argument("--region", metavar="TEXT", help="substring of the region name, e.g. 西北B区")
    p.add_argument("--max-price", type=float, metavar="YUAN",
                   help="only machines whose per-card hourly price is at most this")
    p.add_argument("--min-idle", type=int, default=1, help="need at least this many idle cards (default 1)")
    p.add_argument("--cards", type=int, default=1, help="cards to put in the deep link (default 1)")
    p.add_argument("--limit", type=int, default=1, help="announce at most N cheapest machines (default 1)")
    p.add_argument("--open", dest="open_browser", action="store_true",
                   help="open the create page in the system browser on every new match")
    p.add_argument("--minutes", type=int, default=30, help="stop watching after this long (default 30)")
    p.add_argument("--interval", type=int, default=8, help="seconds between checks (default 8)")
    p.set_defaults(handler=cmd_watch)

    p = subs.add_parser("market", help="what the 算力市场 sells: cards, prices, Pro-capable (no token)")
    p.add_argument("--gpu", metavar="TEXT", help="substring of the model name, e.g. 4090")
    p.add_argument("--pro", action="store_true", help="only machines open to 容器实例Pro")
    p.add_argument("--all", action="store_true", help="include machines with no idle card")
    p.set_defaults(handler=cmd_market)

    p = subs.add_parser("ls", help="instances on this account")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--size", type=int, default=20)
    p.add_argument("--status", metavar="STATE", help="only this state, e.g. running")
    p.set_defaults(handler=cmd_ls)

    p = subs.add_parser("info", help="state, ssh, price, ports, live usage")
    p.add_argument("uuid")
    p.set_defaults(handler=cmd_info)

    p = subs.add_parser("start", help="power on in GPU mode and arm the watchdog")
    p.add_argument("uuid")
    p.add_argument("--start-command", metavar="CMD", help="overrides the one set at creation")
    p.add_argument("--no-watch", dest="watch", action="store_false",
                   help="do not arm the watchdog for this boot")
    p.set_defaults(handler=cmd_start)

    p = subs.add_parser("stop", help="power off; billing stops")
    p.add_argument("uuid")
    p.set_defaults(handler=cmd_stop)

    p = subs.add_parser("release", help="delete an instance for good (needs it shutdown)")
    p.add_argument("uuid")
    p.add_argument("--yes", action="store_true", help="confirm the deletion")
    p.set_defaults(handler=cmd_release)

    p = subs.add_parser("images", help="private images on this account")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--size", type=int, default=10)
    p.set_defaults(handler=cmd_images)

    p = subs.add_parser("image-save", help="snapshot an instance into a private image")
    p.add_argument("uuid")
    p.add_argument("--name", required=True)
    p.set_defaults(handler=cmd_image_save)

    p = subs.add_parser("ssh", help="print the ssh command and password")
    p.add_argument("uuid")
    p.set_defaults(handler=cmd_ssh)

    p = subs.add_parser("exec", help="run one command over ssh (needs sshpass)")
    p.add_argument("uuid")
    p.add_argument("remote", nargs=argparse.REMAINDER, help="the command, quoted as one argument")
    p.set_defaults(handler=cmd_exec)

    p = subs.add_parser("watchdog", help="background stopper: stop the box when no job is running")
    p.add_argument("uuid", nargs="?", help="the instance to watch")
    p.add_argument("--foreground", action="store_true", help="run the poll loop here instead of detaching")
    p.add_argument("--interval", type=int, help="seconds between checks (default 60)")
    p.add_argument("--idle", type=int, help="write window that counts as activity, in minutes (default 1)")
    p.add_argument("--rounds", type=int, help="consecutive idle checks before power_off (default 30)")
    p.add_argument("--status", action="store_true", help="one line about the running watchdog")
    p.add_argument("--off", action="store_true", help="stop the watchdog, leave the instance alone")
    p.set_defaults(handler=cmd_watchdog)
    return parser


# --------------------------------------------------------------------------- 命令

def _client() -> "client.Client":
    return client.Client(client.require_token())


def cmd_credentials(args) -> int:
    if args.set_token:
        # 先验证再写盘：验不过就一个字节都不落，坏 token 不该有「设置成功」这种中间态
        client.verify_token(args.set_token)
        client.store_token(args.set_token)
    creds = client.load()
    token = client.require_token()  # 缺 token 时抛错，带文件路径与控制台路径
    aud = client.token_aud(token)
    # aud 决定「下一步该做什么」：develop_api 说明类型对了、只是失效；没有 aud 说明贴错了东西
    out(f"token {client.masked(token)} " + (f"aud={aud}" if aud else "aud=- (not a signed token)"))
    if creds["account"]:
        out(f"account {creds['account']}")
    defaults = {k: v for k, v in creds["defaults"].items() if v not in ("", None)}
    if defaults:
        out("defaults " + " ".join(f"{k}={v}" for k, v in defaults.items()))
    return OK


def cmd_gpus(args) -> int:
    # 每行第一个词是它要填的 flag，不用表头也不用小结
    for spec_id, (name, tier) in GPU_SPECS.items():
        out(f"gpu {spec_id} {name} {tier}")
    for uuid, (framework, detail) in PUBLIC_IMAGES.items():
        out(f"image {uuid} {framework} {detail}")
    for key, value in REGIONS.items():
        out(f"region {key} {value}")
    return OK


def _more(data: dict, page: int, command: str) -> None:
    """有下一页才提一句，落在 stderr，stdout 里只有数据。"""
    max_page = data.get("max_page") or 1
    if page < max_page:
        err(f"page {page} of {max_page}; more: autodl {command} --page {page + 1}")


# --------------------------------------------------------------------------- 库存
# 这个接口的响应形状没有稳定文档：可能是 {型号: {idle_gpu_num, total_gpu_num}}，
# 也可能是 [{region_sign, gpu_alias_name, idle_gpu_num, total_gpu_num}]，还可能按区分层。
# 所以不认字段位置，只认「谁跟谁在一起」：往下走，遇到同时带空闲数和总数的节点就取一行。

IDLE_KEYS = ("idle_gpu_num", "available_gpu_num", "free_gpu_num", "idle_gpu", "idle_num", "idle")
TOTAL_KEYS = ("total_gpu_num", "gpu_num", "total_gpu", "total_num", "total")
NAME_KEYS = ("gpu_alias_name", "gpu_name", "gpu_type", "gpu_spec", "alias_name", "name")
REGION_KEYS = ("region_sign", "region_name", "data_center", "region", "dc")
WRAPPER_KEYS = {"data", "list", "items", "result", "results", "rows", "stock", "gpu_stock", "gpus"}


def _num(node: dict, keys) -> int | None:
    for key in keys:
        value = node.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _text(node: dict, keys) -> str | None:
    for key in keys:
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _price(node: dict) -> int | None:
    """只认 `payg_price`，其余 price 字段一律不碰——因为同一套 API 里有两种标度。

    `payg_price` / `origin_pay_price`（Pro 实例详情）是**分**：1970 就是 ¥19.70/h。
    弹性部署容器的 `price` 是**元×1000**：2680 才是 ¥2.68/h。
    两个数长得一样，除以 100 还是 1000 猜错一次就差十倍，所以这里只认名字里带
    `payg` 的那个（标度在官方文档里写死了），其它一律当作没有。

    库存接口本身按官方文档只回 `idle_gpu_num`/`total_gpu_num`，通常这里会返回 None。
    """
    for key, value in node.items():
        low = str(key).lower()
        if "payg" not in low or "origin" in low:
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _names_a_region(key: str) -> bool:
    low = key.lower()
    return low in {code.lower() for code in REGIONS} or "region" in low or "dc" in low


def _walk_stock(node, region, gpu, price, rows) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_stock(item, region, gpu, price, rows)
        return
    if not isinstance(node, dict):
        return
    idle, total = _num(node, IDLE_KEYS), _num(node, TOTAL_KEYS)
    name = _text(node, NAME_KEYS) or gpu
    where = _text(node, REGION_KEYS) or region
    cost = _price(node) if _price(node) is not None else price
    if idle is not None and total is not None and name:
        rows.append((str(name), where or "-", idle, total, cost))
        return
    for key, value in node.items():
        if not isinstance(value, (dict, list)):
            continue
        if str(key).lower() in WRAPPER_KEYS:
            _walk_stock(value, where, name, cost, rows)
        elif _names_a_region(str(key)):
            _walk_stock(value, str(key), name, cost, rows)
        else:
            _walk_stock(value, where, str(key), cost, rows)


def stock_rows(data, region: str | None = None) -> list[tuple[str, str, int, int, int | None]]:
    """(型号 identifier, 区, 空闲, 总量, 价格分/小时)，按 identifier 再按区排序。

    第一列就是 `--gpu` 要的键。响应本身不带区名（区是请求参数），所以区由调用方传入。
    价格为 None 表示响应里没带，输出里也就不出现——库存接口确实只回 idle/total。
    """
    rows: list[tuple[str, str, int, int, int | None]] = []
    _walk_stock(data, region, None, None, rows)
    return sorted(set(rows), key=lambda row: (row[0], row[1]))


def cmd_stock(args) -> int:
    """region_sign 是必填参数，且响应里不带区名，所以按区逐个问，再合并。

    官方附录里的地区标识码是固定的标识，不是卡名映射：这里只有区代码，没有任何
    「4090 等于什么」的对照表。
    """
    wanted = [part.strip() for part in str(args.region or "").split(",") if part.strip()]
    regions = wanted or list(ESD_REGIONS)
    api = _client()
    rows: list[tuple[str, str, int, int, int | None]] = []
    failed: list[tuple[str, Exception]] = []
    for region in regions:
        try:
            data = api.call("POST", client.STOCK_REGION, {"region_sign": region},
                            base=client.stock_base_url()) or []
        except CliError as exc:
            failed.append((region, exc))
            continue
        found = stock_rows(data, region)
        if not found and data:
            failed.append((region, CliError(API, f"a shape this tool does not read yet: {str(data)[:160]}")))
            continue
        rows.extend(found)

    if not rows and failed:
        raise failed[0][1]           # 一个都没成：把第一个真实原因原样抛出去
    for region, exc in failed:
        err(f"{region}: {exc}")      # 部分失败：数据照出，问题落 stderr

    if args.gpu:
        # 只认 identifier 本身：不建别名，不做子串——「4090」不是「RTX 4090」，
        # 猜错一次就是租错一张卡的钱。大小写忽略，其余必须一模一样。
        wanted_id = args.gpu.strip().casefold()
        known = sorted({row[0] for row in rows})
        rows = [row for row in rows if row[0].casefold() == wanted_id]
        if not rows:
            if not known:
                raise CliError(NOT_FOUND, f"no stock reported for '{args.gpu}' in "
                                          f"{', '.join(regions)}")
            raise CliError(USAGE, f"no identifier '{args.gpu}'; identifiers are: " + " | ".join(known))
    for ident, where, idle, total, cost in rows:
        bits = [ident, where, f"{idle}/{total}"]
        if cost is not None:
            bits.append(money(cost))
        out(" ".join(bits))
    return OK


def _payg(machine: dict) -> int | None:
    """单卡按量价，单位分/卡·小时。`payg_price` 单位是厘（1/1000 元），已经是**单卡**价。

    两个实测把单位钉死了：
    - 同型号 8 卡机与 12 卡机的 `payg_price` 完全相同（4090D 都是 1980），
      说明它不随卡数变化，不是整机价；
    - 1980 / 1000 = ¥1.98，与控制台创建页对该机型显示的单价一致（÷100 会得到 19.80，
      ÷卡数会得到 1.65，两者都错）。
    """
    price = machine.get("payg_price")
    if not isinstance(price, int) or price <= 0:
        return None
    return round(price / 10)          # 厘 -> 分


def _watch_matches(machines: list[dict], args) -> list[dict]:
    """按 `watch` 的条件筛机器，返回仍然有空闲卡的。"""
    gpu = str(getattr(args, "gpu", "") or "").strip().casefold()
    region = str(getattr(args, "region", "") or "").strip().casefold()
    picked = []
    for m in machines:
        if int(m.get("gpu_idle_num") or 0) < max(1, int(getattr(args, "min_idle", 1) or 1)):
            continue
        if gpu and gpu not in str(m.get("gpu_name", "")).casefold():
            continue
        if region and region not in str(m.get("region_name", "")).casefold():
            continue
        per = _payg(m)
        if args.max_price is not None and (per is None or per / 100 > args.max_price):
            continue
        picked.append(m)
    return picked


def _watch_line(m: dict) -> str:
    per = _payg(m)
    price = f"¥{per / 100:.2f}/card·h" if per is not None else "price?"
    return (f"{m.get('machine_id')} {m.get('gpu_name')} "
            f"{int(m.get('gpu_memory') or 0) // 2 ** 30}G {m.get('region_name')} "
            f"idle {m.get('gpu_idle_num')}/{m.get('gpu_number')} {price} "
            f"{'pro' if m.get('enable_container_pro') else 'console-only'}")


def _watch_link(m: dict, cards: int = 1) -> str:
    """控制台的创建页深链：打开就是这台机器、这个区、这个卡数，只差按「创建」。

    路由是从前端 bundle（assets/index.d42e8c2b.js）里读出来的，名字
    `market-create-instance`，但**路径是顶层的** `create/:region?/:id?/:num?/:chargeType?`
    —— 不在 `/market` 下面；写成 `/market/create/...` 会落到 `/:pathMatch(.*)*`
    的 404 页。参数就是市场列表 `toCreateInstance` 里 push 的那四个：
    `region_sign / machine_id / gpu_idle_num / charge_type`。
    """
    num = max(1, min(cards, int(m.get("gpu_idle_num") or 1)))
    return (f"https://www.autodl.com/create/{m.get('region_sign') or ''}/"
            f"{m.get('machine_id')}/{num}/payg")


def _open_browser(url: str) -> None:
    """把深链直接丢给系统浏览器。失败只留一行 stderr，不影响继续盯。"""
    try:
        subprocess.run(["open", url], check=False, timeout=10)
        err(f"opened {url}")
    except (OSError, subprocess.SubprocessError) as exc:
        err(f"could not open a browser ({exc}); the LINK line above still works")


def cmd_watch(args) -> int:
    """盯市场，只报事件：某台机器出现空闲卡就立刻打一行，被抢走再打一行。

    这是给人抢的：API 那边的 create 有一道账号闸门（见 exit 8），控制台却能点。
    所以这里不代替人下单，只负责在窗口打开的瞬间把「哪台、哪个区、什么价」喊出来。
    stdout 一行一台机器，`APPEAR` / `GONE` 开头，方便程序读；诊断走 stderr。
    """
    if not (args.gpu or args.region):
        raise CliError(USAGE, "watch needs --gpu <text> and/or --region <text> to narrow it down")
    deadline = time.monotonic() + args.minutes * 60
    interval = max(5, int(args.interval))
    live: dict[str, dict] = {}
    opened: set[str] = set()
    rounds = 0
    err(f"watching for {_describe_watch(args)} for {args.minutes}m")
    while True:
        rounds += 1
        try:
            fresh = {str(m.get("machine_id")): m for m in _watch_matches(_market_rows(), args)}
        except CliError as exc:
            err(f"market read failed ({exc}); retrying")
            fresh = {}
        # 只把最便宜的 N 台喊出来：候选越多，人要做的判断越多。
        ranked = sorted(fresh.items(), key=lambda kv: _payg(kv[1]) or 10 ** 9)
        picked = dict(ranked[:max(1, int(args.limit))])
        for mid, m in picked.items():
            if mid not in live:
                out(f"APPEAR {_watch_line(m)}")
                link = _watch_link(m, args.cards)
                out(f"LINK {link}")
                # 同一台机器只弹一次浏览器：卡被抢走又回来时不该再打断人。
                if args.open_browser and mid not in opened:
                    opened.add(mid)
                    _open_browser(link)
        for mid, m in live.items():
            if mid not in fresh:
                out(f"GONE {_watch_line(m)}")
        live = fresh
        left = deadline - time.monotonic()
        if left <= 0:
            err(f"watch ended after {args.minutes}m, {len(live)} machine(s) still had idle cards")
            return OK
        err(f"{time.strftime('%H:%M:%S')} {len(live)} match(es) live, {left / 60:.0f}m left")
        time.sleep(min(interval, max(1.0, left)))


def _describe_watch(args) -> str:
    bits = []
    if args.gpu:
        bits.append(f"gpu~{args.gpu}")
    if args.region:
        bits.append(f"region~{args.region}")
    if args.max_price is not None:
        bits.append(f"<=¥{args.max_price:.2f}/card·h")
    if args.min_idle > 1:
        bits.append(f"idle>={args.min_idle}")
    return " ".join(bits)


def cmd_market(args) -> int:
    """控制台「算力市场」那张表，未登录也能读：这是唯一能查到价格的地方。

    与 stock 的分工：stock 报的是弹性部署按卡型号的空闲数（没有价格、没有区名）；
    market 报的是控制台真正在卖的主机——整机价、单卡价、区名，以及这台机器是否
    对容器实例 Pro 开放（enable_container_pro）。Pro 的 create 只能落在后者上。
    """
    machines = _market_rows()

    wanted = str(args.gpu or "").strip().casefold()
    if wanted:
        # 这里是「查表」不是「下单」，所以允许子串：输 4090 要能看到 4090/4090D/48G。
        # create 那条路上仍然是精确匹配，两处语义不同是有意的。
        machines = [m for m in machines if wanted in str(m.get("gpu_name", "")).casefold()]
    if args.pro:
        machines = [m for m in machines if m.get("enable_container_pro")]
    if not args.all:
        machines = [m for m in machines if int(m.get("gpu_idle_num") or 0) > 0]

    groups: dict[tuple, list] = {}
    for m in machines:
        per = _payg(m)
        # pro 必须进 key：同区同型号里，能不能承载 Pro 实例是逐台属性。混在一起会
        # 打出「idle 16 pro」，而 16 张空闲其实全在 console-only 的机器上——那种行
        # 会让人以为 API 有卡可开。分开之后 empty 的 pro 行就是真的没卡。
        key = (str(m.get("gpu_name", "?")), int(m.get("gpu_memory") or 0) // 2 ** 30,
               str(m.get("region_name", "?")), bool(m.get("enable_container_pro")))
        row = groups.setdefault(key, [0, 0, None])
        row[0] += int(m.get("gpu_idle_num") or 0)
        row[1] += 1
        if per is not None:
            row[2] = per if row[2] is None else min(row[2], per)
    if not groups:
        raise CliError(NOT_FOUND, "no machine matches that filter on the market right now")

    for (name, mem, region, pro), (idle, count, per_card) in sorted(
            groups.items(), key=lambda kv: -kv[1][0]):
        bits = [name, f"{mem}G" if mem else "?", region, f"idle {idle}"]
        bits.append(f"{count} mac")
        if per_card is not None:
            bits.append(f"¥{per_card / 100:.2f}/card·h")
        bits.append("pro" if pro else "console-only")
        out(" ".join(bits))
    return OK


def cmd_ls(args) -> int:
    data = _client().call("POST", client.LIST, {"page_index": args.page, "page_size": args.size}) or {}
    items = [item for item in data.get("list") or [] if isinstance(item, dict)]
    if args.status:
        items = [item for item in items if str(item.get("status")) == args.status]
    for item in items:
        out(instance_line(item))
    _more(data, args.page, "ls")
    return OK


def _snapshot(client_obj, uuid: str) -> dict:
    data = client_obj.call("GET", client.SNAPSHOT, {"instance_uuid": uuid})
    if not isinstance(data, dict):
        raise CliError(API, f"snapshot for {uuid} came back empty")
    return data


def cmd_info(args) -> int:
    api = _client()
    state = api.call("GET", client.STATUS, {"instance_uuid": args.uuid})
    out(f"state {field(state)}")
    for line in snapshot_lines(_snapshot(api, args.uuid)):
        out(line)
    return OK


def _market_page(page: int, regions: list[str] | None = None) -> dict:
    return client.anonymous_json(client.MARKET, {
        "page_index": page, "page_size": 100, "region_sign_list": regions or [],
        "gpu_name_list": [], "charge_type": "payg"})


def _market_rows(regions: list[str] | None = None) -> list[dict]:
    """市场机器列表，并发翻页。

    单页约 2.6 秒、共 9 页，串行一轮 38 秒 —— 实测闲卡窗口只有十秒量级，串行会
    系统性错过。先取第 1 页拿 max_page，其余并发。`region_sign_list` 真的会过滤
    （四区 385 台 / 4 页），而 `gpu_name_list` 不生效（传了仍回全部型号）。
    `page_size` 调大更慢（500 时单页 21 秒），别动。
    """
    first = _market_page(1, regions)
    rows = [item for item in first.get("list") or [] if isinstance(item, dict)]
    max_page = min(int(first.get("max_page") or 1), 20)
    if max_page > 1:
        with ThreadPoolExecutor(max_workers=8) as pool:
            pages = pool.map(lambda page: _market_page(page, regions), range(2, max_page + 1))
            for data in pages:
                rows.extend(item for item in data.get("list") or [] if isinstance(item, dict))
    return rows


def cmd_start(args) -> int:
    # 官方文档：payload 只有 "gpu"，「暂不支持API以无卡模式开机」。所以这里没有 --cpu。
    body = {"instance_uuid": args.uuid, "payload": "gpu"}
    if args.start_command:
        body["start_command"] = args.start_command
    _client().call("POST", client.POWER_ON, body)
    if getattr(args, "watch", True):
        start_watchdog(args.uuid)
    return OK


def start_watchdog(uuid: str) -> None:
    """开机即挂看门狗：实例起来之后没人盯着，它替人盯着。

    成功不吭声（和别的动作一样，退出码是回执）；失败只留一行，不影响 start 本身。
    """
    try:
        watchdog.spawn_in_background(uuid)
    except OSError as exc:
        err(f"watchdog did not start ({exc}); stop this box by hand")


def cmd_watchdog(args) -> int:
    if args.status:
        out(watchdog.status_line())
        return OK
    if args.off:
        return watchdog.stop_watchdog()
    if not args.uuid:
        raise CliError(USAGE, "watchdog needs an instance uuid, or --status / --off")
    cfg = watchdog.settings()
    for key, value in (("interval_seconds", args.interval),
                       ("idle_minutes", args.idle), ("rounds", args.rounds)):
        if value:
            cfg[key] = value
    if args.foreground:
        return watchdog.run_foreground(args.uuid, cfg)
    pid = watchdog.spawn_in_background(args.uuid, cfg)
    out(str(pid) if pid else "already running")
    return OK


def cmd_stop(args) -> int:
    _client().call("POST", client.POWER_OFF, {"instance_uuid": args.uuid})
    return OK


def cmd_release(args) -> int:
    if not args.yes:
        err(f"refused: releasing {args.uuid} deletes it and its disk, --yes to release "
            f"(snapshot first: autodl image-save {args.uuid} --name <name>)")
        return USAGE
    api = _client()
    state = field(api.call("GET", client.STATUS, {"instance_uuid": args.uuid}))
    if state != "shutdown":
        raise CliError(USAGE, f"{args.uuid} is {state}, the API releases only a shutdown instance: "
                              f"autodl stop {args.uuid}")
    api.call("POST", client.RELEASE, {"instance_uuid": args.uuid})
    return OK


def cmd_images(args) -> int:
    data = _client().call("POST", client.IMAGE_LIST, {"page_index": args.page, "page_size": args.size}) or {}
    items = [item for item in data.get("list") or [] if isinstance(item, dict)]
    for item in items:
        bits = [field(item.get("image_uuid")), field(item.get("status"))]
        if item.get("image_size"):
            bits.append(size(item.get("image_size")))
        if item.get("name"):
            bits.append(field(item.get("name")))
        out(" ".join(bits))
    _more(data, args.page, "images")
    return OK


def cmd_image_save(args) -> int:
    data = _client().call("POST", client.IMAGE_SAVE,
                          {"instance_uuid": args.uuid, "image_name": args.name})
    out(field(data.get("image_uuid") if isinstance(data, dict) else data))
    return OK


def cmd_ssh(args) -> int:
    api = _client()
    data = _snapshot(api, args.uuid)
    state = field(api.call("GET", client.STATUS, {"instance_uuid": args.uuid}))
    if state != "running":
        err(f"warning: {args.uuid} is {state}, ssh answers only while running: autodl start {args.uuid}")
    if not data.get("ssh_command"):
        raise CliError(API, f"snapshot for {args.uuid} carried no ssh_command")
    out(str(data["ssh_command"]))
    if data.get("root_password"):
        out(f"password {data['root_password']}")
    return OK


def cmd_exec(args) -> int:
    command = " ".join(args.remote).strip()
    if not command:
        raise CliError(USAGE, 'nothing to run: autodl exec <uuid> "nvidia-smi"')
    data = _snapshot(_client(), args.uuid)
    host, port, password = data.get("proxy_host"), data.get("ssh_port"), data.get("root_password")
    if not host or not port:
        raise CliError(API, f"snapshot for {args.uuid} carried no ssh endpoint")
    sshpass = shutil.which("sshpass")
    if not sshpass or not password:
        raise CliError(
            SSH,
            "no non-interactive ssh: install sshpass (brew install hudochenkov/sshpass/sshpass), "
            f"or run it yourself with autodl ssh {args.uuid}",
        )
    argv = [sshpass, "-p", str(password), "ssh", "-p", str(port),
            "-o", "StrictHostKeyChecking=accept-new", f"root@{host}", command]
    return subprocess.run(argv, check=False).returncode


HANDLERS = {
    "credentials": cmd_credentials,
    "gpus": cmd_gpus,
    "stock": cmd_stock,
    "market": cmd_market,
    "watch": cmd_watch,
    "ls": cmd_ls,
    "info": cmd_info,
    "start": cmd_start,
    "stop": cmd_stop,
    "release": cmd_release,
    "images": cmd_images,
    "image-save": cmd_image_save,
    "ssh": cmd_ssh,
    "exec": cmd_exec,
    "watchdog": cmd_watchdog,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if not getattr(args, "command", None):
        parser.print_help(sys.stderr)
        return USAGE
    try:
        return HANDLERS[args.command](args)
    except CliError as exc:
        err(str(exc))
        return exc.code
    except KeyboardInterrupt:
        err("interrupted; anything already created keeps billing: autodl ls")
        return 1
