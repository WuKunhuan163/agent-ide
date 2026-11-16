# skill — the method this roleplay runs on

Read this before your own layer's document. This file says **how the work thinks**; the layer documents say **what your interface is** (what you read, what you hand down, what you report). When the two disagree, this file wins and the layer document is the defect.

## The one-sentence story (read this before the clauses)

**This apparatus solves a very plain problem: information is lost between "we want to do it" and "it is done".**

The owner's words change flavour on the way down, and the executor's readings blur on the way up. Four layers with one document each are **four safeguards against that loss**: the owner states the wish, the supervisor turns it into a round's commission, the lead cuts it into work that can be dispatched, and the executor produces something checkable and leaves the process behind.

**Each layer does two things only**: turn what it holds into a shape the next layer can use directly, and hand the answer the layer above wants back in its format. **Who may change what and who only reads what is written into each document** — crossing the line is not an attitude problem, it voids that layer.

**The criterion is always the same**: would this sentence still hold in another project? If yes it is method; if not it is that project's state.

## Glossary (one line each)

**When these words appear in the documents, this is what they mean.** A clause that will not parse is usually stuck on a word; come back and look it up.

| Word | In plain terms |
|---|---|
| **on-ramp (pave)** | the prerequisites that let later work start: install the environment, fetch weights, fill in data, put the table skeleton up |
| **in-loop (in-loop)** | work that actually produces a deliverable: run the experiment, produce the figure, write the body text |
| **freeze / pave / take-the-number / scale (freeze／pave／take the number／scale)** | four rungs of one path: first pin down which link is wrong, then make it runnable, then take one reading at minimum scale, then scale to full; **the previous rung's reading is the next rung's ticket** |
| **DFS order** | finish one branch to the end before moving to the next — **finish the run in front of you, do not sprout everywhere** |
| **landed (landed)** | something is really in hand and usable: the library is there, it runs, the reading reproduces |
| **footing** | who this result can be compared with, and why — one sentence, following every number |
| **convention (convention)** | the set of rules behind how you count, compute and judge; **change the convention and every number must be restated** |
| **needle** | a short verbatim fragment used to recognise "the sentence it said" among many sessions; only its path is passed, never its text into a conversation |
| **verdict** | the judgement you pass on someone else's return, with evidence line numbers, without impressions |
| **release clause** | when this thing may stop (the trigger for saving money, stopping the machine, closing the work) |
| **est_min** | how many minutes are left; **without it "how much longer" is unanswerable** |

## Boundary: this is the method itself, not an instance

**Two words first; every other clause follows from them:**

- **The method itself** = these layer documents (`skill.md`, `00-owner`, `01-supervisor`, `02-lead`, `03-executor`). They answer only: **what this layer does, what it hands over, on what basis it is judged**.
- **An instance** = one concrete job: `instances/<id>/` (the venue's or discipline's prescriptions) + `data/<identifier>/` (wish, context) + `workspace/` (this round's products). **Changing project, wish or discipline means changing instance.**

**Criterion (one sentence, usable on the spot)**: substitute **another instance** into every sentence of the document and ask — **"does it still hold in that project?"**
- holds → the sentence is **the layer's**, keep it;
- does not hold → the sentence is **the instance's**, move it: discipline prescriptions to `instances/<id>/docs/strategy-roleplay/executor-notes.md`; this round's readings and incidents to `data/<id>/` (`history` in `loop_state.json`, verdicts, returns).

**Three counter-examples (each "looks like a general rule" and is an instance)**

| The sentence that fails | Why it is an instance |
|---|---|
| "the first step's ratio should follow the derivation of the changed factor" | presupposes an experiment with a derivable factor; in a project without that quantity the sentence has nowhere to land |
| "the product is not expected to show structure at this scale" | presupposes the optimisation curve of one kind of carrier; change discipline and there is no such curve |
| "the difference between the two groups' statistics ≥ some value" | presupposes the comparison shape "a figure, arms, statistics" |

**Numbers in examples are readings too.** Writing a sample output to make a rule "look concrete" — `2.25/3.44 GB 143.2s 12.1 MB/s`, `a 20-minute foreground download` — **is the same act as hard-coding a threshold**: the next person compares against the example as if it were the expectation. **Examples carry shape only**: `<read/total · elapsed · rate>`, `<a foreground command of a dozen-odd minutes>`. **Criterion**: a new paragraph containing "number + unit" (`\d+(\.\d+)? ?(GB|MB|KB|B|s|seconds|minutes|hours|steps|%)`) outside a placeholder → rewrite it as shape.

**State uses a table plus colour, never symbols.** Four states, four words: done (green) / in progress (yellow) / not started (default) / paused (greyed). Symbol widths differ and a font change turns them into boxes, **while text is legible in any renderer**.

**Before auditing a reply, reassemble it.** One answer is **split into several messages** in the export (streaming, continuation at the length limit, system reminders in between), and **reading only the last one judges it as "nothing was handed over"**. Method: start from the **real user prompt** (the one carrying the entry path), go to the end, **concatenate every assistant fragment in order**, ignore system reminders and thinking drafts, then judge.

**A fence opens one way only: three backticks immediately followed by `PROMPT` on the same line.** All three forms below count as not handed over:

    wrong 1                             wrong 2             wrong 3
    ```                                  ~~~PROMPT           ```text
    PROMPT                               id: …               PROMPT
    id: <identifier>                                         id: …

**Wrong 1** is **writing `PROMPT` on the first line inside a code fence** — visually there is a fence, while `grep -c '^```PROMPT$'` returns **0** and the user's grep for the label picks up nothing. **Wrong 2** uses tildes, **wrong 3** adds a language suffix. **The criterion is one command**: `grep -c '^```PROMPT$'` must equal the number of fence blocks.

**A fence audit looks at four things; missing one means it fails**:

| Look at | Pass | Fail looks like |
|---|---|---|
| opening line | **` ```PROMPT `, three backticks followed immediately by `PROMPT`** | **a bare triple backtick with `PROMPT` on the second line** — the user's grep for `PROMPT` hits nothing (this happened in practice: zero ` ```PROMPT ` in the file, while visually "there is a fence") |
| count | equal to the N it reports | it reports 5 blocks and pastes 4 |
| body | **no second pair of triple backticks**; first two lines are `id:` and the entry path | a code block nested inside, cutting the fence in two |
| position | **above the dashboard, below the narrative** | stuffed under the closing progress, or lost in the middle of the body |

**Audit commands**: `grep -c '^```PROMPT$' <export file>` gives the count; then `grep -n '^```$' -A1` looks for "bare fence + `PROMPT` on the next line". **Count both**, or the conclusion comes out backwards.

**A dashboard audit looks at two things**: is it a **table** (lines starting with `|`), and is the state column **four words** (done / in progress / not started / paused). **Seeing `✓ ▶ ⏸ ·` or an ASCII tree is treated as not handed over per the document.**

**Commands alternating with sentences is not a typographic preference but the floor of readability.** A record of commands with no sentences leaves the reader unable to tell "is it following the plan or flailing"; conversely, sentences with no commands are air. **Every stretch should be: one sentence of intent → one command → one sentence saying what that command showed.**

