"""One verb per action, one-to-one with the official endpoints.

Output rule: data on stdout (one record per line, no header, no prefix), diagnostics
on stderr (prefix ``autodl: ``, one per line). ``create`` / ``image-save`` print the new id;
``start`` / ``stop`` / ``release`` say nothing on success -- the exit code is the receipt.
``credentials --set-token`` first makes a real list call with that token; nothing is stored unless it works.
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

# Spec table from the official appendix. Ids outside it are still sent: new cards appear faster than this file changes.
GPU_SPECS = {
    "h800": ("H800-80G", "general"),
    "v-48g": ("4090-48G", "general"),
    "pro6000-p": ("PRO6000-96G", "performance"),
    "v-32g-p": ("4080(S)-32G", "performance"),
    "v-48g-350w": ("3090-48G", "general"),
    "5090-p": ("5090-32G", "performance"),
    "4090D": ("4090D", "general"),
}

PUBLIC_IMAGES = {
    "base-image-l2t43iu6uk": ("PyTorch", "cuda11.8-cudnn8-devel-ubuntu20.04-py38-torch2.0.0"),
    "base-image-l374uiucui": ("PyTorch", "cuda11.3-cudnn8-devel-ubuntu20.04-py38-torch1.11.0"),
    "base-image-u9r24vthlk": ("PyTorch", "cuda11.3-cudnn8-devel-ubuntu20.04-py38-torch1.10.0"),
    "base-image-12be412037": ("PyTorch", "cuda11.1-cudnn8-devel-ubuntu18.04-py38-torch1.9.0"),
    "base-image-mbr2n4urrc": ("Miniconda", "cuda11.6-cudnn8-devel-ubuntu20.04-py38"),
    "base-image-l2843iu23k": ("TensorRT", "cuda11.8-cudnn8-devel-ubuntu20.04-py38-trt8.5.1"),
}

REGIONS = {"westDC3": "northwest", "beijingDC2": "beijing"}

# Market card name -> spec id of the developer API. Only the ones that line up: the 27
# RTX 5090 D / RTX 6000D Pro machines have no id in the docs, and `await` skips them -- an id you cannot pass is a card you cannot rent.
SPEC_BY_MARKET_NAME = {
    "vGPU-32GB": "v-32g-p",
    "vGPU-48GB": "v-48g",
    "vGPU-48GB-350W": "v-48g-350w",
    "RTX 4090D": "4090D",
    "RTX 5090": "5090-p",
    "RTX PRO 6000": "pro6000-p",
    "H800": "h800",
}

# The deployment stock API requires region_sign, so every region in the appendix is asked by default.
# These are region codes (verbatim from the appendix), not a card map: nothing here says what "4090" equals.
ESD_REGIONS = (
    "westDC2", "westDC3", "beijingDC1", "beijingDC2", "beijingDC3", "beijingDC4",
    "neimengDC1", "neimengDC3", "foshanDC1", "chongqingDC1", "yangzhouDC1",
)


# --------------------------------------------------------------------------- output
# bash contract: data on stdout so it can be piped; diagnostics on stderr, prefixed with the tool name, one per line.
# State-changing actions say nothing on success -- like mkdir and rm, the exit code is the receipt.

def out(message: str) -> None:
    print(message, file=sys.stdout, flush=True)


def err(message: str) -> None:
    print(f"autodl: {message}", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- formatting

def money(fen) -> str:
    """Prices are in fen: 4090 reports 268, which is the published 2.68 CNY/h."""
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
    """One instance per line, single spaces, no padding for alignment."""
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
        lines.append(f"price {money(payg)}" + (f" (list {money(origin)})" if origin and origin != payg else ""))
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


# --------------------------------------------------------------------------- arguments

class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        err(message)
        raise SystemExit(USAGE)


def build_parser() -> _Parser:
    parser = _Parser(
        prog="autodl",
        description="AutoDL API from a terminal: one host (api.autodl.com), one developer token, several product lines.",
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

    p = subs.add_parser("credentials", help="show or store the developer token")
    p.add_argument("--set-token", metavar="TOKEN", help="store it in data/credentials.json (0600)")
    p.set_defaults(handler=cmd_credentials)

    p = subs.add_parser("gpus", help="spec ids, public images, regions")
    p.set_defaults(handler=cmd_gpus)

    p = subs.add_parser("stock", help="idle/total GPUs per region (deployment stock API)")
    p.add_argument("--region", metavar="A,B",
                   help="only these region codes (default: every region in the docs appendix)")
    p.add_argument("--gpu", metavar="ID",
                   help="exact identifier from column 1, e.g. 'RTX 4090' (no alias, no substring)")
    p.set_defaults(handler=cmd_stock)

    p = subs.add_parser("watch", help="report the moment a machine has an idle card, for a human to grab")
    p.add_argument("--gpu", metavar="TEXT", help="substring of the model name, e.g. 4090")
    p.add_argument("--region", metavar="TEXT", help="substring of the region name, e.g. northwest-B")
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

    p = subs.add_parser("market", help="what the compute market sells: cards, prices, Pro-capable (no token)")
    p.add_argument("--gpu", metavar="TEXT", help="substring of the model name, e.g. 4090")
    p.add_argument("--pro", action="store_true", help="only machines open to Container Instance Pro")
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


# --------------------------------------------------------------------------- commands

def _client() -> "client.Client":
    return client.Client(client.require_token())


def cmd_credentials(args) -> int:
    if args.set_token:
        # Verify before writing: a bad token must not leave a "set" half-state behind.
        client.verify_token(args.set_token)
        client.store_token(args.set_token)
    creds = client.load()
    token = client.require_token()  # raises with the file path and console path when the token is missing
    aud = client.token_aud(token)
    # aud decides what to do next: develop_api means the type is right and only the token is stale; no aud at all means the wrong thing was pasted.
    out(f"token {client.masked(token)} " + (f"aud={aud}" if aud else "aud=- (not a signed token)"))
    if creds["account"]:
        out(f"account {creds['account']}")
    defaults = {k: v for k, v in creds["defaults"].items() if v not in ("", None)}
    if defaults:
        out("defaults " + " ".join(f"{k}={v}" for k, v in defaults.items()))
    return OK


def cmd_gpus(args) -> int:
    # The first word on each line is the flag it fills; no header, no summary.
    for spec_id, (name, tier) in GPU_SPECS.items():
        out(f"gpu {spec_id} {name} {tier}")
    for uuid, (framework, detail) in PUBLIC_IMAGES.items():
        out(f"image {uuid} {framework} {detail}")
    for key, value in REGIONS.items():
        out(f"region {key} {value}")
    return OK


def _more(data: dict, page: int, command: str) -> None:
    """Mention a next page only on stderr; stdout carries data alone."""
    max_page = data.get("max_page") or 1
    if page < max_page:
        err(f"page {page} of {max_page}; more: autodl {command} --page {page + 1}")


# --------------------------------------------------------------------------- stock
# The response shape of this endpoint is not stabilised in the docs: it may be {model: {idle_gpu_num, total_gpu_num}},
# or [{region_sign, gpu_alias_name, idle_gpu_num, total_gpu_num}], or layered by region.
# So position is not trusted, only co-occurrence: walk down and take a row from any node carrying both an idle and a total count.

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
    """Only `payg_price` is read; every other price field is ignored -- the same API carries two scales.

    `payg_price` / `origin_pay_price` (Pro instance detail) are **fen**: 1970 is 19.70 CNY/h.
    The deployment container `price` is **yuan x 1000**: 2680 is 2.68 CNY/h.
    The two look alike; dividing by 100 instead of 1000 is off by ten, so only the field
    whose name carries `payg` is trusted (its scale is fixed in the docs); everything else counts as absent.

    The stock endpoint itself returns only `idle_gpu_num`/`total_gpu_num` per the docs, so this usually returns None.
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
    """(model identifier, region, idle, total, price fen/hour), sorted by identifier then region.

    The first column is the key `--gpu` wants. The response carries no region name (region is a request parameter), so the caller passes it in.
    A None price means the response did not carry one and it then does not appear in the output -- the stock endpoint really does return idle/total only.
    """
    rows: list[tuple[str, str, int, int, int | None]] = []
    _walk_stock(data, region, None, None, rows)
    return sorted(set(rows), key=lambda row: (row[0], row[1]))


