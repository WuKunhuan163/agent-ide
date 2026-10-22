#!/usr/bin/env python3
"""arXiv literature search CLI with cache, Crossref citations, and HF upvotes."""
import argparse
import sys

from src.run_search import run_search

_orig_exit = sys.exit


def clean_exit(code=0):
    sys.stdout.flush()
    _orig_exit(code)


sys.exit = clean_exit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="文献调研助手 - arXiv 官方高可用排异缓存架构")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--max_results", "-m", type=int, help="返回的新文献数量")
    parser.add_argument(
        "--sort_by",
        "-s",
        type=str,
        choices=["relevance", "submittedDate", "lastUpdatedDate"],
        default=None,
        help="排序方式：relevance, submittedDate, lastUpdatedDate（arxiv 默认 submittedDate，openalex 默认 relevance）",
    )
    parser.add_argument("--min_upvotes", type=int, default=0, help="最低 Hugging Face 每日点赞数过滤")
    parser.add_argument("--min_citations", type=int, help="最低 Crossref 引用数过滤")
    parser.add_argument("--abstract_contains", type=str, help="摘要必须包含的关键词（忽略大小写）")
    parser.add_argument("--max_eval", type=int, default=100, help="最大评估文献数量（防止死循环）")
    parser.add_argument("--delay", type=float, help="两次请求间的延迟（RPS控制）")
    parser.add_argument("--exclude-cache", action="store_true", help="启用排异模式")
    parser.add_argument("--source", choices=["arxiv", "openalex"], default="arxiv",
                        help="检索源：arxiv（默认）或 openalex（跨学科、带被引与 OA PDF）")
    parser.add_argument("--year_from", type=str, default=None,
                        help="openalex 源：起始年份，如 2023")
    parser.add_argument("--year_to", type=str, default=None,
                        help="openalex 源：结束年份")
    parser.add_argument("--in", dest="search_in", choices=["fulltext", "title_abstract"],
                        default="fulltext",
                        help="openalex 源：检索范围（title_abstract 更精确）")
    parser.add_argument("--download", action="store_true",
                        help="检索后直接下载命中的 PDF")
    parser.add_argument("--out", default=None, help="PDF 目标目录，默认 data/fetch/pdfs/")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="每条打印完整字段（默认每条一行：title<TAB>year<TAB>cites<TAB>pdf）")
    return parser.parse_args()


def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] == "download":
        from src.download import main_download

        sys.exit(main_download(argv[1:]))
    args = parse_args()
    query_stripped = args.query.strip() if args.query else ""
    if not query_stripped:
        print("[ERROR] Query string cannot be empty. Please provide at least one search keyword.", file=sys.stderr)
        sys.exit(1)
    if args.source == "openalex":
        from src.run_search import run_openalex_search

        records = run_openalex_search(args)
    else:
        records = run_search(args)

    if args.download and records:
        from src.download import download_records
        from src.paths import data_dir
        import os

        dest = args.out or os.path.join(data_dir(), "pdfs")
        pairs = [{"title": r.get("title", ""), "url": r["pdf_link"]}
                 for r in records if r.get("pdf_link")]
        missing = len(records) - len(pairs)
        if missing:
            print(f"[WARN] {missing} record(s) have no pdf link; skipped.", file=sys.stderr)
        if pairs:
            stats = download_records(pairs, dest, delay=args.delay or 1.2)
            print(f"\n{stats['ok']} new, {stats['present']} already present, "
                  f"{stats['skipped']} skipped, {stats['failed']} failed, "
                  f"{stats['bytes'] / 1048576:.1f} MB -> {dest}")
            if stats["failed"]:
                sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
