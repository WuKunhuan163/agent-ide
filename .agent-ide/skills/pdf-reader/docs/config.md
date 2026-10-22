# pdf-reader parameters

Generated from `src/config/schema.py` -- do not edit by hand. Regenerate with
`pdf-reader config list --markdown`.

A value comes from the first of these that names it: `--set KEY=VALUE` on a
`read`/`fetch` call (this invocation only), the environment variable in the
**env** column, `data/config.json` (written by `config set`), then the default.
Upper bounds are pinned to the endpoint's own ceilings, so a parameter cannot be
raised into a value the service would refuse anyway.

Where a number comes from is marked in the **source** column: `[D1]` the official
API documentation, `[D2]` the ecosystem repository, `[D3]` the official client's
own defaults, `[T]` measured against the live endpoint, `[C]` carried over from
the archived tool, `[?]` no published value exists.

## common

| key | default | bounds | env | what it does | source |
|---|---|---|---|---|---|
| `common.request_timeout_s` | `60` | 5..300 | `PDF_READER_COMMON_REQUEST_TIMEOUT_S` | per-HTTP-request timeout for link requests and state probes | [?] no official value; measured 0.16s (link request) / 0.75s (state probe) |
| `common.upload_timeout_s` | `300` | 30..1800 | `PDF_READER_COMMON_UPLOAD_TIMEOUT_S` | timeout for one PUT upload; on expiry the job is retried | [D3] SDK upload read-timeout is 300s |
| `common.poll_init_s` | `2` | 1..30 | `PDF_READER_COMMON_POLL_INIT_S` | first polling interval | [T] local uploads reach done in 6-16s, so a 2s first probe is fine |
| `common.poll_max_s` | `30` | 5..300 | `PDF_READER_COMMON_POLL_MAX_S` | top of the polling backoff | [T] worst observed completion is ~38s (URL input) |
| `common.poll_total_timeout_s` | `1800` | 60..7200 | `PDF_READER_COMMON_POLL_TOTAL_TIMEOUT_S` | total wall-clock budget for one run before it is declared stalled | [D3] SDK batch-level timeout is 1800s |
| `common.retry_max` | `3` | 0..10 | `PDF_READER_COMMON_RETRY_MAX` | retry budget per job | [C] carried over from the archived tool (--retries 3) |
| `common.concurrency_initial` | `4` | 1..64 | `PDF_READER_COMMON_CONCURRENCY_INITIAL` | in-flight job budget at the beginning of a run | [T] 6 concurrent flash jobs succeeded with zero 429; 4 is the conservative start |
| `common.concurrency_max` | `6` | 1..64 | `PDF_READER_COMMON_CONCURRENCY_MAX` | ceiling for the adaptive in-flight budget | [?] no published ceiling; [T] 6 verified. Raise only after calibration |
| `common.concurrency_down_factor` | `0.5` | 0.1..0.9 | `PDF_READER_COMMON_CONCURRENCY_DOWN_FACTOR` | multiplier applied to the budget when -60009 or 429 is observed | [?] policy value, not documented |
| `common.concurrency_up_step` | `1` | 1..4 | `PDF_READER_COMMON_CONCURRENCY_UP_STEP` | increment applied to the budget after a clean streak | [?] policy value, not documented |
| `common.concurrency_probe_after` | `3` | 1..10 | `PDF_READER_COMMON_CONCURRENCY_PROBE_AFTER` | consecutive successes required before probing the budget upwards | [?] policy value, not documented |
| `common.backoff_steps` | `[2, 4, 8, 16, 30]` | - | `PDF_READER_COMMON_BACKOFF_STEPS` | sleeps used by the retry/poll backoff | [?] fixed sequence replacing the old POLL_FACTOR/RETRY_DELAY pair |
| `common.quota_reset_tz` | `Asia/Shanghai` | - | `PDF_READER_COMMON_QUOTA_RESET_TZ` | timezone whose midnight resets the local ledger (the endpoint never says when its own day rolls over) | [C] the archived key pool reset on the Beijing calendar day |

## precision

| key | default | bounds | env | what it does | source |
|---|---|---|---|---|---|
| `precision.split_page_limit` | `200` | 1..200 | `PDF_READER_PRECISION_SPLIT_PAGE_LIMIT` | a source larger than this is split by page range, never physically | [D1] 'file pages must not exceed 200'; also the -60006 trigger |
| `precision.max_file_mb` | `200` | 1..200 | `PDF_READER_PRECISION_MAX_FILE_MB` | admission check; an oversized file is refused before submission | [D1] 'single file size must not exceed 200MB' (-60005) |
| `precision.link_batch_size` | `50` | 1..50 | `PDF_READER_PRECISION_LINK_BATCH_SIZE` | how many files one link request carries (the real batch ceiling) | [D1] 'a single request may not ask for more than 50 links' |
| `precision.daily_page_quota` | `1000` | 1..100000 | `PDF_READER_PRECISION_DAILY_PAGE_QUOTA` | basis of the local page ledger; exceeding it warns, it does not refuse | [D1] 'each account gets 1000 pages/day at top priority'; beyond that priority drops |

## flash

| key | default | bounds | env | what it does | source |
|---|---|---|---|---|---|
| `flash.split_page_limit` | `20` | 1..20 | `PDF_READER_FLASH_SPLIT_PAGE_LIMIT` | a source larger than this is split by page range before submission | [D1] flash page limit is 20 (-30003) |
| `flash.max_file_mb` | `10` | 1..10 | `PDF_READER_FLASH_MAX_FILE_MB` | admission check | [D1] flash size limit is 10MB (-30001) |
| `flash.daily_file_quota` | `null` | 1..100000 | `PDF_READER_FLASH_DAILY_FILE_QUOTA` | optional local file ledger for flash; null disables the ledger | [?] user reports 5000 files/day on the web UI; absent from every public doc |