def cmd_stock(args) -> int:
    """region_sign is required and the response carries no region name, so ask region by region and merge.

    The region codes in the appendix are fixed identifiers, not a card map: only codes here, no
    "what does 4090 equal" table of any kind.
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
        raise failed[0][1]           # nothing succeeded: re-raise the first real cause
    for region, exc in failed:
        err(f"{region}: {exc}")      # partial failure: data still printed, problem to stderr

    if args.gpu:
        # Match the identifier itself: no aliases, no substrings -- "4090" is not "RTX 4090",
        # and guessing wrong costs a rented card. Case is ignored; everything else must match exactly.
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
    """Per-card on-demand price in fen per card-hour. `payg_price` is in li (1/1000 yuan) and is already **per card**.

    Two measurements pin the unit down:
    - An 8-card and a 12-card machine of the same model report the identical `payg_price` (4090D both 1980),
      so it does not scale with card count and is not a whole-machine price;
    - 1980 / 1000 = 1.98 CNY, matching the unit price the console shows for that model when creating
      (dividing by 100 gives 19.80, dividing by the card count gives 1.65; both are wrong).
    """
    price = machine.get("payg_price")
    if not isinstance(price, int) or price <= 0:
        return None
    return round(price / 10)          # li -> fen


def _watch_matches(machines: list[dict], args) -> list[dict]:
    """Filter machines by the `watch` conditions, returning the ones that still have idle cards."""
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
    """Console deep link for the create page: it opens on this machine, this region and this card count; only the click is missing.

    The route was read out of the frontend bundle (assets/index.d42e8c2b.js); the name is
    `market-create-instance`, but the **path is top level** `create/:region?/:id?/:num?/:chargeType?`
    -- not under `/market`. Writing `/market/create/...` lands on the `/:pathMatch(.*)*` 404 page.
    The parameters are the four that `toCreateInstance` pushes from the market list:
    `region_sign / machine_id / gpu_idle_num / charge_type`。
    """
    num = max(1, min(cards, int(m.get("gpu_idle_num") or 1)))
    return (f"https://www.autodl.com/create/{m.get('region_sign') or ''}/"
            f"{m.get('machine_id')}/{num}/payg")


def _open_browser(url: str) -> None:
    """Hand the deep link to the system browser. A failure is one stderr line and does not stop the watch."""
    try:
        subprocess.run(["open", url], check=False, timeout=10)
        err(f"opened {url}")
    except (OSError, subprocess.SubprocessError) as exc:
        err(f"could not open a browser ({exc}); the LINK line above still works")


def cmd_watch(args) -> int:
    """Watch the market and report events only: a machine gains an idle card -> one line; it is taken -> another line.

    This is for a human to grab: create on the API side sits behind an account gate (see exit 8), while the console can be clicked.
    So it does not order on your behalf; it shouts "which machine, which region, what price" the moment a window opens.
    stdout is one machine per line, starting with `APPEAR` / `GONE` so a program can read it; diagnostics go to stderr.
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
        # Only the N cheapest are announced: the more candidates, the more judgement a human has to make.
        ranked = sorted(fresh.items(), key=lambda kv: _payg(kv[1]) or 10 ** 9)
        picked = dict(ranked[:max(1, int(args.limit))])
        for mid, m in picked.items():
            if mid not in live:
                out(f"APPEAR {_watch_line(m)}")
                link = _watch_link(m, args.cards)
                out(f"LINK {link}")
        # One browser popup per machine: a card that is taken and comes back must not interrupt again.
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
    """The console compute-market table, readable while signed out: the only place a price can be seen.

    Division of labour with stock: stock reports idle counts per card model under deployment (no price, no region name);
    market reports the hosts the console actually sells -- whole-machine price, per-card price, region name, and whether
    the machine is open to Container Instance Pro (enable_container_pro). A Pro create can only land on the latter.
    """
    machines = _market_rows()

    wanted = str(args.gpu or "").strip().casefold()
    if wanted:
        # This is a lookup, not an order, so substrings are allowed: typing 4090 should show 4090/4090D/48G.
        # The create path stays exact; the two semantics differ on purpose.
        machines = [m for m in machines if wanted in str(m.get("gpu_name", "")).casefold()]
    if args.pro:
        machines = [m for m in machines if m.get("enable_container_pro")]
    if not args.all:
        machines = [m for m in machines if int(m.get("gpu_idle_num") or 0) > 0]

    groups: dict[tuple, list] = {}
    for m in machines:
        per = _payg(m)
        # pro must be part of the key: within one region and model, Pro-capability is per machine. Mixed together it
        # prints "idle 16 pro" when all 16 idle cards sit on console-only machines -- a line that
        # suggests the API has cards to open. Kept apart, an empty pro line really means no card.
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
    """Market machine list, paged concurrently.

    One page takes about 2.6 s and there are 9, so a serial pass is 38 s -- measured idle windows are on the order of ten seconds,
    and serial would miss them systematically. Fetch page 1 for max_page, then go concurrent.
    `region_sign_list` really does filter (385 machines / 4 pages across four regions), while `gpu_name_list` does nothing
    (pass it and every model still comes back). A larger `page_size` is slower (21 s per page at 500) -- leave it alone.
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
    # Official docs: the only payload is "gpu", and "the API cannot boot in GPU-less mode". So there is no --cpu here.
    body = {"instance_uuid": args.uuid, "payload": "gpu"}
    if args.start_command:
        body["start_command"] = args.start_command
    _client().call("POST", client.POWER_ON, body)
    if getattr(args, "watch", True):
        start_watchdog(args.uuid)
    return OK


def start_watchdog(uuid: str) -> None:
    """Booting arms the watchdog: once the instance is up nobody is watching, and it watches instead.

    Success is silent (as with every other action, the exit code is the receipt); a failure leaves one line and does not affect start itself.
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


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
