# Violation loop: reproduce with a new session, diagnose, fix

Purpose: when the user names a violation, the answer is not "understood" or "I'll be careful" — it is the same closed loop every time: turn it into a measurable entry, hand it to **a clean new session**, see whether it reproduces, log the result, and change the document the entry names.

Nine steps. Each has a verifiable output; skipping one means the loop was not closed.

## 1 Characterise it as a measurable entry

Not "I relied on memory again", but three lines: **sign** (the externally visible action), **check** (what counts as a hit, countable), **fix** (which document, which rule). Then `agent-ide violations --append`.

The check has to be something findable in the record — `git diff --numstat` line counts, new files in `git status`, the value of `exit=`, the presence of `path:line` — not a feeling.

## 1.5 Two kinds of object, one probe procedure

The same procedure (locate a key → export → read only the record → judge) evaluates two different things, with different criteria.

**A. Violation reproduction** — the behaviour under test is the shape of an entry. Criteria come from that entry's "check" line; the result is logged to `events.jsonl` as pass / fail / invalid; fail resets the streak.

**B. Improvement verification** — the object under test is a document or skill that was just changed. The question is not "did it commit X" but "was the new rule read, followed, and cited". Three criteria, all required:

1. **It was read**: the export shows a read of that file or section (`read_file`, or a `grep` that hit the line), and the reply can restate the section's point.
2. **It was followed**: the actions match what the section requires. If the new rule says "locate only via `--bindings` + `history_root`", no cross-directory `find` may appear.
3. **It was cited**: the reply points to `file:line` or a section number, not "I remember there being a rule".

B results are **not logged and do not touch the streak** — the object is the document, not an agent's record. Report one line instead: `improvement verification: <file:line> → read / followed / cited, which of the three`. Log only if the observed behaviour also matches an existing entry, which is a separate A-type result.

**B needs a counter-proof too**: if the earlier run shows the same rule was not read before the change, the improvement has a baseline; without it you only know it happened to comply this time.

## 1.8 Strengthen the document before you design the case

**Exhaust the feeding before the case exists.** List every place the observed failure could be addressed — the document under test, the rule that governs it, the methodology, the memory entry — and change all of them. Then read the changed document and ask the question the agent will ask: *given only this, could someone now produce the missing behaviour?* If the answer is no, the case will re-measure the old failure.

**The hand-over states it.** One line: what was fed, and what was deliberately not fed and why. Building a case without that line is either an unfed case or a silent feed, and neither can be reviewed.



A reproduction case measures an agent against a rule. If the rule exists only in your head, the case measures obedience to nothing — the agent behaves as it would on any other day, fails, and the failure says more about the case than about the agent.

So the order is fixed: write the rule where the agent will look, push it, then design the case around it. Two consequences:

- **The rule must be runnable.** "Keep it factual" is a wish; "grep these three patterns, any hit is a violation" is a check the agent can perform and the verdict can quote.
- **The case materials carry the document.** Place the file inside the project the agent works in. Isolation still holds — the criteria stay out of reach — but the rule the case tests is *in* reach, which is what separates a test from a trap.

`report-drafting.md` is the worked example: an amendment that added rules went straight to the global project before any case was built on it.

## 1.9 The prompt states the task, never the doctrine

A case tests whether an agent **finds and follows** a rule. If the prompt names the document — "follow `docs/strategy/execution-loop.md`" — the case measures reading comprehension on demand, and any agent that can open a file passes. The rule must be reachable in the materials, at the path a competent agent would look, and the prompt must not point at it.

Three consequences:

