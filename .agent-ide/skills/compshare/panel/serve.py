#!/usr/bin/env python3
"""CompShare stock board: two jobs only -- run this package's CLI, turn the result
into JSON.

Signing and API calls are not implemented here, so there is no second copy of the
logic to drift. Every number comes from this package's `compshare.py`, and an error
there surfaces verbatim. The board sits next to the skill package, so it moves with it.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PKG = Path(__file__).resolve().parent.parent          # skill package root
SKILL = PKG / "compshare.py"
PAGE = Path(__file__).resolve().parent / "index.html"

ZONE_NAMES = {
    "cn-wlcb-01": "North China 2A",
    "cn-sh2-02": "Shanghai 2B",
    "cn-bj2-03": "North China 1C",
    "cn-sh2-01": "Shanghai 2A",
    "cn-sh2-03": "Shanghai 2C",
}
ZONE_KIND = {"cn-wlcb-01": "VM", "cn-sh2-02": "VM", "cn-bj2-03": "Container",
             "cn-sh2-01": "Container", "cn-sh2-03": "Container"}


def _default_gpu() -> str | None:
    """The card type defaults to the most recent instance record; no model is
    hardcoded, so changing cards needs no code change."""
    import glob
    import json as _json
    files = sorted(glob.glob(str(SKILL / "data" / "instance-*.json")), key=lambda f: -__import__("os").path.getmtime(f))
    for f in files:
        try:
            gpu = (_json.load(open(f)).get("gpu") or "").strip()
        except Exception:  # noqa: BLE001
            continue
        if gpu:
            return gpu.split()[0]
    return None


def run(*args: str, timeout: int = 90) -> tuple[int, str, str]:
    # The board refreshes every 60s; letting a missing key pop a browser would steal
    # focus once a minute.
    env = {**os.environ, "COMPSHARE_NO_OPEN": "1"}
    proc = subprocess.run([sys.executable, str(SKILL), *args],
                          capture_output=True, text=True, timeout=timeout,
                          cwd=str(PKG), env=env)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def find_image(grep: str) -> tuple[str | None, str]:
    """Pick an image: names carrying cu12x come first (sm_89 needs CUDA >= 11.8 to
    build the rasteriser).

    cu116 and older are useless here because diff-gaussian-rasterization will not
    compile, so they sort last.
    """
    code, out, err = run("images", "--grep", grep)
    if code != 0:
        return None, err or out or f"images exit {code}"
    rows = [ln.split(None, 2) for ln in out.splitlines() if ln.strip()]
    rows = [r for r in rows if len(r) >= 3]
    if not rows:
        return None, f"no image matched {grep!r}"

    def rank(r):
        name = r[2].lower()
        if "cu12" in name or "cuda12" in name:
            return 0
        if "cu118" in name or "cuda118" in name:
            return 1
        return 2

    rows.sort(key=rank)
    return rows[0][0], " ".join(rows[0])


def stock(gpu: str, image: str) -> list[dict]:
    code, out, err = run("stock", "--gpu", gpu, "--image", image, "--all")
    if code != 0:
        raise RuntimeError(err or out or f"stock exit {code}")
    rows = []
    for line in out.splitlines():
        f = line.split()
        # <region> <zone> <zone-name> <gpu> <cards> <cpu> <mem> <yes|no>
        if len(f) < 8 or f[7] not in ("yes", "no"):
            continue
        rows.append({
            "region": f[0], "zone": f[1], "name": f[2], "gpu": f[3],
            "cards": int(f[4]), "cpu": int(f[5]),
            "mem": int(f[6]), "enough": f[7] == "yes",
            "kind": ZONE_KIND.get(f[1], ""),
        })
    return rows


def quote(region: str, zone: str, gpu: str, cards: int, cpu: int, mem: int, image: str) -> dict | None:
    code, out, err = run("quote", "--region", region, "--zone", zone, "--gpu", gpu,
                         "--cards", str(cards), "--cpu", str(cpu), "--mem-gb", str(mem),
                         "--image", image)
    if code != 0:
        return None
    for line in out.splitlines():
        if line.startswith("pay "):
            nums = [t for t in line.split() if t.replace(".", "", 1).isdigit()]
            if len(nums) >= 2:
                try:
                    return {"instance": float(nums[0]), "system_disk": float(nums[1])}
                except ValueError:
                    return None
    return None


def state(gpu: str, image: str | None, grep: str) -> dict:
    base = {"ok": False, "ts": datetime.now().strftime("%H:%M:%S"), "gpu": gpu,
            "image": image, "rows": [], "error": ""}
    if not image:
        image, note = find_image(grep)
        base["image"] = image
        if not image:
            base["error"] = note
            return base
    try:
        rows = stock(gpu, image)
    except Exception as exc:  # noqa: BLE001 - the board shows what the CLI actually said
        base["error"] = str(exc)
        return base

    for r in rows:
        if r["enough"]:
            r["quote"] = quote(r["region"], r["zone"], gpu, r["cards"], r["cpu"], r["mem"], image)
    base.update(ok=True, rows=rows)
    return base


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silent: the log keeps errors only
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        url = urlparse(self.path)
        if url.path == "/api/state":
            q = parse_qs(url.query)
            gpu = (q.get("gpu") or [_default_gpu() or ""])[0]
            if not gpu:
                return {"error": "no gpu given and no instance record to borrow a card type from"}
            image = (q.get("image") or [None])[0]
            grep = (q.get("grep") or ["torch"])[0]
            try:
                body = json.dumps(state(gpu, image, grep), ensure_ascii=False).encode()
                self._send(200, body, "application/json; charset=utf-8")
            except Exception as exc:  # noqa: BLE001
                self._send(500, json.dumps({"ok": False, "error": str(exc)},
                                           ensure_ascii=False).encode(),
                           "application/json; charset=utf-8")
            return
        if url.path in ("/", "/index.html"):
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"compshare board http://127.0.0.1:{args.port}/  pkg={SKILL.parent}", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
