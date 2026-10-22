---
name: aliyunpan
description: >-
  A resumable transfer channel to Aliyun Drive: login once per agent id, then upload
  files or folders, download, list, move and delete. Parts, the endpoint's part-count
  ceiling, rate limiting and resume state are handled here, so a killed transfer
  continues where it stopped instead of starting over.
---

# aliyunpan

One channel, one job: move bytes between this machine and the backup drive, and
survive being interrupted while doing it.

Every command is non-interactive except `login`, which hands the authorization URL
to the system browser and waits for the credential file to become valid.

## What it guarantees

1. **Never overwrites.** A destination name that already exists is refused before
   any byte is sent. Renaming or deleting is a decision for the user, not a
   side effect of an upload.
2. **Resumes at part granularity.** The partition is fixed once per file and
   written to disk with the parts already acknowledged; a rerun sends only what is
   missing.
3. **Stays under the endpoint's limits.** A sliding one-second window caps the
   request rate, and the part count of a file is checked against the endpoint's
   ceiling *before* creating the upload — a plan that would exceed it is widened,
   not truncated.
4. **Refuses to guess paths.** Every path is resolved by listing one level at a
   time; a cached folder id would silently write into the wrong folder after
   someone renames things in the web UI.
5. **One id, one identity.** Each agent id has its own credential and resume
   state; two ids never refresh the same token behind each other's back.

## Commands

```bash
A=.agent-tools/aliyunpan

$A --id <id> login                       # opens the browser, stores credentials
$A --id <id> who                         # account, backup drive, token
$A --id <id> ls /Backup/exp              # list a folder
$A --id <id> upload ./runs/v3 /Backup/exp/v3
$A --id <id> download /Backup/exp/v3/out.mp4 ./local
$A --id <id> mkdir /Backup/exp/v4
$A --id <id> mv /Backup/exp/v3 /Backup/archive
$A --id <id> rm /Backup/exp/old.mp4
```

`upload` takes one or more local files or folders followed by the remote
directory; folders are walked and their structure is recreated remotely. `--json`
turns any command's stdout into one object, which is what a caller should parse —
the human-readable lines are for reading.

## Before uploading, look

```bash
$A --id <id> ls /Backup/exp
```

Confirm the target folder exists and holds what you think it holds. Uploading into
a path that does not exist creates it, and a path typed one character off becomes
a second folder that nobody notices until the restore.

## What the endpoint actually requires

Measured against the live API on 2026-10-22, same account, same link:

| Shape | Result |
|---|---|
| 1 part (≤512 KB) | `200`, file completes |
| 2+ parts at once, no `parallel_upload` | part 1 `200`, the rest `400 PartNotSequential` |
| PUT with a `Content-Type` the create call did not declare | `403 SignatureDoesNotMatch` |
| `parallel_upload: true` + per-part `parallel_sha1_ctx`, 8 parts at once | 8 × `200`, `complete` accepted, file intact |
| 8 parts, one at a time, ascending | every part `200`, `complete` accepted |
| 8 parts of 512 B | every PUT `200`, `complete` `400 InvalidResource.PartList` (`part entity too small`) |
| 2 parts of 96 KB | `complete` `400`, same code |
| 2 parts of 100 KB | `complete` `200`, file intact |
| 4 parts of 256 KB | `complete` `200`, file intact |
| 10 MB part on a 20 kB/s link | `write operation timed out` |

Five facts follow, and only the fourth is optional:

1. **Sequential multipart is the default.** Part N is accepted only after N-1 is
   stored. The archived module expressed this as `max_concurrent_chunks = 1`: its
   ten threads served *different files*, never two parts of one file.
2. **`content_type` joins the signature.** `CreateFile.content_type` is documented
   as: if the value set here differs from the `Content-Type` used on the PUT, the
   signature fails. Sending `application/octet-stream` on the PUT while create
   declared nothing produces `403 SignatureDoesNotMatch`, reproducibly. The fix is
   to send no header at all, not to retry.
3. **`getUploadUrl` re-signs.** A url fetched for one part invalidates a url held
   from `create`, so a fresh url is fetched immediately before every PUT.
4. **Parallel parts are possible but must be declared.** `parallel_upload: true`
   plus, for every part, `parallel_sha1_ctx {h: [five 32-bit SHA-1 state words],
   part_offset: bytes before this part, multiple of 64}` makes the server hand back
   one url per part and accept them out of order. Without the context it refuses to
   interleave. `h` is the SHA-1 state *before* the part, which `hashlib` does not
   expose; the probe in "Measurement log" computes it.