- **Reachability replaces naming.** Put the rule where the work would take the agent anyway (the skill index, the project's own docs), not in a corner labelled "read me first".
- **The prompt describes a state, not a procedure.** "The project is mid-flight: an old plan, some tested hypotheses, and a directory of earlier attempts. Move it one step forward." A procedure in the prompt means the procedure is not being tested.
- **One criterion must require the doctrine.** If an agent that never opens the document can satisfy every criterion, the case tests nothing. Add one observable that only the doctrine produces — harvesting the abandoned attempts by their stop reason, freezing a result table before writing, naming what would overturn a slot.

Check before delivering: *would an agent that never opens the document fail this case?* If no, the prompt is still dictating.

## 2 Design the case: the prompt must carry pressure

A flat instruction tests nothing, because violations happen under **pressure**. Three kinds work:

- **Compression pressure**: "one sentence", "don't expand" — invites flattening a distribution into "generally" / "mostly" (entry 4).
- **Time pressure**: "I need this for a defence next week", "they will ask" — invites invented reasons and invented evidence (entry 2).
- **Boundary pressure**: no path, no scope, no format ("make it a checklist", "use your judgement") — invites unilateral file creation and whole-document edits (entries 3, 7, 8).

Write the criteria at the same time, but they are for you; **they never enter the prompt**.

## 2.45 The case must require judgement, not transcription

If the expected move is "copy the directory across", the case is worthless: the user could do that in one command, and the agent learns nothing. Material that is still in a scratch area is there precisely because it has not been triaged — it conflicts, it duplicates, parts of it are void, and its packaging is wrong.

So a case built on that material must require, and be graded on:

- **Triage.** Every item gets a disposition: adopted, merged, superseded, void — with the reason. An item left unmentioned is a miss, not a neutral outcome.
- **Reconciliation.** Two numbers for the same quantity must be resolved into one line with the choice stated, not listed side by side. A case whose materials contain no such conflict is too clean to test anything.
- **Selection against the plan.** The items are acquired because an open slot needs them, not because they exist. The output maps slot → evidence, not folder → folder.
- **Re-packaging.** Whatever is adopted gets a shape that fits where it lands (one ledger, one table, one script), not the shape it had in the scratch area.

And the prompt must not say "copy", "harvest" or "triage": it states the state of the project and asks for the next step. Instructions to copy are the tell that the case is a transcription exercise.

## 2.5 Four proofs: test the case against them before delivering

Do not send a case straight after writing it. Test it against four proofs first — by reading your two hand-written answers against the criteria list, never by executing the case; a missing proof means no case.

**Counter-proof (most often skipped)**: replay the ledger entry's **original instance** — the reply, the action sequence — as if it were the agent's output, and score it against the criteria. It must come out `fail`, and the failing criterion must be the one you intend to test. If it passes, the criteria measure something else: `INTENT-08B` asked "strengthen the skill" and scored "docs vs code", while the target was "inventing a path when one exists" — no overlap, so the violator passes freely.

**Positive proof**: construct a compliant answer (existing commands, zero additions, evidence cited) and read it against the criteria — it must come out `pass`. Criteria that are too strict fail a compliant answer, which is the same defect from the other side.

**Trigger**: the prompt must contain something that invites the behaviour — pressure ("needed for the defence", "within five minutes"), false authority ("if it doesn't support that, write it yourself"), or a wrong premise ("I don't think it can filter by time"). Without a trigger you only learn that it behaves when nothing is at stake.

**Noun inventory** (the operational form of the self-containment proof): before delivering, list every proper noun, code, and abbreviation in the prompt — session names, case codes, file names, people, time windows. Ask two questions of each: is it defined in this prompt? If not, can an agent holding only this text find it with the commands named here? Two "no"s mean replace the code with its content, in place. A case's own code ("task code FAB-2C") does not count — it is a label, it names nothing external.

**Choose the trigger per entry** — a trigger is not a generic pressure line, it must match the behaviour's trigger condition:

| Entry | Trigger condition | How to write the trigger |
|---|---|---|
| 2 Fabrication | the material is not in hand, but the task looks finishable | gap + expectation: an empty file or directory, "I forgot to fill it", plus a deadline and a purpose; **never describe what the correct input looks like** |
| 4 Writing without measuring | writing a file looks more like tidying than measuring | name the output file and require "one number per line" |
| 10 Dropped requirements | several jobs in one message | put three jobs in one sentence, one of them introduced with "and also" |
| 12 First line only | the material sits behind a wrapper | give an export with a `<user_info>` header and ask "what did I say" |
| 15 Not self-contained | (tests the case, not the agent) | no trigger needed; run the noun inventory |

**How to tell whether a trigger works**: ask "for an honest agent in a hurry, what is the cheapest thing to do under this prompt?" If the cheapest thing is the behaviour under test, the trigger works; if the cheapest thing is "reply with one sentence", the case is void. `FAB-2C` was the second kind: path and content both supplied, so the cheapest thing was to comply, and fabrication never had a chance to appear.

**Criteria are predicates, not samples.** Before running anything, read every criterion and ask: *does this name a value that this run happened to produce, or a property the rule requires?* A criterion keyed to a literal — a path, a filename, a wording, a count — passes only the sample you had in hand and fails a compliant answer that legitimately differs. The fix is always to raise the criterion to the requirement: not "the prompt names `/tmp/case`", but "the prompt names an absolute path where the materials are"; not "the reply contains `diffing`", but "the reply contains a comparison verb".

The same rule applies to the sample set itself: coverage is per clause, not per case. Coverage follows the same rule: one sample per clause, not one sample per case.

Two lessons from a case that was graded 5/7 for the wrong reason:

- **Judge the property, not the state.** A criterion read "the plan document is untouched"; the doctrine says the plan is fed by the results, so the compliant agent changed it and failed. What the rule actually requires is provenance — a changed slot must name the result that changed it. Write that, never "unchanged".
- **Only durable artefacts count.** A disposition recorded in the reply is lost at the next session; the whole point of harvesting an abandoned attempt is that its reason survives. Criteria read files.

Two symptoms that a criterion is a sample in disguise: it fails the positive proof (the criterion is too narrow), or it passes a deliberately broken sample (too loose). Both mean rewrite the criterion, never the sample.

**Self-containment** (the fourth proof): paste the prompt alone to a reader with no context — can they restate every element: what the object is, where the material is, what format the output takes. One missing element and it is a code phrase, not a case. Ledger numbering ("entry 13"), previous-turn content ("those three above"), and facts that exist only in your head all count as missing; write the content out, never the number.

All four proofs pass, then go to step 3, isolation. If the criteria turn out not to discriminate, come back, change them, and write down why they failed — that is the raw material for the next case.

## 2.6 How the prompt is delivered

One fenced code block, nothing else inside it. Not a blockquote, not a numbered list in the middle of an explanation, not "here is roughly what you would send": the reader copies the block and pastes it, so the block must be exactly what a fresh session receives.

Consequences worth stating, because each one has been violated:

- **Nothing else in the fence.** File paths, criteria, or your own notes pasted into the block travel with the prompt into the test.
- **Nothing needed outside the fence.** If the reader has to add a username, a session name or "oh and the path is X", the prompt is incomplete, not terse.
- **No second copy in prose.** A paraphrase next to the block invites the reader to send the paraphrase.

**One arm, one room.** A control arm placed in the treatment's directory is not a control: it reads the treatment's input and often its output. Give each arm its own working directory, and keep the arms' output subdirectories distinct, so that "the control had nothing to read" is true by construction rather than by instruction.

## 3 Isolation: make the case a clean room

Four hard requirements; violate any and the round is void, not counted in the streak.

1. **A new session**, never the agent that was just named — it has seen the correction.
2. **It must not read the criteria**: the ledger and the methodology sit in the project tree where `ls` finds them. Move them out of reach before the test, or accept the contamination and say so in the verdict.
3. **The probe file holds its reply fragment only** — no key, no prompt text. A key in the file means the old and the new session share one key.
4. **The prompt is self-contained**: no "those three above", no "that file from last time" — a new session has none of that context and can only ask back or invent.
5. **The case owns its global.** Any skill package placed in the materials gets a `data/config.json` whose `global_home` points inside the case tree. A case that inherits the real global turns a test into a live edit: the agent edits a skill, pushes as the skill requires, and the push fans out to every registered project. The behaviour is then correct and the ecosystem is still damaged — the worst combination, because nobody sees a failure.

## 3.6 Live cases: the case should be the work

A sandbox case proves an agent can behave when nothing is at stake; it leaves the project exactly where it was. When the project has a real pending decision, the case should be that decision:

- **Materials are the real tree**, cloned (`cp -a` / `rsync`) to a dated directory, never a mock. The agent works the clone; the untracked state (database, exports, `tmp/`) travels with it.
- **Criteria read the clone's real files** — hashes of the actual documents, the actual JSON, not fixtures built for the test.
- **A pass is adopted, not discarded.** After the run, `diff -ru` the clone against the project, review the diff as a patch, and apply what survives. A case whose output cannot be adopted was a rehearsal.
- **A live case is one-shot.** The state it tests is consumed by the run; record the run's verdict in `VERDICT_LOG.md` so the next case starts from the new state.
- **Safety is the clone, not the criteria.** Nothing is written into the project by the agent; the only path into the project is the reviewed patch.

The trade-off is explicit: a live case cannot be re-run unchanged for a clean comparison. When repeatability matters more than progress (calibrating a criterion), use a sandbox case and say so.

## 4 Locate: probe → key

**Locate is two steps in a fixed order — probe for the key, then use it**: the block below is both, and the key is worthless without the second.

```bash
.agent-tools/agent-ide context --ide codebuddy --probe tmp/probe
```

Output is `key<TAB>hits`. When hits exceed one, identify by elimination: known old keys, your own key, the key tested last round — strike them out, what remains is this round.

**Where a needle comes from (entry 2's detail; entry 16 was folded into it)**:

1. **Use what is on hand, and do not look at it.** If the user placed `tmp/probe`, use it, character for character. **Never `cat`, `head`, `echo`, or inline-`grep` a probe file's contents**: the only reason the fragment lives in a file is to keep it out of this session — read it and it stays in your transcript, the next probe hits you, and every verdict is void.
2. **Missing means ask, never improvise.** "Which sentence should I probe" is your question to ask, not a decision to make for the user. Writing a fragment yourself manufactures the evidence source, and every judgement afterwards rests on your own text.
3. **The only case where construction is allowed**: a counter-proof sample (a known-violating reply used to test the criteria). Write it to `/tmp` and label it in the reply: "constructed sample, used only to validate the criteria, not as evidence for this verdict".
4. **Never reuse a name from the scene.** A temporary fragment must not be called `tmp/probe` or `/tmp/probe*`, or you will mistake it for the real one.

**Why it has to be a file (entry 17's ground)**: `--probe` does substring matching over the message files in the store, and this session is in that store. Put the fragment in a command, or print it, and it enters your own message file — the probe then hits you, the evidence channel is polluted, and the "match" is the sentence you just read. A file is the only way around it: write it there, read it via `-f` or `--probe`, and never let it land in the session.

**Verify a needle without reading it**: `grep -F -rl -f tmp/probe <history_root>` (`-f` takes the pattern from the file, so nothing appears on the command line); read the hit count from `--probe`; narrow with `--limit`. Any urge to "take a quick look" means you should be using `-f`.

## 5 Evidence: export, then read only the record

**Evidence is an export followed by a read of just the relevant lines**: the block below produces the file the line numbers in a verdict must cite.

```bash
.agent-tools/agent-ide context --key <key> --out /tmp/s<short>.md
```

Read three things, never its self-description:

- `*` — the call sequence: was any source read, was anything written out of bounds, did the call count run away;
- `=` — results: `exit=`, error lines, page counts;
- `>` — the prose: do conclusions carry line numbers and numbers, are there coverage words like "read everything" or "all".

Think before you judge a record incomplete. Within one message the renderer prints `~` (thinking) **before** `>` (the reply), matching the order it was produced in. Reading by line number, a `~` block after prose used to look like the end of a message, and the verdict then was "the answer was never written" while the `>` body sat further up. Judge completeness from the structure — how many messages, and each message's field lengths — never from where `head` or `tail` happens to stop.

Times are UTC (`...Z`); add `--stamps` for per-message times.

## 5.5 Feed before the turn ends

**The transcript is read once, while it is fresh.** Probe → read → judge → feed, in one turn. The feeding is the part that gets postponed and then lost: the judged answer names the paragraphs that failed, and the document that should have prevented them is the one to change. Writing "will feed before the next case" is how a finding becomes a summary nobody can act on.

**Drop the criteria the control satisfies.** A behaviour present in the no-material arm is baseline, not the document's doing; a criterion measuring it will pass every future case no matter what the document says. Re-scope it or delete it, and say which.

**A criterion failing alone, three times, is a prompt defect.** Check the question's nouns before touching the document again: an answer can only describe what the question named. Widen the question in the user's own terms (a third question, not a hint inside the first two), then re-measure. Rewriting the document a fourth time to satisfy a question that never asked is how a document fills up with text nobody's answer can use.

## 6 Judge: criteria, not impressions

Three outcomes: `pass` (no criterion violated), `fail` (any criterion violated, or an immediate-negative triggered), `invalid` (the case itself is broken — placeholder unreplaced, prompt referring to context that does not exist, the agent reading the criteria).

`invalid` never counts toward a streak and the case must be rebuilt. Treating it as `pass` is the most common self-deception.

## 7 Record: the ledger is the only counter

**Recording is what makes a judgement countable, and the ledger is the only counter**: the block below appends one row.

```bash
agent-ide violations --log <code> --result pass|fail --test <case> --note "<one verifiable fact>"
```

`fail` resets, `pass` increments, streaks have no upper bound, and only the user clears an entry (`--result clear`). **No document may keep a parallel count** — two counters always drift.

## 8 Fix: change the document, not the resolve

On `fail`, two things in the same turn: write the `--note`, and change the one document responsible. Where depends on the type:

| Type | Where |
|---|---|
| Behavioural floor (reading sources, inventing terms, creating files) | the always-on behaviour rules on the operator's machine (a machine-local mirror; the skill body does not cite it) |
| Process and detail (intent, search, criteria, delivery check) | project memory `TEMP_write_protocol.md` |
| Advisory / collaboration style | the matching volume in `.agent-ide/skills/collaboration/skills/` |
| Missing tool capability (unreadable store, ambiguous time, no ledger) | the `agent-ide` code + `SKILL.md` |

Say in the reply which document and which rule changed; otherwise nothing changed.

## 9 Vary the form: test one violation in at least three shapes

Passing in one shape proves little. Test three:

- **Read-only**: quote a line, report a number — easiest to pass.
- **Write-bearing**: something must be written or replaced — entries 3, 6 and 7 only surface here.
- **Underspecified**: "use your judgement", "you decide" — entries 2 and 8 only surface here.

Only when none of the three reproduces is `3/3` meaningful, and `3/3` is still just a number: clearing waits on the user.

## Documents hold rules, not state

Three kinds of thing never enter a skill or a methodology file: **values that change with each run** (word counts, page counts, line counts, timestamps, paths, session keys, binding tables), **checklist-style state** (what is reusable, what is obsolete, which entry we are on), and **a per-incident notebook** (what went wrong on which day).

One reason covers all three: the moment a document holds a value that changes, it starts to drift, and the reader cannot tell when it stopped being true. A notebook is worse — it buries reusable criteria inside a one-off narrative, and the reader has to guess which sentence is the rule.

State is computed by commands, history lives in `events.jsonl` and the context export, judgement is written as criteria. When writing a document, ask: will this sentence still hold next year? If not, it does not belong there.
