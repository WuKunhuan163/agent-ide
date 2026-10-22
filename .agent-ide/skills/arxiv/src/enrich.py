"""Crossref citations and HuggingFace upvotes enrichment."""
from __future__ import annotations

import urllib.parse

from src.http import http_get_json

_CROSSREF_UA = "ResearchPaperSurveyBot/1.0 (mailto:contact@cursor.ai)"
_HF_UA = "Mozilla/5.0"


def get_crossref_citation(title: str) -> int | None:
    encoded_title = urllib.parse.quote(title)
    url = f"https://api.crossref.org/works?query.bibliographic={encoded_title}&rows=1"
    try:
        data = http_get_json(url, headers={"User-Agent": _CROSSREF_UA}, timeout=3)
        items = data.get("message", {}).get("items", [])
        if items:
            return int(items[0].get("is-referenced-by-count", 0))
    except Exception:
        pass
    return None


def get_huggingface_upvotes(arxiv_id: str) -> int | None:
    if not arxiv_id:
        return None
    url = f"https://huggingface.co/api/papers/{arxiv_id}"
    try:
        data = http_get_json(url, headers={"User-Agent": _HF_UA}, timeout=3)
        upvotes = data.get("upvotes")
        return int(upvotes) if upvotes is not None else None
    except Exception:
        return None
