"""PDF download engine.

Input is any result JSON that carries a pdf url — openalex writes `pdf_url`,
arxiv writes `pdf_link`. Hosts are not assumed to be arxiv.org: the caller may
point this at AAAI, institutional repositories, or any OA location the search
tool found. Three rules keep it honest:

  * a browser User-Agent, because some hosts drop the default python UA;
  * the first bytes must be `%PDF`, because a failed fetch often returns a 200
    HTML error page;
  * download to `.part`, rename only after the magic check, and resume with
    `Range` when the host supports it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time

import requests

from src.paths import data_dir, resolve_arg

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
PDF_MAGIC = b"%PDF"
CHUNK = 64 * 1024


def is_pdf(head: bytes) -> bool:
    return head.startswith(PDF_MAGIC)


def slug(text: str, limit: int = 70) -> str:
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", (text or "").strip()).strip("-")
    return s[:limit] or "paper"


def filename_for(url: str, title: str = "") -> str:
    return f"{slug(title)}-{hashlib.sha1(url.encode()).hexdigest()[:8]}.pdf"


def records_from_json(path: str) -> list[dict]:
    """Accept openalex ({results: [...]}) and arxiv ([...]) snapshots alike."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("results") if isinstance(data, dict) else data
    records = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        url = it.get("pdf_url") or it.get("pdf_link") or it.get("link")
        if not url:
            continue
        records.append({
            "title": it.get("title") or it.get("display_name") or "",
            "url": url,
        })
    return records


def download_one(url: str, dest_dir: str, title: str = "", *, timeout: float = 60,
                 retries: int = 3, session: requests.Session | None = None) -> dict:
    os.makedirs(dest_dir, exist_ok=True)
    final = os.path.join(dest_dir, filename_for(url, title))
    if os.path.exists(final) and os.path.getsize(final) > 5:
        return {"status": "exists", "path": final, "bytes": os.path.getsize(final)}

    part = final + ".part"
    s = session or requests.Session()
    last_error = ""
    for attempt in range(retries):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        headers = {"User-Agent": BROWSER_UA}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            with s.get(url, headers=headers, timeout=timeout, stream=True,
                       allow_redirects=True) as resp:
                if resp.status_code in (401, 403, 404, 410):
                    return {"status": f"http{resp.status_code}", "path": "", "bytes": 0}
                if resp.status_code == 429:
                    last_error = "http429"
                    time.sleep(min(2 ** attempt + 1, 10))
                    continue
                resp.raise_for_status()
                resuming = have > 0 and resp.status_code == 206
                if not resuming:
                    have = 0
                head = b""
                if resuming and os.path.exists(part):
                    with open(part, "rb") as f:
                        head = f.read(4)
                with open(part, "ab" if resuming else "wb") as f:
                    for chunk in resp.iter_content(CHUNK):
                        if not chunk:
                            continue
                        if not head:
                            head = chunk[:4]
                        f.write(chunk)
                if not is_pdf(head):
                    os.remove(part)
                    return {"status": "not-pdf", "path": "", "bytes": 0}
                os.replace(part, final)
                return {"status": "ok", "path": final, "bytes": os.path.getsize(final)}
        except requests.RequestException as exc:
            last_error = type(exc).__name__
            time.sleep(min(2 ** attempt, 8))
    return {"status": f"failed:{last_error}", "path": "", "bytes": 0}


def download_records(records: list[dict], dest_dir: str, *, delay: float = 1.2,
                     retries: int = 3, quiet: bool = False) -> dict:
    """Download a list of {"title", "url"} records; returns counters.

    Shared by `download --from` and by `--download` on a fresh search, so both
    paths obey the same UA / magic / resume / atomic-rename rules.
    """
    session = requests.Session()
    stats = {"ok": 0, "present": 0, "skipped": 0, "failed": 0, "bytes": 0}
    started = time.monotonic()
    for i, rec in enumerate(records, 1):
        result = download_one(rec["url"], dest_dir, rec.get("title", ""),
                              retries=retries, session=session)
        status = result["status"]
        if status in ("ok", "exists"):
            stats[status] += 1
            stats["bytes"] += result["bytes"]
            if not quiet:
                print(f"{status}\t{result['bytes'] / 1048576:.1f}MB\t"
                      f"{os.path.basename(result['path'])}")
        elif status.startswith("http4"):
            stats["skipped"] += 1
            if not quiet:
                print(f"skip\t{status}\t{rec.get('title', '')[:70]}")
        else:
            stats["failed"] += 1
            if not quiet:
                print(f"fail\t{status}\t{rec.get('title', '')[:70]}")
        sys.stdout.flush()
        if i < len(records):
            time.sleep(max(delay, 0))
    stats["seconds"] = time.monotonic() - started
    return stats


def main_download(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="arxiv download",
        description="Download the PDFs listed in a search snapshot (openalex or arxiv).",
    )
    parser.add_argument("--from", dest="source", required=True,
                        help="result JSON: openalex data/results/*.json or arxiv data/fetch/results/*.json")
    parser.add_argument("--out", default=None, help="destination directory (default data/pdfs; a relative path is read against the project root)")
    parser.add_argument("--limit", type=int, default=0, help="stop after N files (0 = all)")
    parser.add_argument("--delay", type=float, default=1.2, help="seconds between requests")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true", help="list what would be fetched")
    args = parser.parse_args(argv)

    try:
        records = records_from_json(args.source)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ERROR] cannot read {args.source}: {exc}", file=sys.stderr)
        return 2
    if args.limit > 0:
        records = records[: args.limit]
    if not records:
        print(f"[WARN] no pdf url in {args.source}", file=sys.stderr)
        return 1

    dest = resolve_arg(args.out) if args.out else os.path.join(data_dir(), "pdfs")
    if args.dry_run:
        for r in records:
            print(f"{r['url']}  <-  {r['title'][:60]}")
        return 0

    stats = download_records(records, dest, delay=args.delay, retries=args.retries)
    print(f"\n{stats['ok']} new, {stats['present']} already present, "
          f"{stats['skipped']} skipped, {stats['failed']} failed, "
          f"{stats['bytes'] / 1048576:.1f} MB in {stats['seconds']:.0f}s -> {dest}")
    return 0 if stats["failed"] == 0 else 1
