"""OpenAlex as a second search source for this CLI.

Everything returns the same record shape the arXiv path produces, so display,
persistence and the download engine do not need to know which source answered:

    {"title", "year", "authors", "pdf_link", "citations", "abstract",
     "doi", "venue", "openalex_id", "source": "openalex"}
"""
from __future__ import annotations

import urllib.parse

from src.http import http_get_json

BASE_URL = "https://api.openalex.org"
UA = "arXivResearchTool/2.0 (mailto:contact@cursor.ai)"

# arxiv's --sort_by vocabulary mapped onto OpenAlex's sort syntax.
SORT_MAP = {
    "relevance": None,
    "submittedDate": "publication_date:desc",
    # lastUpdatedDate has no OpenAlex equivalent; callers fall back to relevance.
}


def _normalize_date(value: str) -> str:
    v = str(value).strip()
    parts = v.split("-")
    if len(parts) == 1:
        return f"{v}-01-01"
    if len(parts) == 2:
        return f"{v}-01"
    return v


def _pdf_url(work: dict) -> str | None:
    url = (work.get("best_oa_location") or {}).get("pdf_url")
    if url:
        return url
    for loc in work.get("locations") or []:
        if (loc or {}).get("pdf_url"):
            return loc["pdf_url"]
    return None


def _rebuild_abstract(index: dict | None) -> str:
    if not index:
        return ""
    slots: dict[int, str] = {}
    for word, positions in index.items():
        for p in positions:
            slots[p] = word
    return " ".join(slots[i] for i in sorted(slots))


def search_works(query: str, per_page: int = 10, *, sort_by: str = "relevance",
                 year_from: str | None = None, year_to: str | None = None,
                 search_in: str = "fulltext", timeout: float = 60) -> tuple[list[dict], int]:
    """One request; OpenAlex caps per-page at 200 and has no cursor here."""
    per_page = max(1, min(int(per_page), 200))
    filters = []
    if year_from:
        filters.append(f"from_publication_date:{_normalize_date(year_from)}")
    if year_to:
        filters.append(f"to_publication_date:{_normalize_date(year_to)}")

    if search_in == "title_abstract":
        filters.append(f"title_and_abstract.search:{query}")
        params = []
    else:
        params = ["search=" + urllib.parse.quote(query)]
    if filters:
        params.insert(0, "filter=" + urllib.parse.quote(",".join(filters)))
    sort = SORT_MAP.get(sort_by)
    if sort:
        params.append("sort=" + urllib.parse.quote(sort))
    params.append(f"per-page={per_page}")

    data = http_get_json(f"{BASE_URL}/works?" + "&".join(params),
                         headers={"User-Agent": UA}, timeout=timeout)
    total = (data.get("meta") or {}).get("count", 0)
    records = []
    for w in data.get("results") or []:
        src = ((w.get("primary_location") or {}).get("source") or {})
        records.append({
            "title": w.get("display_name") or "",
            "year": str(w.get("publication_year") or ""),
            "authors": [a.get("author", {}).get("display_name", "")
                        for a in (w.get("authorships") or [])][:10],
            "pdf_link": _pdf_url(w),
            "citations": w.get("cited_by_count", 0),
            "abstract": _rebuild_abstract(w.get("abstract_inverted_index")),
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "venue": src.get("display_name"),
            "openalex_id": (w.get("id") or "").rsplit("/", 1)[-1],
            "source": "openalex",
        })
    return records, total
