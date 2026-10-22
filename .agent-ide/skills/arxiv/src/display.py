"""Terminal formatting helpers."""
from __future__ import annotations


def truncate_abstract(text: str, max_words: int = 10) -> str:
    words = text.strip().replace("\n", " ").split()
    if len(words) > max_words:
        return " ".join(words[:max_words]) + "..."
    return " ".join(words)


def format_count(value: int | None) -> str:
    return str(value) if value is not None else "N/A"


def format_row(title: str, year: str, citations, url: str | None) -> str:
    """One record per line, tab separated: safe for cut/awk, no colour."""
    clean = (title or "").replace("\t", " ").replace("\n", " ").strip()
    return "\t".join([clean, str(year or "?"), str(citations), url or "-"])
