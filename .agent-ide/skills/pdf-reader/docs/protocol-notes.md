# How requests are shaped, and the traps that shaped them

Everything here was paid for once. Each item is a rule the client follows, the evidence that
produced it, and what goes wrong when it is ignored. Implementation lives in
`src/endpoint/`.

## Uploading: send the bytes, and nothing else

The service hands back a signed upload URL, and the client must `PUT` the file to it **with
no content type and no extra headers**. The signature covers the URL, not a set of headers,
so an added header makes the storage service reject the request with a signature mismatch —
which reads exactly like a broken upload channel.

The trap is that Python's standard-library URL opener *adds* a form content type to any
request that has a body. A client written with it cannot obey the rule by accident. This one
therefore drops to a lower-level HTTP client for the transfer, where the header set is
exactly what it says. The official documentation states the rule outright ("uploading a file
requires no content type header"); the recorded misdiagnosis — "the local upload channel is
unavailable", concluded after adding the header itself and getting a 403 — is what happens
when the rule is discovered by experiment instead of read.

A second trap in the same area: after a successful upload, the task does not change state
immediately. It reports "waiting for file", and only after the server's periodic scan
notices the object does it move to "uploading" and then to the queued and running states —
observed at 15–16 seconds on this machine, and 6–11 seconds under concurrency. A client that
gives up inside that window concludes, wrongly, that the channel is broken. Polling is
cheap, so waiting is the right answer.

## Transport: verify, and find a certificate store

A stock interpreter on this machine has no usable default trust store, so a bare HTTPS call
fails with a certificate error — and a failure that looks like a service outage is a
misleading thing to report. The client builds a verifying context from the first of: the
conventional certificate environment variables, a bundled certificate package if present,
then the interpreter's own default. Verification is never disabled, and a transport failure
is classified separately from a service failure so the advice is not misdirected.

## State: ask the bare endpoint, once each

Two shapes of state query exist, and only one of them is a status check:

- precision — one request for the whole batch returns, per file, a name, a state, a message
  and (when finished) the archive address. Four fields, no per-file code.
- flash — one request per task returns a state, a message, **and a code**. Using the state
  alone discards the only structured signal flash provides; a page-limit refusal then arrives
  as an anonymous "failed" and the window ladder never starts.

The official SDK is not used. Three reasons, in order of how much damage each does:

1. its batch call **downloads the entire result archive** every time it observes a finished
   file, so a status poll silently becomes a transfer;
2. it raises on HTTP error status *before* parsing the body, which means its own
   authentication error can never fire — the failure escapes as a transport exception
   instead, and the caller retries a rejected token against a wall;
3. it exposes the archive's internal files through private fields, so an unofficial layout
   becomes a dependency.

## Handles and expiry

A batch handle is meaningful outside the process that created it: a fresh process can ask
about the same batch, which is what makes it possible to rescue a run whose local record was
lost. The converse is that results are not kept forever — a finished task reports as expired
after a while, so products should be collected when they are wanted rather than re-fetched
later.

## Two envelopes, one failure

Business failures arrive as HTTP 200 with a code in the body; authentication failures arrive
as HTTP 401 with a trace id and a message code and no code at all. Parsing only the first
shape is what made the archived tool's credential error dead code. The client reads the body
of every reply — including error statuses — and classifies from what it finds, so the
credentials path and the business path converge on one failure object. `errors.md` describes
the verdicts; this document only records the shapes.

## What deliberately never happens

- **No credentials are sent anywhere except the endpoint host**, in a bearer header. The
  token is a cloud credential; the local path never sees it.
- **No certificate verification is ever skipped**, even to make a broken environment work.
- **No result archive is fetched to answer "is it finished?"** — that is what the state probe
  is for.
- **No upload carries a header the signature does not cover.**
