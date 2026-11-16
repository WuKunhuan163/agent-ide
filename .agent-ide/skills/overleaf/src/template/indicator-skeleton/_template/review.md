# Collection checklist (when the user asks for an "assessment / collection", tick each item)

- [ ] **1 Frame the round**: fix `# rN` and its start and end; criteria come from the reply body only
- [ ] **2 Check each block**: does `returns/#n.md` exist, is its first line `id:` + `# unit #n`, is `status` legal
- [ ] **3 Judge the execution**: the four steps of `guide-repro-test.md` (frame the round → take the body → take the actions → open files last), every verdict carrying `L<line>`
- [ ] **4 Write the verdict**: `returns/#n-verdict.md`, first line `verdict: pass|fail|marginal`, second line `by: L<line>`
- [ ] **5 Pop the queue**: **the queue is the undispatched pool** — dispatch already popped it; collection only writes `returns/#n-verdict.md` (`task-queue resolve` is for voiding or cancelling, and only at the head)
- [ ] **6 Change the state**: the corresponding row of `LOOP_STATE.md`; top up `## EXIT-READINGS` when needed
- [ ] **7 Attribute**: on a fail tick one — a cutting problem / a dispatch problem / an execution problem
- [ ] **8 Flow back**: one `cutting observation: …` row in the `LEDGER`, and read the last three rows before the next cut
- [ ] **9 Run the ruler**: `check.py <id>` → `PASS 12/12`

**The order cannot reverse**: judge before changing state; pop before editing LOOP_STATE; the attribution goes in the verdict, not in the conversation.

## Where the line numbers come from (`by: L<n>` is not written from memory)

**The command block below is how a line number is produced rather than remembered**: probe, export, then grep the export — a number with no export path is a guess.

```bash
# 1) take one verbatim sentence from the executor's reply as the needle
printf '%s\n' "<copy a whole sentence from its reply>" > /tmp/needle.txt
agent-ide context --probe /tmp/needle.txt          # → key  hits  msgs  bytes
# 2) export that session; its line numbers are the file's line numbers
agent-ide context --key <key> > /tmp/exec.md
grep -n "<that sentence>" /tmp/exec.md             # → the line number
```

**The verdict writes `by: /tmp/exec.md:L<n>`** (with the export path, so anyone can replay it). **No export means no line number — then write `unjudged`, never estimate.**
