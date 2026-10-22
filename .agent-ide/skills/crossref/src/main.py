#!/usr/bin/env python3
"""Crossref literature search CLI (keyless Crossref API)."""
import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.parse
from datetime import datetime

import requests

DEFAULT_MAILTO = os.environ.get("CROSSREF_MAILTO", "").strip()


from .paths import get_skills_dir


class CrossrefClient:
    BASE_URL = "https://api.crossref.org"

    def __init__(self, mailto=None, delay=0.3, max_retries=3, budget_seconds=120):
        self.mailto = mailto
        self.delay = delay
        self.max_retries = max_retries
        self.budget_seconds = budget_seconds
        self._start = time.time()

    def _budget_left(self):
        return self.budget_seconds - (time.time() - self._start)

    def _budget_exhausted(self):
        return self._budget_left() <= 0

    def _make_request(self, url, retries=None):
        retries = retries or self.max_retries
        # Quick-fail: respect overall time budget; abort remaining retries.
        if self._budget_exhausted():
            print(f"[QUICK-FAIL] Time budget ({self.budget_seconds}s) exhausted. Aborting further retries.", file=sys.stderr)
            return None
        time.sleep(self.delay)
        if self.mailto:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}mailto={urllib.parse.quote(self.mailto)}"
        headers = {
            "User-Agent": f"CrossrefAgent/1.0 (mailto:{self.mailto or 'agent@local'})"
        }
        for attempt in range(retries):
            if self._budget_exhausted():
                print(f"[QUICK-FAIL] Time budget ({self.budget_seconds}s) exhausted. Aborting further retries.", file=sys.stderr)
                return None
            try:
                timeout = min(30, max(10, self._budget_left()))
                resp = requests.get(url, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 429:
                    wait_time = min((2 ** attempt) + random.uniform(0, 1), self._budget_left())
                    if wait_time <= 0:
                        print("[QUICK-FAIL] No budget left for 429 backoff.", file=sys.stderr)
                        return None
                    print(f"[WARN] HTTP 429. Retrying in {wait_time:.2f}s...", file=sys.stderr)
                    time.sleep(wait_time)
                    continue
                if resp.status_code == 404:
                    print("[WARN] 404 Not Found.", file=sys.stderr)
                    break
                print(f"[ERROR] API Request Failed: HTTP {resp.status_code}", file=sys.stderr)
                break
            except requests.RequestException as e:
                print(f"[ERROR] API Request Failed: {e}", file=sys.stderr)
                break
        return None

    def search_journal_works(self, issn, query, rows=10, sort=None, from_year=None):
        """Works inside a single journal, filtered by ISSN."""
        path = f"/journals/{urllib.parse.quote(issn)}/works"
        params = [f"query.title={urllib.parse.quote(query)}", f"rows={rows}"]
        if sort:
            params.append(f"sort={urllib.parse.quote(sort)}")
        filters = []
        if from_year:
            filters.append(f"from-pub-date:{from_year}-01-01")
        if filters:
            params.append("filter=" + ",".join(filters))
        url = f"{self.BASE_URL}{path}?" + "&".join(params)
        return self._make_request(url)

    def search_works(self, query, rows=10, from_year=None):
        params = [f"query={urllib.parse.quote(query)}", f"rows={rows}"]
        if from_year:
            params.append(f"filter=from-pub-date:{from_year}-01-01")
        url = f"{self.BASE_URL}/works?" + "&".join(params)
        return self._make_request(url)

    def fetch_work(self, doi):
        url = f"{self.BASE_URL}/works/{urllib.parse.quote(doi.strip(), safe='')}"
        return self._make_request(url)

    def fetch_journal(self, issn):
        url = f"{self.BASE_URL}/journals/{urllib.parse.quote(issn.strip())}"
        return self._make_request(url)


def _license_status(work):
    """Return (cc_type or None, license_url) from Crossref license field.

    Crossref publishes `.../licenses/by-nc/4.0/`, not `.../licenses/cc-by-nc/4.0/`,
    so the old `"cc-by" in url` test never matched a real licence and every
    Creative Commons work came back as a bare "CC".
    """
    for lic in work.get("license", []):
        url = (lic.get("URL") or "").lower()
        if "creativecommons.org/licenses/" not in url:
            continue
        for code in ("by-nc-nd", "by-nc-sa", "by-nc", "by-nd", "by-sa", "by"):
            if f"licenses/{code}" in url or f"cc-{code}" in url:
                return f"CC-{code.upper()}", lic.get("URL")
        return "CC", lic.get("URL")
    # fallback: link with text-mining content type often implies OA
    return None, None


def _authors(work):
    return [a.get("given", "") + " " + a.get("family", "") for a in work.get("author", []) if a.get("family")]


def parse_works(data):
    if not data:
        return []
    items = data.get("message", {}).get("items", [])
    out = []
    for w in items:
        issued = w.get("issued", {}).get("date-parts", [[None]])
        year = issued[0][0] if issued and issued[0] else None
        cc, lic_url = _license_status(w)
        out.append({
            "title": (w.get("title") or [""])[0],
            "year": year,
            "journal": (w.get("container-title") or [""])[0],
            "volume": w.get("volume"),
            "issue": w.get("issue"),
            "pages": w.get("page"),
            "doi": w.get("DOI"),
            "authors": _authors(w)[:10],
            "cited_by_count": w.get("is-referenced-by-count", 0),
            "license": cc,
            "license_url": lic_url,
            "type": w.get("type"),
        })
    return out


def save_output(agent_id, command_name, query, results):
    skills_dir = get_skills_dir()
    output_dir = os.path.join(skills_dir, "data", "results", agent_id)
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rand_hash = hashlib.md5(f"{timestamp}_{random.random()}".encode()).hexdigest()[:8]
    filename = f"{timestamp}_{command_name}_{rand_hash}.json"
    filepath = os.path.join(output_dir, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"command": command_name, "query": query, "timestamp": timestamp,
                       "results": results}, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Failed to save output: {e}")


def _row(p):
    """One work per line: title, year, cited, doi, journal. Tab separated, no decoration."""
    title = (p.get("title") or "").replace("\t", " ").replace("\n", " ").strip()
    return "\t".join([
        title or "-",
        str(p.get("year") or "?"),
        str(p.get("cited_by_count", 0)),
        p.get("doi") or "-",
        (p.get("journal") or "-").replace("\t", " "),
    ])


def main():
    parser = argparse.ArgumentParser(
        description="Crossref Literature Tool (keyless, bot-friendly DOI metadata API)")
    parser.add_argument("--id", type=str, required=True,
                        help="Mandatory Agent ID for isolated execution and storage")
    parser.add_argument("--mailto", type=str, default=DEFAULT_MAILTO,
                        help="Optional contact email for Crossref polite pool (recommended)")
    parser.add_argument("--budget-seconds", type=int, default=120,
                        help="Overall time budget in seconds; abort remaining retries when exhausted (default 120)")
    parser.add_argument("--max-retries", type=int, default=3,
                        help="Max retries per HTTP request (default 3)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    p_issn = subparsers.add_parser("search-issn", help="Search works inside ONE journal by ISSN")
    p_issn.add_argument("issn", type=str, help="Journal ISSN, e.g. 0963-9969")
    p_issn.add_argument("query", type=str, help="Search query (title match)")
    p_issn.add_argument("--rows", type=int, default=10, help="Max results (default 10)")
    p_issn.add_argument("--sort", type=str, default=None,
                        choices=[None, "relevance", "score", "published"],
                        help="Sort order (default: relevance)")
    p_issn.add_argument("--from-year", type=int, default=None, help="Only works from this year on")

    p_search = subparsers.add_parser("search", help="General cross-publisher search")
    p_search.add_argument("query", type=str, help="Search query")
    p_search.add_argument("--rows", type=int, default=10, help="Max results (default 10)")
    p_search.add_argument("--from-year", type=int, default=None, help="Only works from this year on")

    p_work = subparsers.add_parser("work", help="Fetch a single work by DOI")
    p_work.add_argument("doi", type=str, help="DOI, e.g. 10.1016/j.foodres.2026.119852")

    p_journal = subparsers.add_parser("journal", help="Journal metadata by ISSN")
    p_journal.add_argument("issn", type=str, help="Journal ISSN")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = CrossrefClient(mailto=args.mailto, max_retries=args.max_retries,
                            budget_seconds=args.budget_seconds)

    if args.command == "search-issn":
        data = client.search_journal_works(args.issn, args.query, rows=args.rows,
                                           sort=args.sort, from_year=args.from_year)
        papers = parse_works(data)
        if not papers:
            print("[WARN] no results", file=sys.stderr)
            sys.exit(0)
        total = (data or {}).get("message", {}).get("total-results", 0)
        print(f"[crossref] {total} matches in ISSN {args.issn}", file=sys.stderr)
        for p in papers:
            print(_row(p))
        save_output(args.id, "search-issn", f"{args.issn} :: {args.query}", papers)

    elif args.command == "search":
        data = client.search_works(args.query, rows=args.rows, from_year=args.from_year)
        papers = parse_works(data)
        if not papers:
            print("[WARN] no results", file=sys.stderr)
            sys.exit(0)
        total = (data or {}).get("message", {}).get("total-results", 0)
        print(f"[crossref] {total} matches", file=sys.stderr)
        for p in papers:
            print(_row(p))
        save_output(args.id, "search", args.query, papers)

    elif args.command == "work":
        data = client.fetch_work(args.doi)
        msg = (data or {}).get("message", {})
        if not msg:
            sys.exit(1)
        issued = msg.get("issued", {}).get("date-parts", [[None]])
        year = issued[0][0] if issued and issued[0] else None
        cc, lic_url = _license_status(msg)
        abstract = re.sub(r"<[^>]+>", " ", msg.get("abstract") or "").strip()
        vol, iss = msg.get("volume"), msg.get("issue")
        volume = f"{vol}({iss})" if vol else (str(vol) if vol else None)
        fields = [
            ("title", (msg.get("title") or [""])[0]),
            ("year", year),
            ("journal", (msg.get("container-title") or [""])[0]),
            ("volume", volume),
            ("pages", msg.get("page")),
            ("doi", msg.get("DOI")),
            ("type", msg.get("type")),
            ("cited", msg.get("is-referenced-by-count", 0)),
            ("license", cc),
            ("license_url", lic_url),
            ("authors", ", ".join(_authors(msg)[:10])),
            ("abstract", abstract[:800]),
        ]
        for key, value in fields:
            print(f"{key}\t{value if value not in (None, '') else '-'}")
        save_output(args.id, "work", args.doi, [{
            "title": (msg.get("title") or [""])[0], "year": year,
            "journal": (msg.get("container-title") or [""])[0],
            "doi": msg.get("DOI"), "license": cc, "authors": _authors(msg)[:10],
        }])

    elif args.command == "journal":
        data = client.fetch_journal(args.issn)
        msg = (data or {}).get("message", {})
        if not msg:
            sys.exit(1)
        print(f"name\t{msg.get('title') or '-'}")
        print(f"issn\t{', '.join(msg.get('ISSN') or []) or '-'}")
        print(f"publisher\t{msg.get('publisher') or '-'}")
        print(f"subject\t{', '.join(msg.get('subject') or []) or '-'}")
        save_output(args.id, "journal", args.issn, [{
            "title": msg.get("title"), "issn": msg.get("ISSN"),
            "publisher": msg.get("publisher"), "subject": msg.get("subject", []),
        }])


if __name__ == "__main__":
    main()
