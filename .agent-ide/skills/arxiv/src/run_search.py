"""Search orchestration: pagination, filters, enrich, and output."""
from __future__ import annotations

import argparse
import sys

from src.arxiv_api import search_arxiv_chunk
from src.display import format_count, format_row
from src.enrich import get_crossref_citation, get_huggingface_upvotes
from src.persist import load_cache, load_default_config, save_cache, save_result_to_json


def run_search(args: argparse.Namespace) -> None:
    defaults = load_default_config()
    max_results = args.max_results if args.max_results is not None else defaults.get("max_results", 5)
    min_citations = (
        args.min_citations if args.min_citations is not None else defaults.get("min_citations", 0)
    )
    sort_by = args.sort_by if args.sort_by is not None else defaults.get("sort_by", "submittedDate")
    delay = args.delay if args.delay is not None else (3.0)

    history_cache = load_cache()
    new_cache_entries: set[str] = set()
    processed_papers: list[dict] = []
    results_shown = 0
    total_evaluated = 0
    start_index = 0
    chunk_size = 10
    abstract_contains = args.abstract_contains.lower() if args.abstract_contains else None

    while results_shown < max_results and total_evaluated < args.max_eval:
        papers_chunk = search_arxiv_chunk(
            args.query,
            start=start_index,
            max_results=chunk_size,
            sort_by=sort_by,
            delay=delay,
        )
        if not papers_chunk:
            break

        for paper in papers_chunk:
            if results_shown >= max_results or total_evaluated >= args.max_eval:
                break

            total_evaluated += 1
            is_cached = paper["id"] in history_cache

            if is_cached and args.exclude_cache:
                print(f"[cached] {paper['title']}", file=sys.stderr)
                continue

            if abstract_contains and abstract_contains not in paper["summary"].lower():
                continue

            hf_upvotes = get_huggingface_upvotes(paper["id"])
            if (hf_upvotes or 0) < args.min_upvotes:
                continue

            cites = get_crossref_citation(paper["title"])
            if min_citations > 0 and (cites or 0) < min_citations:
                continue

            if is_cached:
                tag = " (In History Cache)"
            else:
                tag = ""
                new_cache_entries.add(paper["id"])

            results_shown += 1
            pub_date = paper["published"][:10]
            authors = paper["authors"]
            if getattr(args, "verbose", False):
                print(f"[{results_shown}/{max_results} (evaluated {total_evaluated})]{tag} {paper['title']}")
                print(f"    Published: {pub_date}")
                print(f"    Authors: {', '.join(authors[:5])}{' et al.' if len(authors) > 5 else ''}")
                print(f"    PDF: {paper['link']}")
                print(f"    Citations: {format_count(cites)} | HF Upvotes: {format_count(hf_upvotes)}")
            else:
                print(format_row(paper["title"], pub_date[:4], format_count(cites), paper["link"]))
            sys.stdout.flush()

            processed_papers.append(
                {
                    "title": paper["title"],
                    "year": pub_date[:4],
                    "authors": authors,
                    "pdf_link": paper["link"],
                    "citations": format_count(cites),
                    "hf_upvotes": format_count(hf_upvotes),
                    "abstract": paper["summary"],
                }
            )

        if len(papers_chunk) < chunk_size:
            break
        start_index += chunk_size

    if total_evaluated >= args.max_eval and results_shown < max_results:
        print(
            f"[INFO] Reached evaluation limit ({args.max_eval}) before finding {max_results} matching papers.",
            file=sys.stderr,
        )

    if processed_papers:
        save_result_to_json(processed_papers)
    if new_cache_entries:
        history_cache.update(new_cache_entries)
        save_cache(history_cache)
    return processed_papers


def run_openalex_search(args: argparse.Namespace) -> list[dict]:
    """Same CLI, different source: one OpenAlex request, same record shape."""
    from src.openalex_source import search_works

    max_results = args.max_results if args.max_results is not None else 10
    sort_by = args.sort_by or "relevance"
    if sort_by == "lastUpdatedDate":
        print("[WARN] openalex has no last-updated sort; falling back to relevance.",
              file=sys.stderr)
        sort_by = "relevance"
    try:
        records, total = search_works(
            args.query,
            max_results,
            sort_by=sort_by,
            year_from=args.year_from,
            year_to=args.year_to,
            search_in=args.search_in,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] openalex request failed: {exc}", file=sys.stderr)
        return []

    if not records:
        print("[WARN] openalex returned no results.", file=sys.stderr)
        return []

    print(f"[openalex] {total} matches", file=sys.stderr)
    for r in records:
        if getattr(args, "verbose", False):
            print(f"{r['title']}")
            print(f"    Year: {r['year']} | Venue: {r['venue']}")
            print(f"    Authors: {', '.join(r['authors'][:5])}")
            print(f"    Cited by: {r['citations']} | DOI: {r['doi']}")
            print(f"    PDF: {r['pdf_link'] or '-'}")
        else:
            print(format_row(r["title"], r["year"], r["citations"], r["pdf_link"]))

    save_result_to_json(records)
    return records
