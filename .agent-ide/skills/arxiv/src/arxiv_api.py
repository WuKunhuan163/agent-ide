"""arXiv API query construction and Atom parsing."""
from __future__ import annotations

import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

from src.http import http_get_bytes

_ARXIV_UA = "ArxivResearchTool/2.0 (Contact: contact@cursor.ai; Academic survey)"
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def normalize_query_terms(query: str) -> list[str]:
    skip = {"and", "or", "not"}
    return [w for w in query.split() if w.strip() and w.lower() not in skip]


def search_arxiv_chunk(
    query: str,
    start: int = 0,
    max_results: int = 10,
    sort_by: str = "submittedDate",
    delay: float = 3.0,
) -> list[dict]:
    terms = normalize_query_terms(query)
    if not terms:
        print("[ERROR] Query has no searchable keywords after normalization.", file=sys.stderr)
        return []
    formatted_query = "+AND+".join(f"all:{urllib.parse.quote(t)}" for t in terms)
    url = (
        f"https://export.arxiv.org/api/query?search_query={formatted_query}"
        f"&start={start}&max_results={max_results}&sortBy={sort_by}&sortOrder=descending"
    )
    if delay > 0:
        time.sleep(delay)
    try:
        xml_data = http_get_bytes(url, headers={"User-Agent": _ARXIV_UA}, timeout=15)
        return _parse_atom_entries(xml_data)
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        reason = e.response.reason if e.response is not None else str(e)
        print(f"[ERROR] arXiv API returned an HTTP Error: {code} ({reason})", file=sys.stderr)
        if code == 400:
            print("[ERROR] query rejected: use space-separated keywords only "
                  "(no AND/OR/NOT, no ti:/au: fields, no quotes).", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[ERROR] Network connection failed or timeout occurred: {e}", file=sys.stderr)
        return []


def _parse_atom_entries(xml_data: bytes) -> list[dict]:
    root = ET.fromstring(xml_data)
    papers: list[dict] = []
    for entry in root.findall("atom:entry", _ATOM_NS):
        title_el = entry.find("atom:title", _ATOM_NS)
        if title_el is None or not title_el.text:
            continue
        title = title_el.text.strip().replace("\n", " ")
        summary_el = entry.find("atom:summary", _ATOM_NS)
        summary = summary_el.text.strip().replace("\n", " ") if summary_el is not None and summary_el.text else ""
        published_el = entry.find("atom:published", _ATOM_NS)
        published = published_el.text if published_el is not None else ""
        raw_link_el = entry.find("atom:id", _ATOM_NS)
        raw_link = raw_link_el.text if raw_link_el is not None else ""
        arxiv_id = raw_link.split("/abs/")[-1].split("v")[0] if "/abs/" in raw_link else ""
        pdf_link = raw_link.replace("/abs/", "/pdf/") + ".pdf" if raw_link else ""
        authors = [
            name_el.text
            for author in entry.findall("atom:author", _ATOM_NS)
            if (name_el := author.find("atom:name", _ATOM_NS)) is not None and name_el.text
        ]
        papers.append(
            {
                "id": arxiv_id,
                "title": title,
                "summary": summary,
                "published": published,
                "authors": authors,
                "link": pdf_link,
            }
        )
    return papers
