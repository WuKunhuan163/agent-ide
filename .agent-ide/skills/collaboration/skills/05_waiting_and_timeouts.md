This booklet is the rule set for how long a call is allowed to take, and what a call that has not returned means. It governs **timing, not task content**. The failure it exists to prevent has two faces: the agent that fires a command with no idea whether it takes two seconds or twenty minutes and then sits on it, and the agent that treats "nothing came back yet" as "it failed" and loses a reply that was still being written.

# 1. Every call has a duration, and it must be estimated first

- Before running anything, place it in one of three buckets: **seconds**, **minutes**, **unknown**.
- Unknown is not permission to fire it. Unknown means: find out first — a `--help`, a dry run, a one-item sample, a status endpoint.
- A command whose duration cannot be bounded is not a foreground command. That is the whole rule; the buckets only make it checkable.
- The cost of a wrong guess is asymmetric. Guessing "seconds" on a twenty-minute build costs the entire turn; spending one cheap call to learn the real duration costs seconds.

# 2. Probe, then commit

- Escalate in steps, and let each step be cheap to fail: is the endpoint alive → does one item work → does a page work → does the full run.
- A probe that fails in two seconds tells you which layer is broken. A full run that fails after ten minutes tells you only that something is.
- When a long operation has a `--limit` / `--max` / `-n` that bounds it, use it for the first run. Never debug at full scale.
- Repeating a probe is waste; changing one variable between probes is progress. Decide which variable before the next call.

# 3. Foreground, background, or not at all

Foreground is for calls that end within the turn. Anything else needs all three of these, or it does not go to the background either:

- **Observable** — output goes to a file or a log the agent can read later, not to a pipe that vanishes with the shell.
- **Completable** — there is a signal that says it finished: exit-status file, marker line, process gone.
- **Wakeable** — the harness will bring the result back, or the next turn will look for it.

An unobservable background job is worse than a slow foreground one: the foreground at least fails visibly.

# 4. A timeout is not a verdict

A call that was cut off, killed, or returned nothing has an **unknown** outcome, not a failed one.

- Before re-running, check the side effects: did the file appear, did the row count change, is a process still alive, did the server log the request.
- Before re-running, check that no instance is still running. Two writers on one output is how a "retry" corrupts the result of a run that had succeeded.
- Report the state as it is — "the call was cut at N seconds, the artifact does or does not exist" — never as success or failure.
- Silence is not evidence. "No output" and "no result" are different claims, and only the second one needs proof.

# 5. The user channel blocks for as long as it takes

The contact channel is designed to wait indefinitely for a human. That is its semantics, not a bug, and it changes how it must be called:

- Do not wrap it in a short timeout. A cut-off contact costs a full round and returns nothing.
- Start it as its **own invocation**: write whatever the channel reads first, then call. Chaining the write and the call in one command means a failure at either half leaves a round that is half-written and unreadable.
- Where the harness exposes a blocking budget, give it the largest value it accepts. A call that returns `0` and is then polled is the worse option: nothing guarantees the poll ever happens.
- Do not call it again because "it has been quiet for a while". Two concurrent rounds on the same id collide; the second one queues or errors, and the reply can land in the wrong place.
- Exit code `4` means the user closed five windows — a decision, not a timeout. Exit code `0` with text means a reply arrived. Anything else is a real error worth reporting.
- When the wait will be long, write the current state down **before** entering it: what was being asked, what was already done, what the next step is. Then a long wait costs wall-clock time, not the work.
- If the harness itself cannot hold a blocking call that long, split the wait into a background call plus a later check. What is forbidden is abandoning the round because it did not return promptly.

# 6. When it looks stuck

Three checks, in this order, before any decision:

1. **Is it alive?** A process still running is not a hang.
2. **Is it producing?** New bytes in a log or output file mean progress, however slow.
3. **Did the side effect appear?** The file, the row, the commit — work that already completed does not need to be re-run.

If all three are negative, stop it, say where it stopped, and say what would distinguish "slow" from "broken" next time. Silent retries are the one thing that must not happen: they hide the failure and multiply the cost.

# 7. Budget the turn, not just the call

- A task has a wall-clock budget, implicit or stated. When it is exhausted, report what exists and what is left; do not extend it silently.
- With the user absent, the budget is tighter, not looser: do the parts that do not need an answer first, and leave one clearly stated question rather than an open-ended wait.
- A turn that ends with "here is what is done, here is what I am waiting on, here is the question" is a successful turn. A turn that ends with nothing, because a call never returned, is the failure this booklet is about.