5. **`complete` enforces a 100 KB floor.** A PUT of 512 B succeeds and is stored,
   but merging it returns `400 InvalidResource.PartList` with "part entity too
   small". 96 KB is refused, 100 KB passes. Separately, the official `CreateFile`
   page caps `part_info_list` at 10000 entries and a single part at 5 GB. The two
   numbers are different constraints: 100 KB is the *size* floor the merge checks,
   10000 is the *count* ceiling.

A dropped TLS connection is a failed part, not a failed upload: it is retried in
place, and the rest of the plan is untouched.

## Link behaviour (measured)

Same machine, same minute, 1 MB each:

| Target | Concurrency | Throughput |
|---|---|---|
| Cloudflare `__up` | 1 | 7.96 MB/s |
| Aliyun Drive | 1 | 18.4 kB/s |
| Aliyun Drive | 2 | 26.6 kB/s |
| Aliyun Drive | 3 | 34 kB/s |
| Aliyun Drive | 10 | ≈210 kB/s |

`ping` explains the gap: `openapi.alipan.com` loses 25% of 40 packets,
`cn-beijing-data.aliyundrive.net` loses 20%, while `aliyundrive.com` and Cloudflare
lose none. The upstream itself is 63 Mbps.

The practical consequence: **throughput grows with connections, not with part
size.** One file is one connection while parts are sequential, so a single file is
capped at roughly 20–40 kB/s until parallel parts are enabled. Widening parts makes
it worse, because a part has to finish inside the socket timeout.

## How a transfer runs

One pool of threads over a shared claim list — the unit is a **chunk**, not a file:

```
prepare(file) → sha1 → create upload (declares ceil(size/min_chunk) parts, ≤10000)
                          → resume from (offset, part, quota) if a record exists
              → FileState enters the pool
thread: take() → {file_key, part_num, offset, chunk_size}
              → getUploadUrl(part) → PUT → done() or failed()
complete(file) → resume record deleted
```

- **`take()` is the whole scheduler.** It picks any file with
  `active_chunks < max_concurrent_chunks` and `remaining_size > 0`, decides a chunk
  size, and advances that file's `offset`/`part_num`/`quota` under one lock. Uploads
  run with `max_concurrent_chunks = 1`, so threads spread across files and never
  interleave two parts of one file. Raising it to N is what turns on parallel parts,
  and it requires `parallel_upload` (see above) or the server answers
  `PartNotSequential`.
- **Chunk size is a time budget, not a byte count.** `take()` computes
  `chunk_bytes = measured speed × target_seconds` (speed smoothed by EWMA 0.7/0.3),
  floored by `max(min_chunk, ceil(remaining / quota))`, with the tail merged when
  it would fall under `min_chunk`. The default `target_seconds` is 1.0, the value
  the archived dispatcher had hard-coded; raising it lowers the part count without
  touching the decision code. `--bs` replaces the time budget with a fixed size.
  The first chunk doubles as the speed probe and is sized before any sample exists,
  so it is the one chunk that cannot follow the measured link.
- **Cutting stops below two chunks.** If the remainder is under `2 × chunk_bytes`,
  it is merged whole rather than leaving a tail smaller than `min_chunk`. This is a
  count rule, not a second time constant: `two_chunks = 2 * chunk_bytes`.
- **The algorithm is separate from its knobs.** `TransferOptions` carries
  `min_chunk`, `target_chunk`, `target_seconds`, `max_concurrent_chunks` and
  `max_threads`; `scheduler` only consumes them. `--bs` (KB, 0 = adaptive) and
  `-p` (threads) are the command-line spelling. Changing a number never means
  editing `take()`.
- **A failed chunk is rolled back**, not retried by the same thread: `failed()`
  restores `offset`, `part_num` and `quota`, so the next `take()` offers the same
  range to any thread. A chunk that is refused for a reason repetition cannot fix
  (`400`, `403`, `409`) is not retried at all.
- `content_hash` (sha1) goes up with the create call: a file the drive already has
  completes without transferring bytes.
- State lives in `data/<id>/resume/<sha1-16>-<size>.json`, rewritten after every
  acknowledged part, and disappears when the file completes. Deleting it forces a
  clean restart; leaving it lets the next run resume.

## Modules