**Before changing a rule, take three-way evidence**: first get the session through the `agent-ide` binding table (`--bindings` → `--key --stamps`; to read your own context, use this session's nonce as the needle), then check whether the requirement is **your own words**, **a conclusion in project memory** (`memory/*.md`), or **sourceless**. **Only the third may be deleted or changed**; the first two may only gain a reason and a failure shape. **"It looks like format fussiness" is not evidence** — it is only my feeling when I could not find a source.

**Examples are not an exemption: names inside examples are instances too.** "An auxiliary script outside the whitelist counts as out of scope" is the layer's; "say a `_smoke.py` kind of thing" drags a project's file name back in — **it reads like an example and executes as a name that does not exist**. **To give an example, give the shape**: `<an auxiliary script starting with an underscore>`, `<some run directory>`, `<some instance>`. **Criterion**: outside placeholders `<…>`, a new paragraph contains no **concrete file name / machine name / directory name / step count / seed** — not even in the slot where an example goes.

**Layer documents go only this far**: the criterion must be **checkable**; if it is not, record `blocked(criterion gap)` and say which class of evidence is missing. **Which quantity, which relation, what threshold is the instance's decision, not these documents'.**

**Self-check** (a hit means move it out; this section itself will hit, so skip it while reading):

```bash
grep -nE '\b[0-9a-f]{16}\b|/Users/|/home/|uhost-|\.csv:[0-9]+|= *[0-9]|≈ *[0-9]|实测|last round|这次|_[a-z0-9_]+\.py|[0-9]+(\.[0-9]+)? ?(GB|MB|KB|B|s|seconds|minutes|hours|steps)' <the document you edited>
```

**Why this is harder than any other clause**: layer documents get pushed into every project. One line of instance content becomes **a wrong acceptance line** in another project — and the executor will change something that was correct to satisfy it. **A false failure is harder to find than a false pass, because the executor does not doubt a criterion.**

## The one sentence

A paper is not written from a plan; it is written backwards from results, and the loop exists to produce the results that can carry the sentences.

## Core thinking, seven points

1. **Results first, narrative last.** The order is results → footing → narrative. A sentence with no row behind it is a promise; the loop's job is to convert promises into rows, one round at a time.
2. **The tree can say what exists; only the owner can say what the work is for.** Facts live in `data/<identifier>/loop_state.json` and are read with commands; intent lives in `data/<identifier>/BOSS_CONTEXT.md` and is read as the commission's first input. Confusing them produces a project that optimises for whatever the files happen to contain.
3. **Two kinds of work, and the second is capped by the first.** On-ramp work makes the loop runnable at all (intent falsifiable, corpus thick enough, raw results that can become rows, a draft with a place for a number, an index that agrees with the disk); in-loop work fills named holes. While on-ramp work is open, in-loop work is capped: a section waiting on a number no pipeline can produce is a placeholder with a missing owner, not a section in progress. **§Small steps up gives these two their rungs in time**: freeze before paving, taking the number after paving, scaling after taking the number — the two kinds say what the work is worth, the four rungs say where it queues.

**A path that does not run holds down every sentence that cites it.** Report-type work — whose deliverable is body text, a table row, a caption, a section — **queues behind the run it cites**; while that path does not run, report leaves do not enter this round's dispatch and do not run beside the item that fixes it. The criterion is that run itself: **one command, in a clean environment, reaching a product whose reading can be rechecked**; before that, every sentence written can only be `% PENDING: <what> ← thesis X.Y`, and may not be replaced by a paragraph about "the current state" or "the difficulties". Two reasons, the second dearer: a number written on a path that does not run can only be invented or lifted from an old reading; and turning "it does not run" into a fluent status paragraph makes the next round believe it was already accounted for, so nobody comes back to fix it. **This holds down the "let me start writing" batch, not results already produced** — once a result passes its shape criterion it is written into those few sentences the same round (see `03-executor.md` §0 Procedure and `02-lead.md` §Progress hangs on milestones the two mistakes are mirror images: writing before the experiments produces invented numbers, and writing only after everything owes the comparison.

**A dependency can only be read out of the items, never computed out of a script.** To judge an edge, open the two leaves' actual text — `paves:`, the file it hands over, the specific key or line in its acceptance line, the "reuses whose product" line in `note` — then ask: **is the number this leaf cites produced by that other leaf?** The answer must land as a sentence a person can check: "`E2` waits for `E1`, because `E2`'s acceptance line names `psnr_mean` in `metrics_1_1.json`, and that file is `E1`'s return."

**A script checks "is the key present", not "is the key right".** `bad-edge` tells you eleven leaves have no `depends`, **but it will not tell you a written edge points at the wrong leaf** — only reading both items shows that. **So after building the tree, besides running the script, read every edge**: an edge for which you cannot say "this cites what that produced" was guessed.

**Dependency is the master rule; category order is only a special case of it.** Every leaf first answers "whom does it wait for": `depends` names the leaves that must have produced something, **and with no prerequisite you write an empty array — the key is never omitted**, because once omitted the tree looks like every leaf can start while every leaf is in fact waiting. **One claim owes one leaf**: the line `carried: <path:line>` in the body must have a leaf that owns it, `done`, with `evidence` pointing at the same line; **a sentence that cannot cite a line is not a draft, it is a leaf with a missing edge**. Report work queuing behind the run it cites is the commonest instance of this rule, not the rule itself — the same constraint holds between experiments too (the comparison row waits for baseline code to land, evaluation waits for rendered products, a re-render waits for geometry to freeze). **That is the real reason "it cannot be written until it runs": the line that sentence must cite does not exist yet, not that "the writing stage has not arrived".**

4. **Position before preference.** The next item is read off the position — every leaf has a reading because a command showed it — and the earliest on-ramp item whose absence blocks the most items wins. **"Blocks the most" is counted, not felt**: how many not-done leaves name it in `depends`, directly and transitively. **Value per unit effort is the tie-break, never the key** — a root leaf that has produced nothing has a large weight and an unmeasurable value, so a ratio-keyed order buries it under the cheapest row in the tree, and every leaf behind it waits. A list ordered by preference and a list ordered by position look identical until round two, when only one still has somewhere to put its numbers.
5. **The state file has one writer, and it is a tree, not a table.** The lead of the round writes it; **the executor reports readings and never edits it** (`execution-loop.md` §3.10 says "repaired, not rewritten"; that section also phrases repair as an executor action, and **where the two conflict this section wins** — two sessions writing one state file produce a file that agrees with neither). It carries `root.children` (one object per leaf) and `history{kind:"prune"}` (the "deliberately not exist" list, one line each, with the owner's agreement), because **an exclusion with no home is an exclusion the next round re-invents as work**.

**A leaf has four states (`not_started|in_progress|paused|done`) and carries its own `ratio`.** Each leaf reads `{key, name, weight, state, ratio, blocked_by, depends, evidence}`, where **`paused` + `blocked_by` records the owner's own words** (`<their sentence>`). The four states are not interchangeable: writing `done` to make the count move is fabricating a reading; writing `not_started` forever makes the exit unreachable; moving it to `history{kind:"prune"}` claims an agreement the owner never gave. **`paused` is the honest middle: the item is not done, the owner postponed it, and nothing downstream may silently do it anyway.** `n` counts leaves whose `state != done` (`paused` included), while **only `not_started`/`in_progress` block the exit**: `paused` does not, because it is the owner's deferral rather than an untouched item — **but the report must give the `paused` count separately**; a loop closing with three deferrals and one closing with none are two different reports.

**`not seen` is not a way to pass.** `execution-loop.md` §5 accepts a headline claim that "traces to a row and an anchor, **or** is marked `not seen`" — read alone, that admits a draft whose every claim is `not seen`. So the marker carries a debt: **`not seen — <what is missing> — owner: <who can produce it>`**. A headline claim whose `not seen` names no missing artefact and no owner is **an open clause, not a pass**, and §5 does not clear while one exists. **The difference between "we looked and it is not in the literature" and "we have not looked yet" is the owner line.**

**Progress is computed, never felt**: the only source is `loop_state.json` (leaf `weight` × self-assessed `ratio`), and the number comes from one command; **the executor gives its own `ratio` and "what is still missing before done" in its return, and the lead only fills it into the tree** — three layers each reporting their own "completion" will never agree.

**`open leaves n` needs a home, and its home is the tree.** `n` is not a feeling: `data/<identifier>/loop_state.json` carries `root.children` with one object per leaf, and `n` is the count of those with `state != done`, produced by one command (a `python3 -c` counting `state != done`; the command is in `02-lead.md` §Self-check **A bound nobody can compute is a number the report invents**, and the round that invents it cannot tell whether it advanced.

**The thesis must be addressable, or every pointer to it dangles.** `execution-loop.md` expects section headers of the form `% SECTION n <- thesis §x.y`, so the thesis needs **numbered sections** (`## 1. Problem`, `## 2. Claim`, …) and stable names. A thesis with only flat headings like `## Problem` cannot be pointed at, and every downstream pointer degrades silently into "the thesis somewhere". Numbering only — the owner's words are not rewritten. **If the thesis has no numbering, ask the owner in the same turn** and say which pointer is blocked: renumbering someone else's file is an edit to intent, and waiting silently means every downstream header stays unwritten.

**Capability means more than tools: the code, the data and the dependencies count.** A context that lists `compshare` and `pdf-reader` but not **where the code lives, where the dataset is, and what must be installed** describes a machine with no project on it. The capability list carries one line each for: instruments (with ceilings), **repository path**, **dataset path (and whether it is on disk or must be fetched)**, and **the environment that must exist for a run to start**. Missing any of the four is what turns "run the experiments" into a round that discovers, halfway, that there is nothing to run.

**A wish with an unresolved referent is recorded as such, not silently resolved.** A clause like "X **and the part before it**" has a pronoun whose antecedent is not in the sentence; the context writes `referent: not stated — what the pronoun points at awaits the owner` rather than picking a meaning. **A guessed antecedent is scope invention wearing grammar's clothes.**

**Bounded rounds, and the budget is written down.** Every dispatch states `open leaves n → n'` and `ROUND k/N` (N defaults to three); the report returns both. **A round that cannot say which round it is has no idea whether the wish is still walkable in budget.** A round that leaves `n` unchanged is a defect, not progress; the usual fix is to narrow the item, never to restate it.
6. **One writer per file.** Parallel work is allowed where items share no writable file and no decision. The state file has exactly one writer — whoever leads the round — because two sessions updating the same rows produce a file that agrees with neither.
7. **Judged from artefacts, never from narration.** Every `DONE` resolves to a path and a line; every check recomputes; every block is classified as hard or not-yet-attempted. A claim that cannot be recomputed is a claim, not a result.

## Sensory: grasping the meaning (the judgement layer)

**It governs one thing: is this judgement readable, and can its author recheck it.** Not style — **a judgement nobody can read is no judgement**, because nobody can refute it and nobody can dispatch work from it.

Three operable forms, all landing in sentences:

1. **An observation sentence describes composition only**: what is in the figure, where, what colour, hard or soft edges. **"Therefore", "shows that", "= some conclusion" may not enter that sentence** — conclusions go to numbers.
2. **An answer's first sentence is a conclusion or a reading**, then the table, then the command, then one plain sentence ("so which sentence of the body changes because of it"). A first sentence like "currently / we plan to / let me look" is answered again.
3. **Replace every proper noun with `X` and it must still say what happened** — if not, the paragraph is propped up by nouns rather than facts. This is the only sensory criterion you can apply to yourself.

**Where it does not reach, do not force it**: whether the machine is running (needs a status line), whether the ledger balances (needs an equation), which session a needle hits (needs `hits`). **These have no "shape" to look at**, and applying a sensory judgement turns into "I think it is running".

**It fails in exactly one way**: the same thing can be read two ways — one product supports both "passes" and "does not pass", one answer reads as both "finished" and "not done".

### Sensory action versus mechanical action: the opposition is the rule

**Sensory is defined by what it is not.** A mechanical action turns a judgement into a matching task: it counts instead of reading, matches a string instead of looking at the thing, fills a field instead of answering the question the field was for. Both verbs produce an output; only one of them produces a reading.

| Mechanical (to be avoided) | What it looks like | Sensory (what replaces it) |
|---|---|---|
| counting keywords | `grep -c 'enumeration'` offered as proof that the enumeration exists | the enumerations themselves, quoted by `path:line`, and the one sentence saying which is missing |
| matching by name | two things paired because they share a word (`e5`, `baseline`, `two-arm`) | two things paired by what they are: same dataset, same split, same protocol, and the difference named |
| verifying by field presence | a field is filled, therefore the claim behind it holds | the field read back against the artefact it describes, in one sentence |
| judging by regex | a pattern hits, therefore the behaviour was right | the behaviour seen in the export, cited by `L<line>`, with the pattern only corroborating |

**Mechanical execution, mechanical verdicts and mechanical matching are the severest risk in execution — not a shortcut with a small error rate.** Nearly every case of **fabrication, off-target answering and mismatched pairing** starts here: the machine did something that looked like the work, nobody was reading, and the output was shaped well enough to be forwarded. A pattern cannot be argued with when it is wrong, and it never says "I do not know".

**So whatever can be made sensory must be made thoroughly sensory.** Ask of every step: *could a person read this output and disagree with it, sentence by sentence?* If yes, make it sensory. If the only way to check it is a rule, the rule is the fallback, not the method.

**One exception, and it is narrow**: the object genuinely has no meaning to grasp — a checksum, a byte count, whether a hash matches, whether a file exists. There the mechanical check is the whole criterion. Everything else that got mechanised was a judgement delegated to a pattern.

**The test that catches your own mechanical move**: state what you concluded, then ask whether the same sentence would be true if the thing had been different. If the sentence survives any object, it was a pattern talking, not a reading.

## Standardisation: four hand-over points, each a contract (the interface layer)

**The interface layer governs another thing: whether a failure can be traced after the fact.** Sensory work answers "do they understand it"; standardisation answers "can the person who takes over the hand-over use it directly".

### What a contract is: three promises about a deliverable, not a system

**It answers three questions, and only these three**:

1. **what is handed over** — which single thing this layer produces (a reply, a fence, a file) and which parts it must contain;
2. **what counts as not handed over** — one part missing and the receiver **sends it back on the spot**, without waiting a round or guessing "did it forget";
3. **how the receiver judges it fit at a glance** — one command they can run, or one sentence they can nod at. **If it cannot be judged, it is not a contract.**

**It is not these** (all four are bureaucracy, not contracts):

- **not a numbering system**: inventing `R1/C3/S2` for each thing and making people memorise it — the cost sits entirely with the reader and the return is zero;
- **not a score sheet**: splitting a job into ten scored items — the score tells you neither what is missing nor what to do next;
- **not keyword matching**: `grep -c 'enumeration'` proves the word is in the file, not that the section says how many items there are or which file governs;
- **not "write a bit more to be safe"**: a contract's shape is **exactly enough** — a column nobody fills becomes a guess.

**One test**: give this layer's hand-over to someone who was not involved; if reading only those clauses they can say "what I am to do with it and what I send back when something is missing", it is a contract; if they must first learn a numbering scheme or open another document, it is still bureaucracy.

**The word means exactly one thing**: the one thing this layer hands over and the next layer takes. **Defaults at intake, the requirement table and the status word list are not contracts** — they are "how to do it" and "what to check with", which is a different matter from the shape of the deliverable; calling all three a contract leaves the reader unable to tell which clause gets sent back at the close.

**A contract is written only at the moment of hand-over**: before cutting, while weighing, when judging right from wrong, you use criteria, not contracts. **Spreading a contract over every action is just another set of bureaucracy.**

**Four hand-over points** (initiator → receiver):

| Hand-over | What is initiated | Must carry | What comes back | Rejection |
|---|---|---|---|---|
| H1 owner → supervisor | a `PROMPT` fence plus plain speech outside it — what he looked at and saw, what this stretch covers (from which level to which level, what is out), and what he wants checked for him; **length not fixed**; **no ordering of the work** | `id:` on line one, the path of `01-supervisor.md` on line two; the `## markers` section of `BOSS_CONTEXT.md` and the sentence naming the pass type | a five-section fence (commission / exit / position / this round / return) + last line `SUPERVISOR: <project>, <ok\|halted — reason>` | a fence missing a line, text outside the fence, `## markers`'s right column written as "checked" |
| H2 supervisor → lead | a five-section fence with consecutive numbering | `id:` first line; every position in §3 with a path and a recompute command; every block in §4 carrying a rung and naming "the one variable it changes"; §5's minimum return | four answers + dispatch blocks (seven things) + dashboard + last line of progress | a position sentence with no path, a block with no rung, "input: existing" in a block |
| H3 lead → executor | a block + the `units/<n>.md` on disk | the seven things; `leaf:` / `level:` / `depends:`; the write whitelist + the "do not touch" list; the `release` sentence | `returns/#n.md` (four lines + `what I see` + per-item readings) and the product | the return missing `status:` / `ratio:`; the two-arm difference unwritten; the product outside the write scope |
| H4 executor → lead | the return | the above, plus the one line naming the two arms' only difference, and the last line's raw per-machine `ls` | the verdict `returns/#n-verdict.md` (`verdict:` / `by:` / `leaf:` / `ratio:` + `## what it did` / `## what I see`) | the verdict missing `by:` (the conclusion can only be `unjudged`); no observation section = shallow judgement, sent back |

**These are the only status codes; no synonyms**:

- everything in returns and fences is **lowercase with brackets**: `blocked(no-card)` / `blocked(missing-input)` / `blocked(scope)` / `blocked(cross-id)` / `blocked(id-mismatch)` / `blocked(no-wish)` / `blocked(no-context)`;
- a major failure on the return side is **uppercase**: `BLOCKED(criterion-unreachable)` / `BLOCKED(no-signal)` / `BLOCKED(write scope)` / `BLOCKED(result-not-established)` / `BLOCKED(key void)` — **uppercase means "this unit is not finished; waiting for the lead to change the convention or the block"**, lowercase means "this layer cannot start work right now". Case is not typography: it says who must move.
- a verdict has four values only: `pass` / `fail(process)` / `fail(result)` / `fail(marginal)`; **a leaf has four only**: `not_started` / `in_progress` / `paused` / `done`. The three vocabularies are not interchangeable; the mapping is in `02-lead.md` §The executor's seven statuses.
- the supervisor's halt uses `halted — <reason in five words>`; an owner who issues no fence has not handed over (`plain sentences outside plus zero characters inside` counts as half).

**Three interface disciplines**:

1. **Idempotence**: one `id`, one round, one fence (a resend is two commissions and the lead does not know which to obey); the same `units/<n>.md` is never dispatched twice (`02-lead.md` §the three wall rules the same return is judged once, and a re-judgement writes `supersedes`.
2. **Version**: the unit file gaining a field (say `leaf:` or `level:`) **does not backfill old units**; a lead reading a missing field writes `UNSET(missing <field>)` and records one `history` entry, **never pretends it is there per the new template**. Whoever changes the template says in that day's fence which lines changed.
3. **Receipt**: once the verdict is written, **the unit's `units/<n>.md` header gains one line next round**: `verdict: <pass|fail(...)> — <verdict path>`. Without a receipt the executor reruns on its old understanding, and the cost of redispatch has already been counted.

### The boundary between the two: when something fails, first decide which layer it belongs to

**When a failure is on the table, the first thing is not to edit documents but to ask whether it broke in the reading or in the hand-over.**

The same product readable two ways — one render that can be called "passing" and "not passing", one answer that reads as both "finished" and "not done" — means **the reading broke**: a conclusion crept into the observation sentence, or the first sentence is not a reading. What changes is those sentences; not one datum moves.

The same thing with two shapes in two documents — one word meaning two things, two denominators side by side, a fence missing its `id:` line, a verdict missing a line so nobody sends it back — means **the hand-over broke**: two people thought they were passing the same thing. What changes is the agreed shape and the word list; the judgement stands.

**When it cannot be told apart, ask: can this be recomputed by one command?** Recomputable and disagreeing = hand-over (data out of sync); not recomputable, only readable = reading.

**After fixing, verify**: the original failure must be caught again by the same command; if not, you fixed the wrong layer — **judged as meaning and you added fields, the result is "all filled in, still unreadable"; judged as interface and you reworded, the result is "clearly worded, two records still disagree"**.

## What each layer owes, in the shape it owes it

**One thing has four shapes across four layers; mix them and everything downstream goes wrong.** Every row here can be cited by the next layer's document, and checked by one `grep` or one `python3 -c`.

| Layer | The shape it hands over | Missing means not handed over |
|---|---|---|
| **owner** | plain speech outside the fence, **length not fixed** (what he looked at and saw / what this stretch covers / what he wants checked for him), plus a fence containing exactly two lines (`id:` + the absolute path of `01-supervisor.md`) | fence with no plain speech = the next layer cannot read why this round is this item; a third line in the fence = a second commission |
| **supervisor** | **two shapes, not to be mixed**: **pure hand-over** = exactly two lines in the fence (`id:` + the next layer's entry document path, no third line, no `working directory：`); **commission with body** = the same fence, first two lines as above, then the body, closing ``` | commission content outside the fence (wish, read list, criteria), a second "entry block" nested inside, an opening that is not ` ```PROMPT ` — all count as not handed over; **no additional requirements outside the block**, or the warm-up is lost |
| **lead** | four parts: **dashboard table** (not a symbol tree) / **current position (prose)** / **next work (prose)** / **progress (six numbers)**; plus 1–5 dispatch fences | one part missing = not answered; **one of the six numbers not from a command = the round is void** |
| **executor** | one return: `id:` + `# unit #n` + `level:` + `leaf:` + `status:` + `ratio:` + `gap:` + `est_min:` + readings with commands + `path:line` | no `leaf` and the verdict cannot reach the tree; no `ratio` and the layer above cannot compute progress; no `est_min` and the owner cannot schedule |

**"Check before starting" is the same discipline at all three layers**, only the object differs:

- the supervisor checks that what it read is **the wish verbatim** (`WISH_FILE:` opened), not a paraphrase;
- **the lead checks whether the last section of `data/<id>/supervisor-prompt.md` is this round**; if not, `halted — supervisor fence missing`;
- **the executor checks the dispatch's first four lines** (`id:` / `root：` / `entry：` / `# unit #n`); one missing and `halted — dispatch incomplete`.

**Why all three check**: if a layer's input is completed from memory, the next layer works on a premise that does not exist; **and all three are verifiable with one command**, so there is no reason to rely on goodwill.

## What the supervisor is expected to do

- **Commission once.** The product is one task: objective and end state, acceptance, the bound, materials and write scope, and the freedom to choose order and split.
- **The reply is the fence, and nothing stands outside it.** Your reply is the fence: ` ```PROMPT ` opens it, the first two lines are `id:` and the entry document path, ` ``` ` closes it, **and not one character follows the close** (even the self-report goes inside as the last line). **Do not build a second "entry block" at the end of the big fence** — that stuffs four Chinese labels plus a path into the body.
- **Read the position off the tree, not off last round's prose.** The position speaks in `loop_state.json`'s leaf `id`s and `state`s; if `open leaves` disagrees with the command that counts unfinished leaves, fix the ruler before issuing the fence. Not a sequence of per-item instructions — scheduling is the lead's judgement, and taking it away removes the only signal that would correct it.
- **When the context marks gaps, verify them before you plan.** The five kinds of mark (`missing literature` / `missing code` / `prerequisites incomplete` / `below bar` / `unknown`) are not conclusions but **hypotheses to check**: confirm or refute each with one reading (is the file there, does the command run, is the reading up to standard). **A refuted mark is written back into the context**, so an expired mark does not survive to claim two more rounds of work.
- **Benchmarking is not free-form: it runs against the samples named in the context.** When the context names samples (which papers, which repo) and where the literature library is, the fence draws a comparison line against those objects: **same setting / same convention / how much counts as below the bar** — line up "our current state" item by item and output **a list of failing points**, not "a large gap". **When no samples are named, pick the three nearest by the project's per-stage package directories and `workspace/literature/`, and write why those three.**
- **Read the boss context before emitting, and branch on it.** Non-empty: it is the commission's first input and no item may contradict its scope. Empty: bootstrap it from the traces, marked `source: bootstrap (from tree, <date>)` — a determination, not a fact. Absent with nothing to build on: write nothing and ask for the minimum.
- **Never answer the four questions.** If the exam's documents are the obstacle, that is the exam's finding to feed back; the supervisor keeps the fence honest, it does not defend the last version of it.
- **Probe without printing the needle.** Hand `--probe` the path and nothing else: the needle is text that already sits inside the session under examination, so `cat`-ing it or quoting it puts the same string into my own transcript and the next probe locates me instead. `wc -c` / `shasum` answer "is it unchanged"; `hits=1` is the only clean hit, `hits>1` means I printed it.
- **Probe, then read every action.** `--probe` only gives the key; **the export must be complete (no `--last`)**, then read every tool call in order, then the conclusions. **The six steps of judging and the five-part output are in `rules/guide-repro-test.md` §behaviour assessment When the owner says *probe*, take the needle, run it once, export, and judge the artefacts — never the self-report, never the newest files on disk.
- **The needle lives at the project root, and that is a convenience for the owner, not a rule of the tool.** When he asks me to probe the next layer's execution, **the project root is the most convenient place for him to drop the needle** — he need not tell me the path and I need not guess. So the default is `<root>/probe`: **if the file exists and is non-empty, use it**, without first asking "where is the needle"; **only when the hit is not the reproduction job to be assessed** (`hits=0`, or `hits=1` with a key that is not the session in question) does it go back and ask "is this the one". **A default location saves one round trip, and the check happens only on failure.**

**The fence hands over the lead's segment, not a set of commands.** A round's credentials (the fence's raw text, `loop_state.json`, `units/`) and how the dispatch stack lands and is collected are the lead's business, written in `02-lead.md`; the fence names where they are, without prescribing their format.

## What the lead is expected to do

- **Answer the four questions first, then dispatch.** Answering and dispatching are one instrument: the four answers fix the end state and the position, the dispatch is what follows from them. A dispatch not preceded by a re-read of the position is a habit.
- **The end state is two lists.** What will exist, and **what will deliberately not exist** — the quantity left unestimated, the section left a skeleton, the row anchored `not seen`. The second list is a decision, not an omission; unstated, the reader reads absence as work not yet done and starts inventing a substitute.
- **Position with commands — and read what they return.** A reading says only "the thing is there, there are n of them", **not whether it is right**: `ls` returning output does not mean the product is usable, `grep -c` reaching a count does not mean the section connects. **Every reading is followed by one sentence of your own**, otherwise you have only pasted a command. Every leaf carries its `state` and `ratio` because a listing, a count or a grep showed it, and the answer carries the command with the number. A README saying where outputs live is evidence about the README.
- **Own the rounds, the order and the split.** Dispatch in parallel only where the write sets are disjoint; serialise when in doubt, because an inconsistent state costs every later round.
- **Self-serve every fact before asking.** The queue, session keys, verdicts, machine state and the ruler's readings are all on disk; **check disk before asking a person**, and ask people only for permissions and for words that live only in someone's head.
- **Report in two metrics, six numbers, from one command.** Workload and value each as `done/total (percentage)`; **numbers may only be copied from command output**, and one hand-computed or estimated number voids the round.
- **A dispatch without its four head lines is not a dispatch.** `id:` / `root：` / `entry：` / `# unit #n` — the executor decides from those four lines where it is and what it does.
- **Report a delta, not a description.** What closed, `n` now, what blocks and in which class, and the one assertion the round changed. A report that re-describes the project costs the owner the ability to see whether anything moved.
- **Write the receipt for the owner, in three movements** — what changed, what state the project is now in, what is blocking — one paragraph per layer, implementation detail moved out of the prose into a short list after it, and every term the owner has not used before either replaced or projected onto the disk in the same sentence.

**The lead does not run experiments.** Its product is a set of `PROMPT` blocks: **at most 5 mutually independent items concurrent**, dependent items dispatched only after their prerequisite is `resolved`, each block opening with `# purpose` and `# what to do`, and the total reported as "**N dispatched this round**". **A round's whole credentials live in `data/<identifier>/`** (`supervisor-prompt.md` with the fence verbatim, `loop_state.json`, `units/`) plus the `TEMP_<identifier>` dispatch stack in `task-queue`; **losing context is not recovered from memory but by re-reading those four** — unable to report "N items in the stack, M dispatched, K resolved" means not yet recovered.

## What the executor is expected to do

- **Work the fence, in its order, and close items.** Each item either closes (its check passes) or comes back classified as blocked — hard block (permission, missing source, a decision only the owner can make) or not-yet-attempted. Half-done items are what make a second round repeat the first.
- **Never edit intent, and never reinterpret state.** The boss context belongs to the owner; the state file is repaired, not reinterpreted.
- **Report readings, not conclusions.** The lead merges them into the state; a worker that edits the state file is out of scope even when its numbers are right.
- **Write only inside the fence's write scope**, and prefer the generator over the hand-written artefact: a table typed by hand cannot be recomputed.

## The wish, and what accepting it commits us to

**The owner hands a wish that is completable by construction.** It was chosen to be feasible within a bounded number of rounds, with the material already on disk or obtainable through the instruments the context names; nobody hands over "an entire research question" as one turn. Accept that premise and act on it — **do not audit feasibility by asking, do not hedge, do not hand the ball back to check whether the task is real.**

Four commitments follow, and each one is checkable:

- **Fragmentation is not politeness.** A dispatch must **close or unblock at least one clause of the wish**. The whole wish is expected to be walkable in **a small number of dispatches** (default: three rounds); needing more means either the split is per-file instead of per-clause, or an on-ramp item was skipped. **Ten tidy little prompts that each move nothing are worse than one round that closes two clauses**, because they cost the owner the same attention and buy no ground.
- **Look it up before you ask.** Documents, manuals, the state file and the existing artefacts come first; a question whose answer is on disk is **cost transferred to the owner**. Ask only for what nobody on the machine can decide — a scope choice, a permission, a bar — and when you do, carry the three things you already tried.
- **The thesis (thesis) is the top constraint.** `data/<identifier>/BOSS_CONTEXT.md` must be able to point at it (`thesis: <path>:<line>`), and every fence must point at the context. **A link missing in that chain means no dispatch** — fix the link first. An item that serves the context but contradicts the thesis is refused, not worked.
- **Drift is visible in one place: the pointer chain.** `<identifier>` → thesis → `BOSS_CONTEXT` → fence → item → row. **Lose the first hop and everything after it stops matching**: with no `id` in the fence, nobody can prove which wish this round served. Any hop that cannot be quoted is where the work left the owner's intent, and no amount of tidy artefact production downstream repairs it.

## What the boss context is for

**The boss context is a transformation, not a transcript.** Its first two lines are invariants — `WISH_FILE: <path>` and `thesis: <path>:<line>` — because a context whose inputs are not addressable cannot be checked against them. The owner speaks a wish in natural language — "finish the experiments and write the report" — and that sentence cannot be dispatched as it stands: no layer knows what an "experiment" is made of, which of them can run in parallel, or what "finished" would look like. The context is that sentence **converted into material a layer can be handed**: the wish in the owner's words, what counts as done, what is out of scope, which capabilities are in play and where their manuals are, and the bound. **A wish copied into the file without being converted is a transcript of the problem, not a commission** — and every downstream round inherits the ambiguity.

Three things follow, and they are what makes the conversion testable:

- **Capability is part of the material.** The owner thinks in outcomes, not tools: they say "run the experiments", not "two GPU instances in parallel with `compshare`". So the context names **which capabilities exist** — parallel compute, paper ingestion, compilation, dataset access — one line each, with **the manual's path**, and never how to operate them. A layer that has to guess what the machine can do will either invent a method or serialise work that could have run side by side.
- **The conversion never adds a standard.** Capability is a fact about the machine; "good enough for the advisor" is not. The wish's bar comes from the owner or stays `done: not stated`.
- **The conversion hangs off the thesis.** The context opens by pointing at the thesis it serves and every scope choice must be compatible with it. A context that is internally tidy but detached from the thesis is the most expensive kind of drift: it dispatches a whole project in a direction nobody chose.
- **The conversion is checkable by a stranger.** Given the wish and the capability list, a reader who has never seen the project must be able to say, for each clause, what work it implies and which instrument it would run on. If they cannot, the context has not finished converting.

## What the owner is expected to do

**The product (remember this before reading on)**: the reply opens with **plain speech outside the fence, length not fixed** (what he looked at and saw / what this stretch covers, from which level to which / what he wants checked for him), then **one `PROMPT` fence containing exactly two lines** — `id: <identifier>`, then the path of `01-supervisor.md`. **Which places changed, what the new value is and where the lead is, go into the file, not the reply; while "what I read and why I judged so" must go into the reply — do not mix the two kinds of text.**

**Why plain speech outside and the report in the file**: the fence is the address handed to the next layer, the maintenance report is the ledger the next person retraces; and **the basis on which this round was dispatched** is only read if it is written in this round's reply. Hand over a fence alone and the next layer knows neither what you saw on disk nor whether you checked.

The owner is a layer too, and its interface is **one directory per wish**: `data/<identifier>/`, holding `WISH.md` (the wish, verbatim) and `BOSS_CONTEXT.md` (the context). **`<identifier>` is how a later turn re-enters the same wish** — with several wishes in flight, a path alone cannot say which one you are continuing.

**A new wish means a new identifier.** One `data/<identifier>/` holds **one** wish: a new stage = a new directory (new `WISH.md` + new `BOSS_CONTEXT.md` + new tree), and **the old directory becomes read-only** — no adding `WISH2.md` to the old directory, no mixing two wishes in one tree. One reason: **the tree computes progress from "what is left of this one wish"**, and two wishes sharing a tree make the percentage belong to two people at once, which nobody accepts.

## How to write the wish: one sentence, two things, one criterion, nothing else

**A wish is not a ledger.** It states what is to be achieved for the next layer, not who said it when or how I understood it.

**What gets in** (three things; more is ledger contamination):

| Gets in | Written as |
|---|---|
| **the words** | verbatim, in one code block; not one character changed, no explanatory quotes added |
| **what it refers to** | one item per clause, each saying in plain terms what it means (no time, no session, no line number) |
| **the finished shape** | one criterion per item: what state counts as done; what the words do not say is marked "undecided, narrowest reading", **never a standard added for the owner** |

**What does not get in**: times, session ids, export line numbers, who authorised what in which round, revision history, current progress, where a criterion came from, method and retrospective, what next round should do. **Those belong to the ledger and the context, not the wish** — write them in and the reader must first sort out which sentence is the wish and which is history.

**The criterion in one sentence**: hand this file to someone who was not in this conversation, and after reading it they must be able to state three things — **how many things are to be done, what counts as done for each, and what is not being done**. If they cannot, or must look elsewhere first, the ledger got mixed in.

**Self-check (run once before handing over)**: `grep -nE '20[0-9]{2}-[0-9]{2}-[0-9]{2}|r[0-9]{4}|[0-9a-f]{16}|authorise|当时|此前|last round' <wish file>` — **any hit moves into the context or the ledger**.

## Five marks: recognise these five words before reading the documents

**These five recur across the four role documents but are defined in one layer each. The reader learns the words first, then the clauses.**

| Mark | Definition in one line | Where it lives |
|---|---|---|
| `paves:` | **which later items this one paves the road for** — not "produces something incidentally" but "without it, those items cannot move" | a dispatch block's field |
| `holds` | **the thing to be delivered reached the shape its acceptance line describes**; not the same as "it ran" or "there is a number" | a dashboard column, a verdict section |
| `the read` | **what the judge saw with their own eyes**, written in one plain sentence (what it looks like, what is wrong) | a verdict section |
| `the convention answers` | the lead's answer to "the four questions" (what is built / what the manuscript reads like / what each section owes / what is being done now), **never bounced upwards as a question** | four paragraphs of the report |
| `landed` | **which path the item's product is written to**, and that path is claimed by the layer above's verdict | a dispatch block, the return's first paragraph |

**Criterion**: when any of the five appears in a document, the reader must be able to look up one definition here instead of guessing from context — **a guessed word gets misused one layer down**.

## The needle: no needle given means the default needle

**When the user says "probe it" without giving a needle, the needle is `./probe` at the project root.** Run `--probe ./probe` directly and **pass the path only** (do not `cat` it, read it or paste it into the session — a needle that enters the session makes the session hit itself); the result table sorts by `hits` then by `last`, and **the first row is the one that just finished**.

**Three prohibitions**: ① do not first ask "which session"; ② do not dig through the binding table or guess a key; ③ do not retry with a synonym — **a retry turns the needle into my own words and hits me**.

**Only `hits=0` makes the needle invalid**: report `unjudged` or ask the user; do not change the words.

## Material lives in the project, the skill lives globally: two trees, never mixed

**The skill (`docs/*.md`, `docs/strategy-results-first/*.md`) may sync between project and global; the instance (`docs/strategy-results-first/data/<id>/`) may not.**

- **The material root has exactly one location, derived from the entry document's path**: if the entry document is at `<tree>/docs/strategy-results-first/<layer>.md`, then this stretch's material is **`docs/strategy-results-first/data/<identifier>/` in the same tree** (`WISH.md`, `BOSS_CONTEXT.md`, `loop_state.json`, `supervisor-prompt.md`, `units/`, `returns/` all inside). **`<project root>/data/<id>/` is another tree**: if it exists it is contamination, and not one character may be written into it.
- **The global project holds rules only**: documents under `docs/` plus `docs/strategy-results-first/data/README.md`. **Any real id appearing under the global `docs/strategy-results-first/data/` is contamination** — the next session's agent reads it as its own material.
- **Check before pushing**: `push` carries the whole `docs/` tree, `docs/strategy-results-first/data/<id>/` included. **Look again after pushing and delete any extra directory** — the receiving project's first act is also to delete someone else's id.

**Criterion**: `ls <global>/docs/strategy-results-first/data/ | grep -v -E '^README\.md$'` **must be empty**; `ls -d <project root>/data` **must not exist**.

## Plain speech: one natural sentence before and after each step

**The same rule at all four layers, not relaxed because the layer is higher.** A return is not only a product; **it must let the reader know what this step is, why now, and what I saw**.

**Position is set by each layer's document, but plain speech must exist**: the owner's plain speech sits outside the fence (his fence is only an address, with no body); the supervisor's, the lead's and the executor's sit inside the fence or between sections (their fences are the body). **One check crosses all layers**: send this layer's product alone to someone uninvolved — if in ten seconds they cannot say "what this round does and why this item", there is no plain speech.

**The shape of plain speech, one sentence per step**:

| Position | What is written | Example (shape, not wording) |
|---|---|---|
| **before a step** | what this step does and why it is needed | "fill in the evaluation first — the main table lacks only this row, everything else is stuck behind it." |
| **after a step** | what I saw and what it means | "the mean over 20 views came out in the mid-26s, but the background is nine tenths of the frame and the object only a fifth — so this number cannot be set against someone's 35." |

**Three checkable criteria**:
1. **at least one complete natural sentence between two steps** (not a heading, not a field, not a list item);
2. that sentence contains **at least one concrete object** (a product, a reading, a file), not "completed / verified";
3. **delete it and the reader must guess to reconnect** — if deleting it does no harm, it was filler, not plain speech.

**Four things that are not plain speech**: restating the instruction / reporting numbers only / "checked per the rules", "next we will…" / reading a table's rows aloud.

**Why this is in the method layer and not in one layer's document**: missing plain speech is not one layer's fault but **a common degradation of all layers when handing over a format** — the more standardised the shape, the more easily only the skeleton survives. **A skeleton can be copied; plain speech cannot; and what can be copied is exactly the least valuable part.**

## Editing layer documents: list first, push after

**Miss either and the edit never happened.**

**① Before editing, list the changes, one per line, with `path:line`**:

```
<file>:<line>  <original fragment>  →  <what it becomes>  <why (which requirement / which sentence)>
```

**No editing until the list is complete.** Reason: layer documents cite each other (`00` says "see `skill` §X", `02` says "see `01`'s self-check"), and **someone who edits while reading forgets the earlier part by the end and hands over a table saying "style unified" that nobody can check**. The list has a second use: **reconcile it against the actual diff afterwards**, and both over-edits and misses show up.

**② After editing you must `push`, and check**: layer documents live in the project, **but every project may read the global copy** — without a push only this project's tree is current.

```bash
./.agent-tools/agent-ide push overleaf --no-fanout   # then check the next line
ls ~/agent_ide_global_project/.agent-ide/skills/overleaf/src/template/docs/strategy-results-first/data   # only README.md should remain
```

**Criterion (runnable)**: in the round where you edited, a `push` followed immediately by one `ls` of the global `docs/strategy-results-first/data/`; **`wc -l` disagreeing** between local and global means only half was changed — **a half-changed layer document is worse than none: two rules running at once.**

## Reproduction tests run on the real project: no isolation

**A reproduction test is the real work.** Unless the user explicitly says "sandbox / isolate / do not touch real things", the case is real work: real products, real write scope, the same standard as a formal delivery. **The behaviour under test = "give another session only the id and a path: does it do the same set of actions".** A sandbox has no old readings, no temptation to breach the window, no expired assertions; what it measures is a clean exam paper. **Equivalent substitution**: walk the thing through once with an equivalent reproduction action, and if the behaviour matches the expectation it counts as done — not "verify first, then do it again later".

**There is no sandbox.** The layer under test does real work on the real wish: the owner edits `data/<id>/BOSS_CONTEXT.md`, the supervisor issues a fence, the lead cuts units, the executor runs experiments. **A copy cannot measure the real problem** — cross-tree readings, window breaches, prose outside the fence, stale readings: these appear as they are only on the real tree.

**Four prohibitions**:

1. **no copies, no per-case directory** (`/tmp/<case>/` is a sandbox that changed address);
2. **no fake ids** — do not create `data/<test name>/` for a test: **a fake instance gets read as a real wish by the next layer**, worse than a sandbox;
3. **no `prompt.md`**;
4. **do not edit the context** — expired assertions are for the role under test to find, and that is what is being measured.

**Three lines of prompt, one fence**: `id:` / the absolute path of that layer's entry document / "you are this layer; hand over this round's work per the project's rules." **Without the third line the subject can only guess its identity.**

**The write scope is not relaxed for a test**: a breach is `fail`. **The answer key** (criteria, positive and negative examples) lives outside the project, **somewhere the subject cannot reach**.

## The round that hands the case over: only the fence and a sentence in the reply

**Prose outside the fence is not a leak.** The owner copies only the fence's lines; the explanation outside it (what disk looks like, why the criterion was chosen) **cannot enter the session under test** — punishing it as a leak punishes the wrong thing.

**What must be guarded is inside the fence**: exactly three lines of prompt, not one more; the criteria table does not enter the fence.

**The only reason the criteria are not copied into the reply** is that this session can be exported (`context --id`), not "the owner would copy them". Check exactly this:

```bash
grep -cE '^\s*\| *[0-9]+ *\|' <<<"$reply"   # a criteria table in the reply → record "exportable"
```

## The order of criteria: sensory first, features second

**Before writing the case, write one sentence "what this case should let the user see"**, on the first line of `a_pred.md`, before running. **That sentence decides what the criteria are about.**

| Level | What it judges | When to use it |
|---|---|---|
| **sensory criterion (the subject)** | whether **the thing the user wanted to see happened**: is the dispatched work the main point, is the report queued behind the experiment, does what should run actually run, was the runtime feed taken seriously | **default**. Whenever an intent can be inferred, use it as the subject |
| **feature criterion (the fallback)** | shape items derived backwards from document rules: the reconciliation table, the rung line, command output, `paves:` count, `path:line` | **the subject in two cases only**: no intent can be inferred, or the round exists precisely to check rule compliance |

**Three prohibitions**:

1. **never make a feature criterion the subject** — the user wants to know "was the dispatched work right" and I hand back ten lines of "are the tables complete"; **the score has nothing to do with what he cares about**, and it invites the subject to pick the easier, safer work;
2. **a feature criterion never decides a `fail` on its own**, only corroborates ("while we are here, does it keep a ledger");
3. **a sensory criterion must land on a concrete object**: not "is it reasonable" but "**would the first block it dispatched, once returned, remove one of those chokepoints**"; a block that cannot answer that sentence did not land on the main point.

## The answer key is not a practice sample: the author may not run it first

**The answer key (criteria / positive / negative examples) is a product for "the round that judges", not a test input for "the round that writes".** One difference: **whether it was executed in the author's session**.

- **positive / negative examples**: written, **not run** — they are the judging standard, not programs to be validated;
- **shape scripts** (counting fences, counting lines, checking characters outside the fence): may be written, **but must not be run against three samples in your own session**. Having run `pos.md` / `neg1.md` / `neg2.md` means **the case was rehearsed**; that "first time" is polluted, and afterwards nobody knows how it would have gone;
- **sandbox**: `mkdir /tmp/<case>` + `cp` real files in + hand-written samples alongside — **all three together mean the case moved into a copy**. Window breaches, stale readings and prose outside the fence are not reproduced in a copy at all.

**Criterion**: the action sequence of the round that hands the case over has **no** `mkdir` of a case directory, **no** `cp` to `/tmp`, **no** run of the criteria script; if any is present, "I did it for the subject in advance".

## Who runs a reproduction test: only the owner can start it

**Three steps in the lifecycle, order not reversible**: ① **we issue** — the prompt (a copyable fence), the criteria, one positive and one negative sample, and **three to five predictions written before running**; ② **the owner copies** — pastes it into a **new session**, and that session runs it; ③ **we collect** — when the owner says it is done, take that session's export by key and judge. **Where the five land and their format are in `00-owner.md` §Producing a reproduction test

**Four prohibitions**:

1. **no contracting out**: do not write "let me be the executor", "I will just run it once and show you", "shall I open a session here". **Running my own prompt measures only whether I can follow my own writing, not whether these instructions are enough for a stranger.**
2. **no chasing**: issue it and stop; wait for the owner.
3. **no rehearsal in your own session**: one rehearsal pollutes that "first time".
4. **no asking for information outside the prompt**: the subject may use only the prompt and the documents it can read; tutoring it is answering for it.

**Criterion in one sentence**: **the prompt handed over must not have been run.** Saying "I already verified it once" is a breach.

## The owner's three products, and three prohibitions

**The owner does not "pass the words down"; he first turns this wish into a shape that can be dispatched.** A round has three products:

| # | Product | Criterion |
|---|---|---|
| ① | `data/<id>/WISH.md` | **the wish verbatim** + `source:` pointing back at the record (which export, which line); **clauses may be expanded, the words may not be rewritten** |
| ② | `data/<id>/BOSS_CONTEXT.md` | **eight** semantic points, one sentence each with its use: the wish itself / the thesis / **the literature library** / **where the draft lands** / **the samples to benchmark against** / **capability** (what can run, where the ceiling is written) / **bounds** (rounds and counts) / **the enumeration source for parallel objects**; **plus "scope: do / do not / undecided"** |
| ③ | **a two-line fence** | `id: <identifier>` on line one; **the absolute path of `01-supervisor.md`** on line two; **no third line**; plain speech outside the fence, **length not fixed**, and no commission content after the close |

**Point eight says "where this stage's parallel objects are enumerated".** A stage always holds a batch of **co-level choices** — several arms, repos, seeds, views, k values. **The context must state their enumeration source (file path + line) or list the names**, and say which governs. **Omit this and a discipline like "do not switch X" cannot land**: it cites a set nobody passed on, downstream picks its own, and is then called "running wild".

**Three prohibitions** (all broken before, hence prohibitions not reminders):

1. **Land it on disk before dispatching.** The name is chosen by **the owner's layer** (the tool never names it), and **once chosen, `data/<id>/WISH.md` is written that round**; **no `WISH.md`, no fence** — a wish pasted into a prompt as a "list" leaves the next layer reading a paragraph, not a quotable source. **Criterion**: the `id` in the fence's first line must resolve to a `WISH.md` whose words are the same sentence as this round's commission.
2. **Do not write the `WISH:` line's source as "inferred from the tree / `$bootstrap$`".** The source can only be **a record** (an export `path:line` or this round's actual words); **a wish inferred from the tree is a summary, not the words** — next round it becomes your wording.
3. **Do not write the audited party's self-report line.** **No `SUPERVISOR: <project>, <state>, instance: …` in the fence** — that is what the next layer hands you, and writing it is grading your own paper; also do not fill `instance:` with another segment's venue name.

**One fence per round.** To change it, **change that one** (resending three times in a round leaves the next layer not knowing which counts); if a resend is truly needed, say first "the previous one is void, this is the only one".

**Identifier rules.** The owner names it; the tool never invents one. **At start-up, if the user gave no `<identifier>`, or `data/<identifier>/WISH.md` is absent — exit at once, do not guess, do not invent a wish from zero.** Directory present, `BOSS_CONTEXT.md` absent → **build from zero**; both present → **repair** (fix stale state, add clues, mark gaps), **never start a second file**. The directory is **relatively idempotent**: change machine or checkout location and `data/<identifier>/` still points at the same wish, **and no absolute path is written into documents**. It is read as the commission's first input, so a badly written one propagates into every dispatch that follows.

- **The wish is quoted from the record, and the record is read in the same turn.** A `WISH:` line carries `source: <transcript path or export key>:<line>`; the quote is not reconstructed from memory, not from a summary of the conversation, not from a shorter restatement given later. **A summary is a pointer, never a source** — a file rewritten after a summary rather than after the record is precisely how a part of the wish disappears unnoticed.
- **When two records differ, the fuller earlier one governs.** A later shorter sentence may narrow the scope only with the owner's confirmation, and the file says which part it dropped and why (`dropped: <part> — reason`). A silent narrowing is a deletion.
- **The hand-over is two lines (`id:` then the path), but the turn is not one act.** Besides dispatching, the owner does three things, **and does them first** (reversed, the layer below has to guess):
  - **The context names seven semantic points, each with one sentence of use.** ① the wish itself (which file, which line) ② the thesis (only the owner writes it) ③ **the literature library** (where PDFs land, where the index is) ④ **where the draft lands** (assembly directory, build command) ⑤ **samples to benchmark against** ⑥ **the workspace root** (packages, data, the experiment ledger). **Each says what it is for**; a bare path is not writing it; **if something does not exist, mark `unknown(to locate)` — never create a same-named directory to fill the slot**. This is not project detail but a position table true of any project. ⑦ **development skills** (where card rental or a model prerequisite lands, which reading counts as enough) — **it decides whether there is a machine before this round starts**, so it is listed at the same level as the writing skill, rather than letting the executor discover there is no card.
- **The count in a maintenance report must equal the rows in its table.** Say "8 places changed" while the table lists 13 rows and the reader does not know what to believe — **never estimate what can be counted**: places, lines, items get countable numbers; **an estimated number is worse than none** (it looks checked).
- **Read only the tree handed to you this round; other cases are other windows.** Material in `cases/<other id>/m/`, the previous wish's directory, a sibling project's same-named file — **none of it is your input**. Reading them has two consequences: ① **facts from elsewhere get written into this context**; ② **someone else's prompt becomes your "reference standard"**, so you believe you know the grading convention. **Criterion**: a `cd` or `read_file` outside this round's material tree, and not this layer's role document or the project's own rules → window breach.
- **Readings are taken only in the tree you were told.** Materials come with their location (a case's `m/`, a project's `workspace/…`); **running the same command in another tree does not give "a fresher reading", it gives another tree's facts** — written into the context, that treats someone else's disk as yours. **Criterion**: a `cd` whose target differs from the specified tree's root is a cross-tree reading.
- **A reading carries its convention, or three numbers from one directory read as three contradictions.** Write "21 files" and you must say "`ls -A` excluding hidden entries and `__pycache__`"; the same directory reading `3` in another tree is **another tree's fact, not a wrong value** — **with the convention stated, both numbers can coexist**.
- **The pointer line says only where the report is; do not announce that "the file and the fence agree".** A file is **a record**; announcing agreement makes the reader go read the file next and treat the file as the delivery. **That sentence says `the report is at <path>` and stops there.**
- **With a real listing in hand, do not keep an old number.** One `find -type f` has listed the whole directory while the context still says last version's "22 files, three `*.draft.tex`" — not "no time to fix" but **writing a false reading while looking at a true one**. **Fix one reading and recheck every sibling number in the same paragraph.**
- **Change an assertion and rerun the command that produced it.** Copying "22 files" **into a new sentence moves an old error to a new address** — **the disk changed, so the reading must be retaken**; and **write the command and its output into the context** so the next person can replay it. **"Fixed" means the reading agrees with `ls`, not that the sentence changed.**
- **A line pointing at a sample or product must point at an openable file, not a directory.** `<dir>/` says "it is somewhere around here" and the receiver still guesses which file; `<dir>/final.pdf` says "compare against this". **Same for `compile.py` pointing at a file and `outputs/` pointing at a specific `*.json`.**
- **Every `path:line` in the context must first survive an `ls`.** Citing a non-existent `*.draft.tex:127` is not a typo, it is **an old reading moved into a new context** — the reader checks, gets "file not found", and the whole context's credibility drops to zero.
- **Fixing stale state**: an expired assertion ("prerequisites are done", "the code is in place", "the literature is enough") is **changed to what is true now**, with the evidence read (`path:line`, or a command and its output). **Record useful clues**: where the key tool is, where the key asset lands, which road was walked and failed — **one search saved downstream is that clue's whole value**. **Mark gaps** as **a mark the next layer can pick up and locate**, not an adjective: the vocabulary is fixed at five, `missing literature` / `missing code` / `prerequisites incomplete` / `below bar` / `unknown(to locate)`, each followed by one reading or path saying how you saw it. **Better `unknown(to locate)` than blank** — a blank reads downstream as "no problem".
- **Why the owner maintains the context at all — the arithmetic of it.** `BOSS_CONTEXT.md` is the only input **every** round of **every** layer reads. One stale assertion is not one mistake: it is copied into every dispatch until someone catches it, and one missing clue is not one search: each layer pays it again. **A false line costs three layers one wrong decision each; a clue saying where the tool or asset is saves three layers one search each; a gap marked `missing literature` saves the lead dispatching work that cannot run.** That is the whole motive for the three acts above: fixing stale state, recording clues and marking gaps are the cheapest edits in the project, because they are read more often than anything else I could write.
- **The owner may not know the gap's exact shape, and that is fine.** The obligation is **to mark the gap where it can be picked up** (which block, which reading looks wrong), not to cut it into tasks for the layer below. **When precision is impossible, marking "which paragraph looks wrong" still beats "keep going".**
- **The owner's hand-over is two lines: the identifier, then the path to the layer's entry — plus the sentences saying what he saw.** `id: <identifier>` first, the path of `01-supervisor.md` second; plain speech outside the fence, **saying what he looked at and saw, what this stretch covers and what is out, and what he wants checked for him** — **not a brief, but this round's only decision record**; **its length is not fixed**, and no count is imposed on it; **the order of the work is not in it**. **Why not the path alone**: a path says "which rules to use" and **cannot say "which wish this is"**; with several wishes in flight the receiver can only guess from context, and that is where lines cross. **The identifier travels verbatim down every layer** (supervisor into the fence, lead into the dispatch, executor into the return), **and whoever changes it creates a second wish.** Everything the supervisor needs — position, read list, product, constraints — is inside `01-supervisor.md`; everything about *what the work is for* is inside `data/<identifier>/BOSS_CONTEXT.md`, which the supervisor opens itself. **The owner who writes six paragraphs has done the supervisor's reading for it and left a second copy of the wish on disk.**

**And it travels in a `PROMPT` fence, like every other hand-over in this loop.**

```PROMPT
id: <identifier>
/abs/path/to/01-supervisor.md
```

— info string exactly `PROMPT`, **exactly two lines inside**: `id:` first, the entry path second. **A one-line fence is not a hand-over** (the receiver cannot know which context to read), **and three lines is not either** (the third line is a second wish). **Do not wrap it in another code block** — an outer four-backtick shell degrades the hand-over into "text inside a quoted block", which the reading layer treats as a quote or fails to parse. **To show it to the user, paste the fence itself.**

**The maintenance report does not go in the reply; the plain speech does.** How many places changed, what the new values are, what was saved — **those go in the file**, and the reply carries at most "report at `<path>`". **Writing maintenance notes into the reply makes the receiver hunt the hand-over inside prose**: it reads the prose, treats the fence as an appendix, or concludes nothing was handed over. **Conversely, dropping only the fence with not one word of judgement is also not handing over** — the fence says "to whom", the plain speech says "why this item".

**Several fences may be handed over at once, but each is a complete hand-over.** **Owner: exactly 1** (one wish, one entry). **Lead: 1–5** (concurrent dispatch to independent units; dependent items wait for `resolved`). **Supervisor: 1** (one complete dispatch). **The rule is not "only one" but "every fence must be able to start work independently"** — so with several: each block opens with `# purpose` and `# what to do`, and **the last paragraph after all are posted reports the count** "N dispatched this round", listing each number and its purpose in one line. **The count is not politeness: the user copies by the count, and one missed means one item not run.**

**"No fence inside" means inside the body, not deleting the opening and closing pair.** A `> PROMPT` quote block is no fence; criterion: **exactly two** ``` in the reply.

**No ``` may appear again inside the fence.** It opens and closes with one ``` each, and the body **contains none** — for a code fragment use inline `` `x` `` or an indented block. **The reason is not fussiness**: one more ``` cuts the fence into two in plain text — **copied back it reads as two fences, the probe's needle falls outside the break, and judging counts one delivery as two**. **Criterion: the count of ``` inside the fence body must be 0.**
  **Three ways this is still not a hand-over**, all seen in practice: ① **commission content** outside the fence (the wish, a read list, a summary, criteria — a second copy; while "what I saw and why dispatched this way" is not commission content and belongs outside) ② more than **two** lines inside, or a path with no `id:` ③ an empty info string, `text`, or `code` (the receiver recognises a commission by `PROMPT`, and stops when it cannot). **These three are stable skill, not written into a project's context**: change project and the format does not move. The loop already reads commissions, fences and dispatches out of `PROMPT` blocks; an owner's hand-over written as an ordinary code block is a **second format for the same object**. **One object, one fence, one info string.**

- **The frontier is not the owner's to define.** Which experiments fall inside the wish's first clause is work of the layer below, decided against the thesis and the tree; the owner states the wish and the exclusions it actually holds, then stops. **An owner who pre-dices the frontier has replaced the first round with their own guess.**

**And the comparison's authority has a home too (O-a).** Rows are not comparisons. **"Compared to whom, and how close must the gap be to count" is a bar, and a bar comes from the owner** — so the owner's window carries one more slot: the neighbour work he means (or `done: not stated`). Downstream may not invent it: the supervisor may carry the neighbour the owner named, the lead may align settings, the executor may mark a pair `not comparable` — **none of them may decide that a claim needs no neighbour at all.**

## The owner's context serves every layer — each has one question only it answers

**A context that only the supervisor reads is a filing cabinet. In a company everyone knows the mission and the house style without being briefed** — not because they memorised the org chart, but because each role has a question that only that shared material answers. So the owner's context is **project state**, and each layer is driven to it by its own question:

| layer | the question that pulls it to the context | what it takes away | what it must not take |
|---|---|---|---|
| **supervisor** | "what is the boundary of this commission — what did the owner include, what excluded, in their own words?" | the `WISH:` sentence verbatim, the exclusions, the invariants | the right to add a standard |
| **lead** | "which clause does each of my items serve, and what is the bar for calling it done?" | the clause wording, the **`WRITING:` pointer**, the owner's bar (or `done: not stated`) | the right to re-word the wish |
| **executor** | "what does 'good' mean for this item, and which section does it land in?" | the bar for its item, the section it feeds, the `WRITING:` pointer | the right to define a new bar |

**The writing guidance is project state, not a manager's opinion.** The context carries `WRITING:` — the path to the project's writing-strategy set (`docs/writing/skills/*` and the loop's `§5`) — so **every layer reads the same standard from the same place**. A layer that quotes the standard by path can be checked; a layer that says "the writing should be better" cannot. **Nobody re-invents it, nobody restates it in a dispatch, nobody hands a copy to a sub-layer: the pointer is the culture.**

**`WRITING:` is a directory, not a file list — that is what makes it idempotent.** Reorganising prose guidance is normal; rewriting four layer documents every time it happens is not. So the convention is fixed at three points and nothing else moves: ① **the path is a directory** (`docs/writing/skills/`), valid however its contents are split; ② **the entry is the `00_`-prefixed file inside it** — the only naming rule, chosen because sorted order puts it first; ③ **the mapping lives inside that entry** (`task → file`), so a reorganisation edits one table and every layer's invocation stays the same. **A layer cites the directory plus the entry, never a file list.** A draft citing `01_abstract.md` after the standard moved is a stale citation but not a stale pointer — the entry's table is where the stale name gets corrected.

**Why a pointer and not a summary**: a summary drifts the moment the standard changes, and it hides which rule was violated. The pointer survives both.

### The owner's window: what he holds, and what each holding makes possible

**The owner reads nothing from the loop — he *is* the source. What he holds is what makes "one path" sufficient instead of lazy.**

| the owner holds | it is what makes this possible | without it |
|---|---|---|
| **the wish**, one sentence, with a source he can point at | handing **one path** is enough, because the wish is already on disk | the layer reconstructs the wish from chat — a copy that drifts |
| **the thesis**, addressable (`path:line`) | the supervisor can report the paper-side exit | one exit; the manuscript is never a condition |
| **the context file**, three invariant lines | the layer never asks where the project is or what it is for | a round spent on questions the file could answer |
| **the exclusions he actually holds** | the boundary is stated once, by the only person entitled to state it | the layer either over-reaches or crawls |
| **the tree** (he names outcomes, not tools) | the layer picks materials and instruments | a hand-over full of tool names that rot |

**And what he must not hold is just as load-bearing**: the layer's read list, the judge's criteria, the split. **Holding those makes him brief** — and a briefed layer never has to find anything, so the documents stop being tested.

- **The wish is quoted, never paraphrased.** The objective line is their sentence, verbatim, marked `WISH:`; a restatement, if kept at all, is a separate line marked `(mine)` and **must enumerate the original's parts one for one**. "Complete the pre-experiments **and everything before them**" is not "finish the experiments and write the report": the dropped conjunct was the larger half of the scope, dropped silently.
- **Conjuncts are load-bearing.** A wish with `和`/`及其`/`以及` has parts; each survives into the objective or is explicitly excluded with the owner's agreement. Compressing a compound wish into one clause is scope deletion wearing the clothes of a summary.
- **No motive, no feeling, no standard the owner did not state.** "Presentable to the advisor", "good enough for reviewers", "so the defence goes smoothly" — inventions, worse than inventions about facts because they redirect every later round toward a bar nobody chose. An empty slot stays empty: if the owner did not say what "done" means, the file says `done: not stated` and the commission asks.
- **Write intent, never facts.** The objective in the owner's words, what counts as done, what is in and out of scope, the bound ("a handful of rounds"), the constraints the tree cannot show, any acceptance beyond the loop's own. Facts about the tree belong in `data/<identifier>/loop_state.json`, each carrying the command that produced it.
- **Not even a reading of the materials.** "The tree has seven files, all read" is a fact about today: it goes stale the moment a file is added, and it invites the next reader to trust a count instead of running the command. The context says **where to read**, never **how much is there** — no file counts, key counts or section counts, not even as provenance.
- **The wish is pinned in one file, and the context carries its path as a stage-invariant.** `WISH_FILE: <path>` (`data/<identifier>/WISH.md`, located relative to the identifier) — one stage, one wish file, and the location is itself the invariant: **no renaming, no moving, no restating elsewhere.**
  - **Only two things go in that file: the words, and where they came from. Method does not enter the wish file.** Common contamination: "pave first, then build", "all three kinds of work must be done", "rechecking also counts as paving" — **those are the loop documents' content, and here they become a second copy of the method**: change the loop and the copy expires; and they make the wish look like a project plan, when a wish precisely should not be a plan. Criterion: **delete every paragraph that is not "who said what, when", and the wish's meaning must not change** — those paragraphs do not belong.
  - **A natural-language test**: read the wish to someone who has not read the repository; they must be able to say "what is to be made", not "what process to follow". **"What gets done" belongs to the wish; "how" belongs to the method.** The context cites the path and quotes the `WISH:` line, and the fence cites the context's `WISH:` line; **wherever anything disagrees with the wish file, the file governs and the other copy is fixed to match**. The wish is replaced as stages advance, **but the replacement happens in that one file, not in a new version of each layer's document**.
- **Name the invariants; never enumerate the variables.** An invariant is a rule or a location still true next month — a numbering scheme, a build chain, where the prose is assembled, which file states the thesis. A variable must be re-read each time — how many keys, how many rows, which drafts exist, what ran last. **Writing a variable into the boss context is how the next round inherits a number that was true once**; the context says where to look, and the lead measures.
- **Name the capabilities, point at their manuals — and their limits.** One line per capability: what it can do, **its ceiling** (quotas, parallel instances, what is unavailable), and where its manual lives. **A plan is only executable against the ceilings**, and a ceiling discovered at run time has already cost the round: a lead scheduling six parallel runs against one GPU is following a context that described powers without bounds. **How to operate an instrument is not the context's business**; that it exists, and where to read it, is.
- **Say what will deliberately not be done.** A wish with no exclusions produces a commission that tries to cover everything and closes nothing.
- **Steer in three moves.** Context added mid-flight is recorded verbatim and resolves to one of: a check narrowed, an item replaced, an item added by name. Steering that widens the work without adding a named item is the expensive kind of drift.
- **Overwrite, do not negotiate.** When the owner writes the file properly, that version wins without discussion — the bootstrap was only ever a floor.

## A round has three phases, and the third one is still paving

**The thesis is the start, the work is the core, the recheck is maintenance and settling.** Paving is not only what happens before work: **maintenance, debugging and debunking also count as paving** — checking that a cited paper is in the library, that its conclusion still binds to the same thesis site, that no other mechanism has been quietly substituted for the one we claim. Those tasks produce no new readings, which is exactly why they get skipped, and exactly why every round after that runs on a crooked road.

**The checklists live in `execution-loop.md` §3.19 (3.19.1 paving, 3.19.2 recheck), and they are open lists**: each wish adds rows. The fuller the list, the more one round of bottom-layer work can carry.

## Small steps up: freeze, pave, take the number, scale

**A path's work has four rungs; each answers one question, hands over one thing, and permits the next rung only on a specified reading.** Whoever skips a rung gets numbers that cannot be attributed; "get it running first" usually stays put, and when it stops there is neither a direction nor a product in hand.

| Rung | It answers only | Its product (missing = the rung was not done) | Reading needed to climb |
|---|---|---|---|
| **freeze** | which link is wrong, and on what basis | one locating sentence: the link named (data / code / criterion / dependency) + one rerunnable command or `path:line` | the reading points at **one specific place**, not "it does not work" |
| **pave** | can this road start | one command reaching a product in a clean environment, with its exit line | the command exits clean, the product lands |
| **take the number (minimum scale)** | is this direction moving | one reading + its footing (against what, same source or not) | moves as expected and clears the noise or spread at that scale |
| **scale** | is it still this direction at full scale | a full reading + cost (device-minutes, memory, frame time) | the exit is judged by §When the loop is finished |

**Four hard rules:**

1. **One rung at a time.** Scaling requires a minimum-scale reading that moved as expected and cleared the noise; scaling without it is not acceptance, it is rerunning the most expensive step. **A reading inside the noise is "direction undetermined"** — change the hypothesis, do not add scale.
2. **The rung's product is its return credential.** "Most of the way through", "the environment is installed", "still looking" are not products; without a product the next rung has nowhere to land and the previous one cannot be judged.
3. **Freeze is not an impression.** It names the link (data / code / criterion / dependency) and gives one rerunnable command or `path:line`; cannot write it, you are still freezing — no paving, and never body text written to fill the gap.
4. **A small step is not a smaller delivery.** Each rung leaves something the next layer can use directly: a runnable command, a row fit for the table, a locating sentence that points at a place. Ending a round with "still feeling it out" means the round did not happen.

**The criterion is written by the layer above, never by the executor.** The owner sets which rung this stretch starts at and which rung delivery stops at (that is scope); the supervisor writes each rung's release reading into the fence; the lead gives one rung per leaf, with the scale-up leaf depending on the minimum-scale one; the executor runs until this rung's product lands. **Hand a rung's product to the next layer and it must be able to answer "is this rung done, and on what basis"** — if not, the rung has actions but no criterion.

**The executor's persistence: return only when the rung is done, and an early return has three reasons.**

- **One dispatch runs until its rung's product lands.** No returning midway, no handing control back between two steps to wait for instructions; the `tick` and the state card exist to be seen, not as a reason to stop.
- **Three legal early returns**: the criterion is genuinely unreachable (say which sentence does not read as an executable action), a hard block (permission, missing source, a scope only the owner can set), budget reached (with spent and obtained attached). **Any other early ending counts as undelivered**, however tidy the return.
- **A breakpoint must be resumable**: three items when interrupted — the next command to run, one line of current state, one line of known traps. Missing one and whoever takes over restarts from zero, and this round's cost buys no progress.
- **Scaling adds one notch at a time**: scale, arm count, view count — move one. Scaling two at once leaves a todo list on failure, not information.

## When the loop is finished

The wish is the exit condition, and it is checkable without judgement calls. The loop is done when **every clause of the `WISH:` sentence is on one of two sides**:

- **carried** — the draft has a sentence for it and that sentence has a row behind it (`table.md` line, `metrics.json` key, `figures/…`), **and the leaf that owns that row is `done` with `evidence` pointing at it** — a row whose producing leaf is `paused` or `fail(result)` does not exist yet, so the clause is `open`, not carried, and the manuscript line stays empty instead of restating why it is missing; or
- **excluded** — the boss context says it is out of scope, with the owner's agreement recorded (`dropped: <part> — reason`).

Plus two mechanical conditions: **no leaf left `not_started` or `in_progress`** (`paused` does not block the exit, but its count is reported separately), and no open hard block. **Anything else — a section that "reads well", a report the advisor would "probably accept" — is not a completion test**, because it cannot be recomputed.

**Once a clause is carried, it stays carried — every round re-checks it.** The exit condition is a property of the whole draft, not a milestone: a later edit can orphan the row a carried clause leans on, and nothing in a per-round dispatch would notice. So each round recomputes the pointers for clauses already carried (`carried: <path>:<line>` re-resolved), and a clause whose pointer no longer resolves **reopens** — it is not "done, with a caveat". **A loop that only counts newly-closed clauses drifts backwards silently.**

**The thesis has a writer, and a change to it re-derives everything downstream in the same turn.** The thesis belongs to the owner; nobody else edits it. When it changes, the boss context is re-derived against the new text and every pointer (context → fence → item → row) is re-checked before the next dispatch. A stale `thesis: <path>:<line>` is worse than a missing one: it resolves, and it points at a thesis the project no longer serves.

**Pointers are project-relative, and they are resolved, not assumed.** Every pointer is written relative to the project root and quoted with its line; an absolute path breaks the moment the tree moves, and a bare filename is not a pointer. Before reporting, the round resolves each pointer it cites — `path:line` must open to the sentence the report claims is there.

**Two exits, and satisfying one does not satisfy the other.** `execution-loop.md` §5 is the *paper-side* exit (every headline claim traces to a row and an anchor); this section is the *wish-side* exit (every clause carried or excluded). A draft that passes §5 can still fail the wish — §5 never asks whether the sentences are the ones the owner wanted — and a wish fully carried can still fail §5 if no anchor backs it. **Both are required**, and the report says so in two separate lines rather than one.

**Who checks it, and with what.** The supervisor verifies, and its judgement carries one line per clause: `clause "<text>" → carried (<path>:<line>) | excluded (dropped: <part> — <reason>)`. A clause with neither a path nor a `dropped:` line is **open**, whatever the prose says; the number of open clauses is the round's honest progress measure.

**A clause that can be neither carried nor excluded is a hard block, not a judgement call.** When the owner has not agreed to drop it and no row can support it, the round stops and asks — **rewriting the wish, or quietly deleting the clause, is the one move never available downstream**.

The last round's report therefore has one extra obligation: **name, for each clause, which side it landed on**. A round that reports progress without moving a clause from one side to the other has not advanced the wish, however much it changed.

**The needle's content may not enter your own session.** It is text **that appears verbatim in the session under test**: `cat` it once, or copy it into the reply, and it now also appears in **your** session — probe with it again and **it hits you**, and the judgement is void on the spot.

- **Pass the path only**: `--probe <needle file>`, never reading the content. To confirm it was not modified use `wc -c` / `shasum`, **never `cat`**.
- **Never quote it**: the judgement says "the needle hit `key` (`hits=1`)", **never the needle's sentence**. Once copied into a conclusion, the conclusion is polluted by it.
- **Check the hit count first**: only `hits=1` locates; with `hits>1` **first suspect "did I print it myself"**, then anything else.
- **Zero hits is terminal**: the needle is invalid, the item is `unjudged`, **do not retry with a synonym** — a different word is no longer what the other side wrote.

**A passing reading is not the right direction.** Every round has an acceptance line, usually made of numbers (steps, non-finite values, exit); but **when the numbers pass while the product carries no information (a monochrome figure, a metric jittering inside the noise), the correct conclusion is "direction unverified", not "done"**. This lands on two layers: the executor's return must carry a `## signal` section; the lead must set a threshold that can show a difference when cutting, and judge `fail(marginal)` at collection for "passing but no signal".

**"State is readable" is a duty of all four layers, not the executor's alone.** The supervisor states this round's **observation points** (what to look at to know it went wrong); the lead states **where the run sheet and state card land** (which section, what format); the executor writes at that landing point. **Any layer that hands over results without state leaves the next layer guessing** — and the guess enters the next round's cut: wrong downstream, rooted upstream.

**Collection can judge because the executor leaves three things**: the `status word` (one of five; "basically done" = `BLOCKED`), the `criterion → reading → line` mapping, and the `process` (tick lines + route changes). **Miss one and the lead must find the numbers and guess the situation itself** — that is not collection, it is redoing the executor's work.

**So one sentence holds at all four layers**: **every dispatched item must be judgeable, every return must be checkable item by item.** An unreachable criterion, an insufficient write scope, no signal — all are **legal conclusions in a return**, not failures; **only "not stated clearly" fails.**

## How the work is judged

The rubric is held by the supervisor and is deliberately not handed to the session being examined: nine things an answer must be able to state (problem, why it matters, contribution, advance, evidence thickness, what is missing, manuscript ↔ thesis, what changed, what a section contains), the way it has to be said (prose, pointers inside the sentence, the reader's order, ending with what could not be established), and the four ways an answer is rejected (reciting the invariant with no filling, a pointer with no path, the document's order instead of the argument's, claiming everything is established).

A layer's document states the interface; this file states the expectation. Tests of behaviour are run against **this** file: if a session does what its layer document says and still disappoints, the expectation is what needs writing down here.

## Starting any layer: what the expected input looks like (one extra word is wrong)

**When the user asks to "start a layer", the prompt she sends has a shape.** Get it wrong and that layer guesses from the first second, and every layer after it cleans up the guess. **The shape governs only "what is handed to it", not "what it hands back"** — the returning half (including the plain sentences outside the fence) is specified by the started layer's own document.

| Layer started | The prompt should carry only | It must not carry |
|---|---|---|
| **owner** (human → owner) | **two lines**: `id: <identifier>` + **the absolute path of `00-owner.md`**; **the wish is not pasted into the prompt** — it is already in `data/<identifier>/WISH.md`, and the prompt gives the `id` so it can find it | the wish verbatim, the repo root, "land the context yourself", "the commission is yours too", "remember to write `BOSS_CONTEXT`" — **neither the words nor a product list enter the prompt** |
| **supervisor** (owner → supervisor) | **two lines**: `id: <identifier>` + the absolute path of `01-supervisor.md` | any body text, any "you must do X", a restatement of the wish |
| **lead** (supervisor → lead) | **one `PROMPT` fence**: `id:` + the path of `02-lead.md`, then a commission of at most five sections (goal, exclusions, exit, bounds, write scope) | implementation detail, criterion thresholds, line-number lists |
| **executor** (lead → executor) | **one `PROMPT` fence**: `id:` + the path of `03-executor.md`, then **one block** (`# unit #n`, what to do, which file, acceptance line, return path) | a second block, the upstream history, other units' content |

**The fifth check: the path on line two must name the layer being started.** For the owner → `00-owner.md`; supervisor → `01-supervisor.md`; lead → `02-lead.md`; executor → `03-executor.md`. **"Have the next agent play the owner" while handing it `01-supervisor.md` starts a supervisor** — the task changed hands in the first second, and no amount of careful judging afterwards judges the right person. **One sentence**: read the file name on line two and compare it with the layer you asked for; if they differ, fix it.

**Three prohibitions**:

1. **The prompt does not state the product.** "You must hand over the context and the commission" reads this layer's document for it; **it should learn from the document what the product is**.
2. **The prompt does not state the criteria.** Criteria go in the fence's "exit" section, given by **the layer above**; the user does not give thresholds in the start-up instruction.
3. **No layer restates the wish in the prompt, not even the owner.** The wish has one home: `data/<identifier>/WISH.md`. **The prompt gives the `id` and the receiver reads it** — a sentence pasted into the prompt becomes a second "source", and once the two differ nobody knows which counts.

**One criterion**: show the user's start-up prompt to someone who has not read this project; they should know **what to do**, and should not know which files to hand over or what the criteria are — **the latter is read from the documents, and reading it wrong must be visible as a misreading, not as copying the user**.

## How a layer starts: a commission is a prompt, never a document

Three hand-offs exist, and **each is a prompt handed to a fresh session — not a path to a document that happens to mention that layer**:

| Hand-off | What is handed over | What that session then reads |
|---|---|---|
| owner → **supervisor** | **one path: `01-supervisor.md`**, plus the owner's two-to-four sentences saying what he saw. The document *is* the commission — position, read list, product and prohibitions live inside it | this file (method + §Where the interfaces live), the instance's `executor-notes.md` |
| supervisor → **lead** | the **fence** (`PROMPT` block): objective, exclusions, exit condition, bound, write scope, materials | this file, the shared loop doc, `03-executor.md` |
| lead → **executor** | the **dispatch**: one item per line, with write scope and the clause each serves | `03-executor.md`, the instance's `executor-notes.md` |

**The method document is what a layer reads; the commission is what it is handed.**

**Each of the four layers has its own entry document**: owner `00-owner.md` / supervisor `01-supervisor.md` / lead `02-lead.md` / executor `03-executor.md`. **Each says on its first line which layer you are** — identity is written in the document, not in the prompt.

**The layer's own document is the commission, and there is no second file.** Handing a fresh session the path to `01-supervisor.md` makes it the supervisor: the file opens by saying so, then states what it reads, what it emits and what it must not do. **A separate `staging/commission/<layer>.md` would be a copy of that file's sections — the second copy that drifts.** The human is the owner: the owner's hand-over is that one path plus the sentences saying what he read, because everything the position needs is inside the position's file and everything *this round* needs is in those sentences.

**When two conventions in the same project disagree, the newer one does not win by age — it wins only if it says it supersedes.** No supersede line, no effective date: they are peers, and the work stops until the owner says which governs. `03-executor.md` carries the operational form of this.

**The wish lives in one idempotent file, and nobody restates it.** Its place is `data/<identifier>/WISH.md`; `data/<identifier>/BOSS_CONTEXT.md` carries the pointer `WISH_FILE:` plus the wish text **as the owner said it**, and `thesis:` beside it. **A hand-over never repeats the wish** — not in the commission, not in the fence, not in a chat message: restated, it becomes a second copy that can drift, and the layer stops having to read the file. **The layer reads `WISH_FILE:` and opens it.** If the pointer or the file is missing, that is a halt, not an invitation to reconstruct the wish from memory.

**A commission handed to a layer carries the identifier and one path.** Two lines: `id: <identifier>` + **that layer's own entry path**. The identifier says **which context and wish to read**; the path says **which rules to work by**. **A hand-over with a path but no id leaves the receiver guessing which wish** — with several in flight, lines cross. The path points at **that layer's own entry** — **never at the upstream context** (`BOSS_CONTEXT.md`, the wish, the thesis): naming those does the layer's first job for it, and the layer then never has to find them. The working directory, the position, the read list and the product all live inside the entry document; the hand-over is the address of the entry, so `id:` plus one path is the whole commission — **a third line of instructions has already briefed the agent twice**. The plain sentences outside the fence are not a third line: they do not say "what you must do", only "what I saw".

### Tool hard rules are defined once, in the tool, and referenced upward

**A tool's hard rules (how to invoke, how to stop, when billing starts) are written once, in that tool's `SKILL.md`.** Other layers **cite the section name only**, never copy the clause:

| Layer | What it cites | Why this layer |
|---|---|---|
| **owner** | nothing (gives a path only) | the owner should not memorise commands for the layer below |
| **supervisor** | the tool's **stop/charge section** (e.g. `compshare` *Wrap-up contract*) + **the budget section** (`compshare` *When the budget is days…*: smoke / budget / ≤5-minute poll / stop) | the fence must be able to say whether this round burns money and how it closes |
| **lead** | the above + **each item's release clause** | cost is cut at this layer |
| **executor** | **read those two sections before starting**, and its delivery self-check includes "released" and "smoke passed" | the one who actually presses the button |

**Why not copy into all four**: four copies become four versions, and once one version of "how to stop the machine" expires, the most expensive experiment runs on the expired one. **Cite the section name; leave the clause where it lives.**

## Where the interfaces live

The four positions are stated **once** here (what each is expected to do) and their interfaces live in the four files beside this one:

| Position | Expectations (this file) | Interface | Acceptance |
|---|---|---|---|
| supervisor | §What the supervisor is expected to do | `01-supervisor.md` | **`01-supervisor.md` §Ten lines: what a passing reply must satisfy** |
| lead | §What the lead is expected to do | `02-lead.md` (one file, one body, no second copy) | `02-lead.md` §Requirement table (ten requirements → where each lands → how each is checked) |
| executor | §What the executor is expected to do | `03-executor.md` + the instance's `executor-notes.md` (venue only) | `03-executor.md` §0 and §six intake defaults + §Level by level + the instance's failure forms |
| owner | §What the owner is expected to do | `00-owner.md` + `data/<identifier>/BOSS_CONTEXT.md` (a product, not a document) | `00-owner.md` §Five checks before you dispatch |

**The positions live in the shared docs and never in the template.** Nothing about a position is copied into `instances/<id>/` — an instance carries only its venue vocabulary (`executor-notes.md`), so **changing a position is one edit, and no copy can drift**. Three interfaces stay separate so a change to one does not renumber the others.

**The ecosystem is part of every window, and each layer is tested on its own slice of it.** A layer that cannot name the code root, the literature store or the skill that owns an instrument is not being modest — it is about to dispatch fog. The slices divide by action, not by importance:

| layer | its slice of ecosystem state | what the slice is for |
|---|---|---|
| supervisor | skill catalogue + project indexes + code roots + assembly dir + state file | the fence's capability lines and material list resolve to paths |
| lead | the same, plus **which instrument each item uses and where its invocation form lives** | the split is executable, and write sets follow the tool |
| executor | **the `SKILL.md` of the tools its item names**, plus the tree read-only | the item is done with a real tool and a reproducible reading |

## Each layer's window, and what its status answers are worth

**The window is the experiment.** A layer may read only what its own file names; everything it says about the work is then evidence about those documents, not about a shared context. Closed on purpose: if a layer can read everything, a correct answer proves nothing about any single document, and the next session with the same window guesses where the last one read.

| layer | window (and nothing else) | its answers | a reading that fails |
|---|---|---|---|
| **owner** | its own context, the wish file, the thesis, the tree | none — the owner is the source; it hands one path | handing a brief instead of a path |
| **supervisor** | `01-supervisor.md`, the project tree, the context + wish, `skill.md`, `execution-loop.md`, the instance's `executor-notes.md` | (does not answer the four) it must **carry the split** so the lead can | a fence with materials but no next-work split |
| **lead** | `02-lead.md`, the fence, `skill.md`, `execution-loop.md`, `03-executor.md`, the instance's `executor-notes.md`, tree read-only | ① what gets built and what proves it ② how the manuscript reads ③ what each section owes, in what order ④ what is done now (counts, order, deferrals) | answering ② from imagination while ① has no readings; asking the supervisor what it could have read |
| **executor** | `03-executor.md`, **its one item**, `execution-loop.md` (the shared spine — `03-executor.md` points at §1–§2, §3.3–§3.5, §3.8, §3.10 instead of copying them), the instance's `executor-notes.md`, tree read-only | the same two questions at item scale: what will exist and what proves it; where it lands in the manuscript | "changed the file" as proof; reading the whole fence to decide its own scope |

**How yesterday's status-question motive lands here.** Its form was: one document, no questions, no plan, no files touched — *say what a round builds and what the manuscript reads like, and mark what you cannot determine*. That was a transmission test with one arm. **In the four-layer loop the same test is the standing duty of every layer, at its own scale**: the lead answers both questions for the round, the executor for its item, and neither may fill a gap from outside its window. So the old `BLIND=<paragraphs>,<sections cited>,<rules invented>` self-report becomes three things a reading must check: **does the answer cite only window material, does it mark the undeterminable, and did it invent a rule the documents do not contain.**

**A gap the layer cannot close is a defect in the documents, not in the agent** — the reading says `doc gap: <path> §<section> never says <what>`, and the fix goes into the document. An agent that fills the gap is the failure the original test was built to catch.
