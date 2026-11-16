# 01 · Time budget and quick-fail discipline

> **Maintenance policy**: throughput first. Finding a paper or fetching full text fails fast by default; the budget is lifted only in the rare case where the user explicitly asks to keep digging.

## Default time budget

**Fail fast on a budget, not on a hunch**: each step below has a time it may take and what to do when that time runs out.

| Step | Budget | On timeout |
|---|---|---|
| Single-record metadata lookup (crossref search/work) | ≤ 1 minute | change the query once, then record "not found" |
| Full-text fetch of one paper | ≤ 5 minutes, ≤ 3 sources | record "full text not obtained + reason" |
| Batch (e.g. 7 papers) | timed per paper; one slow paper must not stall the batch | mark the stuck ones pending and move on |

## Giving up (any one of these, by default)

1. Unpaywall/OpenAlex/Crossref all say `is_oa=False` (paywalled, no lawful OA) → drop the full text, keep metadata + abstract
2. The download returns HTML / a captcha / 403 (anti-scraping) and two other sources fail the same way → drop it
3. The channel is Sci-Hub or any mirror of that kind → never attempted (copyright line)

## Exceptions (the few cases where the budget is lifted)

- The user or decision-maker says "keep looking", "we need the file", "try again"
- The work is foundational or highly cited, so an open mirror is likely — two extra university mirrors are allowed
- The user supplies credentials or a way to download it through their own browser

## Output convention

When a paper is dropped, the report says so explicitly: `refXXX full text not obtained | reason: paywalled, no OA / SPA anti-scraping / 403 | alternative: none`.
No silent failure, and no endless detour.