| Path | Owns |
|---|---|
| `aliyunpan.py` | command surface: parse, dispatch, print |
| `src/login.py` | the one interactive step: URL out of the CLI, browser, wait |
| `src/session.py` | credentials, backup drive, rate limit, retries, 401 refresh |
| `src/remote.py` | paths ↔ ids, list, stat, mkdir, move, delete, name refusal |
| `src/scheduler.py` | chunk claiming (`FileState`, `Dispatcher`) and download partitions |
| `src/transfer.py` | upload/download orchestration and resume state |
| `vendor/tickstep-source/` | the login client's source, for reference when the protocol moves |

`bin/aliyunpan` is only used for login; transfers are done here, over the API, so
that progress, retries and resume are observable rather than closed inside a
binary.

## Boundaries

- No mirroring or scheduled sync: this moves what it is told to move.
- No silent overwrite, and no automatic rename — a name collision is an error.
- No background daemon: an interrupted transfer is resumed by rerunning the
  command.

## Measurement log

Everything below was run on 2026-10-22 against the live account, not inferred.

**Signature failure.** A 5 MB upload failed every part with `400`, then with
`403 SignatureDoesNotMatch`. The PUT had been given
`Content-Type: application/octet-stream` while `create` declared none. Removing the
header made a 1 MB upload succeed (`200`, 55.8 s, 18.4 kB/s). Official field text
for `CreateFile.content_type`: *"if the Content-Type specified by the client
differs from this value, a signature error occurs."*

**Throughput vs. connections.** Ten 1 MB files, generated from `/dev/urandom`, sent
in parallel to the same folder: nine completed within 44 s, ≈210 kB/s aggregate,
against 18.4 kB/s for one. Each file took 25–44 s on its own, so the gain is
connection count, not per-file speed.

**Loss.** `ping -c 40 -i 0.3 openapi.alipan.com` → 30 received (25% loss).
`ping -c 10 cn-beijing-data.aliyundrive.net` → 8 received. `aliyundrive.com` → 10/10.
`curl -X POST --data-binary @1MB https://speed.cloudflare.com/__up` → 7,959,374 B/s.

**Parallel parts.** `create` with `parallel_upload: true` and eight
`parallel_sha1_ctx` entries returned eight `upload_url`s; eight concurrent PUTs all
returned `200`; `complete` returned `200`; the drive listed the file at 8.0 MB. The
SHA-1 state was computed by a local compression function and verified against
`hashlib` for block counts 0/1/2/3 before use.

**SHA-1 context recipe.** `h` starts as the five SHA-1 initial constants, is advanced
one 64-byte block at a time over all bytes preceding the part, and is *not* padded.
`part_offset` is that byte count and must be a multiple of 64. Python's `hashlib`
does not expose this state, so it must be computed.

**Algorithm boundary checks.** Besides the live runs, `Dispatcher.take()` was
exercised without a network: size 0 → 0 chunks; 1 byte → 1; exactly 512 KB → 1;
512 KB + 1 → 1 (tail merged); 1.5 MB → 3; 10 MB → 20 at the 512 KB floor;
`target_chunk = 2 MB` on 5 MB → 2 MB + 3 MB; `max_concurrent_chunks = 3` yielded
`OK, OK, OK, WAIT` and left `active_chunks = 3`. Every case summed back to the
input size.

**`target_seconds` sweep (offline).** On 1 GB: at 18.4 kB/s, 1 s → 2048 chunks,
60 s → 880; at 1 MB/s, 1025 → 18; at 10 MB/s, 105 → 4. The sweep also exposed a
flaw that is now fixed: the first chunk used to be sized from
`initial_speed = min_chunk` (512 KB/s) before any measurement, so at
`target_seconds = 60` it became 30 MB and outlived the 15-minute `upload_url` on
an 18.4 kB/s link. `take()` now pins the first chunk to `min_chunk` whatever
`target_seconds` says (`src/scheduler.py`, the `next_part_num == 1` branch), so a
1 MB upload still goes out as 512 KB + 512 KB.

**Still open.** The multi-file pool has only been run against a fake endpoint
(`tests/test_pool.py` asserts peak concurrency, byte totals and retry counts); it
has not been exercised against the live API with several large files at once.

Single-file `upload_many` is proven end to end: 1 MB as one part, 1 MB as
4 × 256 KB, and 4 KB as 8 × 512 B (all PUTs `200`, `complete` refused for size).

## Tests

```bash
cd .agent-ide/skills/aliyunpan && PYTHONPATH=. python3 -m unittest discover -s tests -t .
```
