# Failures, and what a run is allowed to do about them

## Two shapes of failure

The same service reports failures in two shapes that do not resemble each other:

- a **business** failure arrives with an HTTP 200 and a body carrying a code and a
  message;
- an **authentication** failure arrives with HTTP 401 and a body carrying a trace id, a
  message code, a message and a success flag — and no code at all.

A client that only understands the first shape sees the second as a raw transport error.
That is precisely what happened in the archived tool: its credential error was written to
fire on a rejected token, but the token rejection escaped earlier as a transport
exception, so the error never fired and the tool retried against a wall. Both shapes are
therefore collapsed into one failure object here, and every failure is mapped to a verdict
before anything decides what to do next.

## The verdict table

| verdict | codes / conditions | what the run does, and what the caller is told |
|---|---|---|
| retry and back off | a full submission queue; HTTP 429; an internal failure | wait along the backoff, **lower the in-flight budget**, requeue while attempts remain — "the server is busy or throttling" |
| network trouble | transport failures: DNS, TLS, timeouts | same treatment, but with its own wording, so a certificate problem is not blamed on the service |
| split required | the page limit | if the job was blind, replace it with page windows and continue; otherwise fail it |
| input refused | wrong file type, file too large | fail that file and never retry — nothing about retrying makes it smaller |
| allowance exhausted | daily task count, HTML allowance | **halt the whole run**, and say to come back tomorrow |
| token rejected | a bad or expired token | halt, and say to store a new token — no rotation loop, no repeated attempts |
| URL unreadable | the endpoint could not fetch the given URL | fail that input, and suggest uploading the file instead |
| flash channel refused | a size the channel cannot take | fail, and suggest the other channel |
| already finished or expired | the task is missing or has expired server-side | treat it as gone, and re-run the source if the results are still wanted |
| anything else | an unrecognised failure | fail that job, keeping the raw message |

Two of these end the run rather than the job (allowance exhausted, token rejected),
because continuing would only burn attempts against a wall. Two of them lower the
concurrency rather than the job (queue full, throttling), because the limit is not the
file's fault. The distinction is the whole point of classifying: the caller is told to
split, to wait, to come back tomorrow, or to store a token — never merely given a code.

## Failures that arrive as text

A precision batch reports each of its files with a name, a state, a message and an archive
address — and **no code**; a flash task, by contrast, reports a code. So for a batch the
kind of failure has to be recovered: from the code when the service happens to include one
in the message, and otherwise from the wording, in either language.

The order of those wording tests carries weight. The service's own page-limit sentence and
its own daily-allowance sentence are both written as "reached its upper limit", so the
page test has to come first; reading them the other way round would classify an ordinary
page-limit refusal as a spent daily allowance and stop the run for the day. Without any of
this, a page-limit refusal and a momentary hiccup look identical and a file that simply
needed splitting would never be split.
