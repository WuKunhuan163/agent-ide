# Working order: results → footing → narrative

**This file states the loop; the vocabulary lives one level down.** A reader holding only this file knows the shape of a round but not the nouns of the field it is run in: which quantity a row carries, what a "protocol" is called here, what the venue prints. That is by design — the loop is shared, the words belong to the instance (`src/template/instances/<id>/docs/strategy-roleplay/executor-notes.md`). Two consequences follow. An answer built on this file alone is correct in shape and silent in words; it must say so rather than supply a vocabulary. And when the words do exist in the instance, they are quoted, not paraphrased — a renamed quantity is a new quantity.

## The story in six sentences

**A paper is not written; it is assembled from results that were read before they were described.**

You run something, you look at what came out, and you write down **what it can be compared against** — that line is the footing. Only then does a sentence earn its place.

**A round therefore has one shape**: pick the next thing that is worth doing, do it, read the result, decide whether the footing holds, then say where that leaves the paper.

**The number at the end of a round is not a grade.** It answers one question: how much of the thing the owner asked for is now standing on evidence. If the number cannot be recomputed from a file, it is a feeling.

## 1 The claim under test

**Footing** is the line under a result that says which earlier study's setting it can be read against, and why it cannot be carried elsewhere; a row without one is a number nobody can compare. The order this document describes is results first, then that line, then the prose that consumes both.

The common advice is that a paper is built as: hypotheses from literature → experiment → test → conclude. The observable record says otherwise. Papers are **worked out** as: run the analysis → read what the results will support → find the literature that gives each number its footing → choose the narrative that survives the weakest footing. The printed hypothetico-deductive form is a **presentation**, reconstructed after the analysis, not a description of the order of work.

Two checks make the claim observable on any corpus, and both take minutes. The first compares the reference set cited in the introduction with the one cited in the discussion: if the discussion draws on literature the introduction never mentioned, the framing was written after the results. The second counts how many papers state numbered hypotheses or explicit expectations before their methods section: where most do not, the experiment was not designed to confirm a prediction, and "unexpected" in a results section is the narrative being revised rather than a surprise.

## 2 The failure mode this order invites

Writing the chapters first and fitting the results into them afterwards: each section then promises something the data may not deliver, and the promises are discovered late, when the prose is already built on them. The order in §3 exists to make that failure visible early — a section that has nothing to put in it says so in its first five lines instead of in a reviewer's report.

## 3 The loop: the thesis directs the work, the work rewrites the thesis

The spine — the four moves a report is built along, each one consuming what the previous one left — is four moves, and it is a loop because the last move changes the first:

```
thesis  ──directs──▶  making (experiments / analysis / data)  ──produces──▶  results
  ▲                                                              │
  └──────────────  repair (slots, boundaries, claims) ◀────feeds back──────┘
```

- **The thesis directs the making.** It says which questions are open, therefore which extractions and which analyses are worth running. Work that answers no open slot is not work; it is exploration that has not declared itself.
- **A slot** is one question the thesis owes an answer to, with its criterion written beside it.
- **The making produces the results.** Not only numbers: what could be estimated, what could not, what the design cannot answer at all.
- **The results feed back into the thesis.** A result closes a slot, opens a neighbouring one, or shows that a slot was posed wrongly. The thesis gets rewritten — slots filled, boundaries moved, claims narrowed.
- **The rewritten thesis directs the next round of making**, and the next round of work is different from the one that would have been run before.

The loop converges on a sharp thesis, not on a fixed result. Each pass should leave the thesis *smaller and more specific* — one more slot decided, one more boundary stated, one more claim no longer supportable. A pass that leaves it the same size has not fed back; a pass that makes it larger has found a new question, which is legitimate but must be recorded as such.

### 3.1 First entry: material exists, but nothing of it is in the workspace

The loop is usually entered on a project that is **already partly run** — analyses exist somewhere in earlier form, on an older build, under an older definition — and nothing of it is in the workspace yet. Do not start by rummaging for it.

**Ask the user first — but only for what the tree cannot answer.** Which of the existing material belongs in this paper, which is superseded, and which build it must be adapted to. The user knows what was tried and why it stopped; the filesystem is the place to look for everything else, and a question whose answer is a `ls` away is a question that hands the work back. **Ask about inclusion and supersession; do not ask about counts, paths or what a file contains.** does not. Then, and only then:

1. **Adapt.** Take the specific thing the user named, and re-express it against the current build — new database, new definition, new plotting — rather than carrying its old numbers across.
2. **Migrate.** Put the adapted module where the paper will need it (a runnable entry that reads the current build and writes its own output), not where it used to live.
3. **Declare.** Record in the workspace what was brought in, from what state, adapted how, and what was deliberately left behind. Material that is not declared is material a later reader will rediscover and trust.

Guessing here is expensive in a way that compounds: an unadapted module keeps producing numbers from the wrong build, and every later pass inherits them.

**Entering the project is §3.1 of this file; commissioning it is `src/template/docs/strategy-roleplay/01-supervisor.md` (the interface) and `skill.md` (method and expectations) — one copy shared by every instance.** This file states what a loop is and which work is next. How a project is entered, how the next work leaves the room as a fence, and how a returned result is read live in the role documents beside that file — `00-owner.md` (who wishes), `01-supervisor.md` (who commissions), `02-lead.md` (who answers the four questions, dispatches and collects), `03-executor.md` (who does the item). **These exist in one copy only, in `docs/strategy-roleplay/`, and are never copied into any `instances/<id>/`**; the venue vocabulary has one exit: `instances/<id>/docs/strategy-roleplay/executor-notes.md`.

**What comes next splits into two kinds of work, and only one of them is the loop.** A round can hold both, and a report that names only the second is describing a loop that cannot start.

| Kind | What it is | Test of whether it is this kind |
|---|---|---|
| **On-ramp** | work that makes the project capable of running the loop at all: the intent exists and is falsifiable; the corpus is thick enough to write against; raw results exist and can be strung into rows; a first draft exists to put a placeholder in; the map and the index agree with the disk; every number that will exist has one home | removing it makes the next round impossible, not merely thinner |
| **In-loop** | work the loop already can do: a run that turns a named hole into a row, the footing line that anchors that row, the placeholder in the draft that waits for it | removing it leaves the loop runnable and the stage unchanged |

**In-loop work is capped by unresolved on-ramp work, and the cap is not a preference.** A section waiting on a number that no pipeline can yet produce is not a section in progress; it is a placeholder whose owner is a missing pipe. When the on-ramp is empty — no intent, no corpus, no first draft, no raw results — there is no in-loop work to report: the round's product is the on-ramp, named item by item, with what each one unblocks.

So a report of next work answers three things before it lists anything: **how much of it is on-ramp, how much is in-loop, and which in-loop items it is deliberately deferring until the on-ramp closes.** An answer that reports only in-loop items on a project whose on-ramp is broken has misread the project's stage, however accurate its individual steps are.

### 3.2 Writing the first thesis: four inputs, four gates

The thesis is the loop's first act, and the only one that happens without results. It is written from four inputs, and skipping any of them produces a document that later has to be thrown away.

**The four inputs, in this order:**

1. **The user's priors.** Locked items (title, external commitments, venue) and standing preferences (what counts as real data, what kind of contribution is acceptable, what must never be substituted for a missing outcome). These are constraints, not material to weigh: a thesis that violates them is wrong however well argued.
2. **The corpus.** Read benchmarks for the **pain point, the significance and the contribution they claim against it**, not for the method: which sentences say the field is stuck, what reviews admit, which design gap keeps being repeated. A claim without a quoted pain point has no reason to exist; a contribution that no benchmark sentence sets up is a preference, not an argument.
3. **The prior work.** What an earlier phase or another author already assumed and found — hypotheses, results, narrative order. It enters the thesis as *prior*, labelled as such. Inheriting a claim is normal; presenting an inherited claim as a new discovery is the failure.
4. **The traces.** Earlier attempts and abandoned analyses. At this stage their value is not their numbers but what was already tried, so the thesis does not re-propose it.

**The four gates every thesis passes before the making starts:**

| Gate | Question it answers | Failure it catches |
|---|---|---|
| Pain point | two benchmark sentences, quoted, saying the field is stuck | a topic dressed as a problem |
| Provenance | every claim labelled: user / prior work / literature / ours | an inherited claim sold as a discovery |
| Falsifier | for every claim, the result that would kill it | an unfalsifiable story that survives any data |
| Branch | every open claim carries at least two arms keyed to result shapes | a thesis that can only be confirmed |

**And the loop's caveat:** the thesis is provisional by construction. The results may kill a claim, a question, or an entire framing. What survives is kept; what does not is recorded as *tested and failed*, never quietly deleted and never carried into the prose. The final thesis is the intersection of what was proposed and what the data could answer — which is why it is written before the work and rewritten after it.

### 3.3 Designing the work: the corpus decides what a method is

Before writing a single line of analysis, inventory **what models the benchmark work actually runs**. A method the corpus uses is the field's default and needs no defence; a method the corpus never uses needs an argument for why this question requires it. Designing in a vacuum produces analyses that are correct and unreadable to the audience the paper is aimed at.

**The baseline comes before the increment.** At first entry the workspace usually holds no reproducible version of the earlier work, only its traces. So the design has two ordered halves — **the baseline first, the increment second** — and the second is designed against the inventory the first produced:

Migrating the baseline is not copying it. Adapt it to the current build, put it where the paper needs it, and declare what was left behind (see §3.1). Then the increment is designed against the inventory, not against taste.
### 3.4 Literature search is a lookup first, a search second

Searching is expensive and repeatable, so it must be **idempotent**: the second time the same
gap appears, the answer should come from the shelf, not from the network.

**The shelf has one location, and the project's index is what names it.** Every project keeps its literature in a single directory recorded in the workspace index; what that directory is called is the project's own business (§3.4's next paragraph), so read the path from the index rather than assuming one. Whatever it holds:

| Item | What it is |
|---|---|
| the PDF | the file itself, named by citation key |
| the extraction | the text a PDF reader produced from it (`.txt` / `.md`), so the next reader does not re-extract |
| the index | one row per key: key · title · DOI/URL · pdf path · extraction path · status (`held` / `requested` / `not obtained`) |

If the project has no shelf yet, create it where the project's own layout leaves room for it, write that path into the index during the first search, and use it from then on. A shelf nobody can find is the same as no shelf.

**The paths named here are an instance's names, not the rule.** `workspace/10_corpus/` is what one project calls its shelf; another keeps `literature/`, a third keeps the PDFs inside the corpus index. The rule is that the shelf has one location written down where the next session will look, and that the index agrees with the directories. Reading the project's own map before searching is the difference between a lookup and a migration.

**A request row carries three fields, and they are not optional:**

| Field | What goes in it |
|---|---|
| **Title** | full title, venue, year — enough to identify the record without opening it |
| **URL** | **a filed copy outranks a link**: if the PDF is on the shelf, the locator is the path to it, and a URL is only needed for what is not filed. Otherwise a clickable link. A DOI is not a link: render it as `https://doi.org/<doi>`; with no DOI, use the publisher or repository page. **If the record cannot be located at all, the URL field carries the query you ran** (`https://api.crossref.org/works?query.title=…`, `https://scholar.google.com/scholar?q=…`), so "searched, found nothing" is reproducible by the next reader. A bare `10.x/y`, or an empty URL field, is a defect even when the rest of the row is right |
| **Purpose** | the one sentence saying what this paper would change in the design — which question it would answer, which model it would replace |

A paywall note with no link is not a request, it is a complaint. And a link that cannot be
verified is itself a finding: if the DOI resolves nowhere or carries a test prefix, say so
in the report rather than passing it along as if it were a record.

**Before searching, run the lookup.** By DOI, by title, by key. Three outcomes:

1. **Held, with extraction** — read the extraction, go to the methods section, quote it. No search, no download.
2. **Held, no extraction** — extract once, store the extraction next to the PDF, then read it. The extraction is a product, not a scratch file.
3. **Not held** — search. If it can be obtained, file it into the shelf with its key and update the index. If it cannot, it becomes a request row (title · URL · purpose) and the index status becomes `requested`, so the next session does not search for it again.

**Two things this lookup prevents.** Re-downloading a paper the project already owns, and re-reading a PDF a previous session already turned into text. Both look like diligence and are actually a sign that nobody kept the shelf.

**Held is not the same as trustworthy.** A shelf entry can be wrong: the DOI may not resolve, the file may be an excerpt rather than the paper, the method sentence may be truncated. Verify on first use — resolve the DOI, check the page count against the claims being made from it — and record the outcome in the shelf index:

| Status | Meaning | Consequence |
|---|---|---|
| `held` | resolves, complete enough for the claim drawn from it | usable as evidence |
| `held · method only` | resolvable as a method form but not as a finding (excerpt, no sample, no results) | may shape the design, may not be cited for a number |
| `held · unverified` | metadata or file fails verification | do not cite; a verification failure is itself a reason to search for a replacement |
| `requested` | identified, not yet obtained; the request row carries title · locator · purpose | blocks the rows that would cite it, and is listed as open |
| `not obtained` | searched, no obtainable copy | a result, not a gap: it is written once with the query and the date |

**The thesis says whether the stage owes new evidence.** Declare `needs_new: yes` or `no` when a pass starts. With `no`, a held-only pass is complete and cheap; with `yes`, a pass that returns only held has not done the work, and the shelf being adequate is not an answer — it is the reason to search outside it.

**The pass ends in the shelf, not in the reply.** A pass is done when the index on disk changes: new keys filed with their four assessments, or a refusal row naming what was queried and why nothing usable exists. A report that says "I looked for X and could not find it" while the shelf is unchanged has not run — the next session repeats it verbatim.

**A `needs_new: yes` pass has an acceptance test, not a vibe.** Either at least one new key is filed, or a refusal row exists that a reader could re-run (query, where, date, result). Neither present means the pass failed, whatever the prose says. Two further conditions: the new keys must be *for the open slot* the stage is about, not for the topic in general; and none of them may be a paper already on the shelf under another filename.

**One shelf, many manifests.** A large corpus can be split into sub-collections (`increment/`, `channel/`), each with its own manifest, provided the workspace index lists them. What is not allowed is a sub-collection whose existence is known only to the session that created it.

**The index must agree with the directories.** A shelf whose header says 86 while its folders
hold 90 has two truths, and the next reader will use the wrong one: counts are the cheapest check
that a pass actually touched disk, and a stale count is a defect the pass that noticed it must fix.

**A search that found nothing is a record too.** "Not in the shelf, searched by DOI and title, no open copy" is a row; the same gap searched three times across three sessions is a missing row.

### 3.5 What counts as a literature search

**A pass runs in one order: search, then read, then feed back.** Nothing is opened before it is filed under its key, nothing is fed back into the thesis before it is read and noted, and nothing is cited before it is fed back. The order matters because reversing it produces notes nobody can find and citations nobody has read.

**Reusing the shelf is not search work.** Reading a paper the project already owns costs nothing and produces nothing new; it is diligence, not coverage. So a literature pass reports two counts that are never added together:

| Count | Meaning | Cost |
|---|---|---|
| **held** | already in the shelf, reused | zero |
| **new** | found in this pass, assessed, and filed | the actual work |

A pass that returns only `held` has not searched. If the stage needs new evidence, the pass must produce new keys — and each one is assessed before it is filed.

**Four things are judged for every new candidate, and each gets a line in the search log:** whether the record is real (the identifier resolves and the file is the paper, not an excerpt); whether it carries a **premise** the thesis can use, as opposed to a topic it can mention; whether it brings an **axis or a neighbour** the shelf does not already hold, which is what the collision check needs; and which **slot** it serves, since a key that cannot be pointed at a slot is a `rejected` row with its reason.

**Every pass emits a counts line**, whether or not it found anything:

```
held 3 · new searched 41 · read 18 · kept 14 · placed 12 · dropped 23 · requested 4
```

`read` counts papers actually opened and noted; `kept` those filed; `placed` those pointed at an open
slot. For a chapter-thickening pass: `read` ≥ 12, `kept` ≥ 12, and `placed` no more than two short of
`kept`.

**A thicken pass has a floor, and the floor is set by what it feeds.** The pass is not there to
justify sentences already written; it is the input from which the thesis draws its axes and the
body draws its moves. Both are chosen from what has been seen: a pass that files four papers
yields four candidate moves, and the fifth-best move in the field stays invisible — so the thesis
reads as a small delta on a narrow shelf, and the writing has nothing to choose between.

**The floor is a gate, not a stopping rule: a dozen new keys before a pass may be called done, several dozen when the shelf allows.** For a pass
whose purpose is to thicken a chapter's back half, `kept` is at least 12 and `read` is at least 12;
when the field is crowded the honest target is 20–40. The number is not a quota for its own sake.
Two things follow from breadth, and both are what the thesis actually needs:

| What breadth buys | Why four papers cannot buy it |
|---|---|
| **The axes** | Axes are drawn from *premises*, and neighbouring premises are usually held by different groups. Twelve-plus papers make it likely that two independent groups tried the neighbouring premise, which is what a collision check needs — two neighbours held by different groups, so the difference sentence can be built against one of them. |
| **The moves in the prose** | Each paragraph action — what is missing, why the existing line keeps it, what we substitute, what it buys — is instantiated from a paper that did it. With four papers, four paragraphs sound the same. |

**The increment is made one paper at a time, and each one leaves a note.** The loop per paper:
locate (title plus arXiv id or DOI) → file into the shelf under its key → extract once with the
reader in flash mode → write the note: the readings that matter (a table row, a threshold, a commit)
and what it is used for — the section of the thesis it serves. Batches of three to five; the extraction of one batch
runs while the next is searched. A paper with no note has not been read; a note with no readings has
not been read either. This is the slow part of the pass, and it is the part that pays: the note is
what the thesis and the body quote from later.

**Breadth is not padding, because the floor is on `kept` and the judgement is on `fit`.** Every kept
key names the open slot it answers and the difference sentence it makes possible; a key that cannot be
pointed at a slot is a `rejected` row with its reason. A pass that files twenty keys and can place
eight has padded, and the counts line says so.

`needs_new: yes` with `new searched 0` is not a pass. It is a refusal, and a refusal needs a sentence: what was queried, where, and why nothing usable exists. The sentence goes in the log, not in the reply.

**The log is the product, not a diary.** One row per candidate, kept next to the shelf index:

```
key | title | venue | year | citations | why kept / why dropped | status
```

Rejected candidates stay in the log with the reason. A log that contains only the papers that were kept cannot be audited, and the next session repeats the same searches.

**Dedupe before filing.** New candidates are matched against the shelf by DOI and title first; a candidate already held is a `held` row, not a `new` row, and it is not re-downloaded.
**The instance's §3.6 and §3.7 come before this one.** Two of the loop's sections are numbered in the instance document rather than here: the one on turning scattered work into an increment, and the one on a search being procurement as well as a reading pass. They carry the venue's failure modes, so they are stated there; the numbering gap here is deliberate and says where to look.

### 3.8 Paving: what the search owes the stage that follows

**Paving** is what a search leaves behind for the work that comes after it: the difference sentence, the setting a number will be compared against, the page that will be quoted. It is the part of a literature pass that is not a citation.

Procurement (the instance's two sections on scattered work and on search-as-procurement, and §3.8 below) says a search must leave behind what the work will *run*. That is not
enough for a paper whose method comes from the literature rather than from a repository: the
thing to be run is a **specification**, and a specification that is not written down as a package
is rediscovered three sessions later, usually from the wrong paper.

**A paving pass delivers four things, and the pass is not finished until all four exist on disk** (§3.19.1 is the running checklist; it grows with each wish): the section's skeleton file with its five-key header and a placeholder wherever a number will land; the sign for whatever cannot yet be produced (`DECIDE` or `ABSENT`, with its owner); the difference sentence or sentences, quoting the neighbour's own wording, so the section can be written against it rather than around it; and the pinned asset the section's numbers will come from (`repo · commit · snapshot`), so that a later round can reproduce them instead of describing them.

**The skeleton is the unit of paving, and its minimum is small on purpose:**

`run.py` must execute far enough to prove the input path and the argument parsing work, then stop
at the unimplemented step. "It runs" is the difference between a plan and a plan that has touched
the data.

**The intent document's pass block grows one line, and only this line makes the paving auditable:**

```
paves: <slot> · asset <key> · prior <magnitude + design> · package <path> · unlocks <optional experiment>
```

A pass that files papers, appends `now claimable`, and omits `paves` has informed the next stage
but not equipped it. The test is mechanical: open the path in the `paves` line. If it is not
there, the paving did not happen, whatever the manifest says.

**Before the pass is called finished, five checks, all mechanical:**

| Check | Fails when |
|---|---|
| every filed paper carries a **slot tag** in the index (`rq1`, `rq2`, `none`) and the `none` rows say why they are filed | the next pass must re-read eleven summaries to learn which four are for the share |
| every paper a skeleton depends on is marked **`spec-asset`** and appears in that `SPEC.md`'s source line | a cited source and a running package are two different claims, and only one of them is checkable |
| every `paves` path opens **and the skeleton has been executed once**, with the exit line pasted into the pass block | an unexecuted stub is a plan; the first thing a later session discovers should not be a missing argument |
| the pass states **one thing it could not pave**, with the reason: missing paper, undecided instrument, unavailable outcome | a pass that paved everything has either paved nothing or not looked |
| the index's own counts match the directories on disk | a shelf whose header disagrees with its folders is a lookup that fails silently |

**A stale count is a defect, not a note.** Reporting "`README` still says 86" and moving on leaves
the first number a reader sees to be the wrong one; the same pass must fix it or say why it may not.

**A skeleton is a floor, not a ceiling.** When a pass implements the pipeline instead of stopping at
`NotImplementedError`, the obligations change rather than disappear:

**Optional experiments are ranked, not listed.** Each one carries: the slot it serves, the cost
in hours, the result that would make it uninteresting, and whether it can run before the main
result exists. An option that depends on the main result is a *follow-up*, not an option, and
belongs in a different column.
### 3.9 Sub-flows: they sit on the spine, they do not replace it

Real projects interrupt the spine constantly — a reproduction test, a documentation fix, a user decision, a literature look-up. These are **sub-flows**: entered from one point of the spine, exited back to the same point, with their own exit condition and their own artefacts. Three rules keep them from becoming the loop:

- **A sub-flow returns to where it started.** Its output is a decision, a rule, or a fixed file — then the spine resumes at the slot that was open.
- **A sub-flow never resets the spine's state.** The current thesis, the result table, the open slot are read before the sub-flow starts and are still there after it.
- **A sub-flow that changes a rule is written where the next session reads it** (a skill document, a case's materials), not only in the conversation.

### 3.10 Memory of the loop

The loop needs its state to outlive the conversation. Four files carry it, and each is small enough to rewrite in a pass: `data/<identifier>/loop_state.json` (what the layers hold now, each with the command that showed it), `loop_state.json` (the tree, plus `history`: feedback and rounds, append-only), the corpus index (what is on the shelf), and the draft itself (section, claim, readings, hash of the last revision, the round that touched it).

**The state file has one path and is repaired, not rewritten.** `data/<identifier>/loop_state.json` holds the facts a commissioning agent would otherwise re-derive every session, each with the command that produced it. Three rules keep it from drifting: **absent is created, never assumed** (the first commissioning turn builds it from the tree, the way an index is built); **the executor repairs it, the supervisor reads it** (a return updates the fields it changed and leaves the rest alone); **a disagreement is recorded, not resolved** (when the return says fourteen sections and the disk says thirteen, both readings and both commands are kept, because picking the convenient one starts the next round from a fact that was never true).

**The prose is part of the state, and it is tracked per section**, not as one document: section id · its claim · its readings · hash of the last revision · the round that last touched it. Prose written once and never revisited is not a report being iterated; it is a report that stopped. A section reopens for one of three reasons — a feedback item, a new reading, a collision found in a newly filed paper — and the reason is recorded in the same row.
### 3.11 When to stop

Not a deadline. Stop when a full pass changes no slot, opens no question, and invites no analysis. Two conditions make that reachable:

- **The pass itself must be cheap** — tables and scripts, not paragraphs — or the loop stops being run.
- **The pass must be recorded** — a slot that flips back is a warning that the thesis is still ambiguous, not progress; it is not a reason to stop.
- **A literature pass stops on saturation, having cleared the floor — never on the count alone.** Clear §3.5's floor first (a dozen kept, a dozen read), then stop when two consecutive batches of
  three to five papers add no new *premise* — no new axis, no new neighbour for the collision check,
  no new difference sentence. Stopping earlier because the shelf already holds enough to cite is the
  failure this floor exists to prevent; stopping later, once the batches repeat each other, buys
  nothing but notes nobody will quote.

If three passes each change a headline claim, the loop is telling you the effect is conditional. That is a result, and the paper should carry it rather than pick the pass whose narrative reads best.

**Independent items run at the same time, and independence is a property of the write set, not of the topic.** Two items may be dispatched together when they share **no writable file and no decision**: reading the same corpus or the same ledger is fine, writing the same section, the same table or the same state file is not. The state file has exactly one writer — whoever leads the round — because two sessions updating the same rows produce a file that agrees with neither of them, and the disagreement is invisible afterwards. Serialising costs one round; an inconsistent state costs every later round.

**A round serves the objective the owner stated, and where none was stated that absence is the first thing to fix.** The tree can say what exists; it cannot say what the work is for. So a commission quotes the objective it serves, and a round that cannot name one is a round that will optimise for whatever the files suggest — which is how a project acquires a direction nobody chose.

**The on-ramp is delivered in a bounded number of rounds, and every fence states how much of it is left.** Before a fence is written, the open on-ramp items are counted (`open on-ramp: n`), and the fence says which of them it will close. A fence that closes two items and opens three has not made progress, however much work it names; a fence whose checks already pass against the tree is not a round, it is a re-run of a finished one. **A round that leaves `n` unchanged is a defect to fix before any new item is added** — the usual cause is an item too broad to close in one pass, and the fix is to narrow it, not to split it into three.

**The intent is an on-ramp item while the on-ramp is open, and after it closes it moves only on divergence.** On a project that has not finished its first adaptation, building the intent — the claims, their falsifiers, the branches — is one of the items the fence closes, and it is checked like the others: a claim that no result could kill is an unfinished intent, not a finished one with a caveat. Once the on-ramp is closed, the intent document is **not** rewritten each round: it changes when a round's expected state contradicts a sentence it already contains, and then the sentence is corrected **before** the work is run, with the ledger row naming which sentence moved. Editing the intent to match whatever happened is how a thesis stops constraining anything.

### 3.12 A round: the unit of iteration

**A round is one pass over the whole report, not one stage of it.** The report is a single object from the first sentence of the introduction to the last row of the results table, and it is never frozen in halves. Treating "chapters 1–2" as finished and "chapters 3–5" as pending is the failure this section exists to prevent: it produces a document whose front half promises what the back half never measured, and whose back half answers questions the front half no longer asks.

**Every round takes the same five inputs**, in this order, and skipping one is why a round feels productive and leaves the report unchanged:

| Input | Where it comes from | What it does to the round |
|---|---|---|
| **the user's feedback, verbatim** | the last turn's corrections, questions, refusals | it is the round's first-class requirement: written down before anything else, item by item |
| **the tree and its open leaves** | `data/<identifier>/loop_state.json` (a leaf with `state != done` is an open item) | the state file says what each layer holds now; the ledger says which feedback items are still open and which layers a previous round deferred |
| **the literature increment** | a pass under §3.5, at the floor stated there | new premises enter the axes, and axes are what the prose is chosen from |
| **the draft as it stands** | the compiled body, with its hash | what changed is measured against it, not against memory |
| **whatever can be run** | the experiment queue | a reading, or an explicit "cannot run yet, because X" |

**A round can move five surfaces, and a surface it does not move is named.** Surfaces are what the round changes; the five inputs above are what it reads first — the same words appear in both lists, and that is the point: what you read is what you may move. Not every round can move all five — a round with no runnable experiment cannot produce a new reading — but the omission is written in the ledger, not left implicit:

1. **thesis** — claims, open slots, boundaries;
2. **skeleton** — one falsifiable sentence per section, plus the experiment that would refute it;
3. **literature** — keys filed, one note each, at the floor;
4. **prose** — the section the round is about, rewritten against the four inputs; a section is reopened whenever a new reading or a feedback item contradicts it;
5. **experiment** — what was run, or why nothing could be.

**Feedback items are closed one by one, and a refusal is a closure.** Each feedback item becomes a leaf (or a `history` entry) in `loop_state.json`, then marked `done` (with the artefact that shows it), `superseded` (with the reason the item no longer applies) or `refused` (with the reason, and what would change the answer). An item left blank is the one thing a round may not end with: an unanswered correction becomes a second correction two rounds later, usually angrier.

**A round ends with a diff, not a summary.** The record of it is four numbers and one sentence — sections touched · keys added · readings added · feedback items closed, and one sentence naming the claim that changed. "Reworked chapter 3" is not a diff; "chapter 3's cost claim moved from 'cheaper' to 'cheaper in count, not in silhouette fidelity', and the table that would show it is still empty" is. **The record and the report are two different things and both are required:** the record is this one ledger row, written for the next session; the report is the three movements of §3.13 — what changed, what state the project is now in, what is blocking — written for the owner. A round that files the row and sends no report leaves the owner with a diff they cannot read; a report with no row leaves the next session with prose it cannot check.

**Nothing is ever called final during the loop.** The word only appears in the last round, and what makes it the last round is §5, not seniority. A section written three rounds ago is reopened by exactly the same rule as one written today: a feedback item, a new reading, or a collision found in a newly filed paper.

**When this file is silent, the round decides and records the decision.** Silence has three different meanings and only one of them is an answer:

| Silence about | What to do | What is not allowed |
|---|---|---|
| **a fact** — a number nobody measured, a page nobody read | a sign with an owner and a blocker (§3.14) | estimating it, borrowing a neighbouring paper's protocol |
| **a choice** — which of two admissible shapes to take | decide, then write the decision and its reason into the round's ledger row | "the document does not say, so it cannot be determined" — a choice left undecided is a decision to let the next round re-open it |
| **a conflict** — two rules that cannot both hold | follow the one that protects the reader who has less time, and record the tension in the same row | quietly satisfying one and pretending the other does not apply |

The distinction matters because the two failures look identical in a report: a missing fact and an unmade decision both read as "not yet". They are not: the first is honest work left for someone with the instrument, the second is work nobody is doing.

### 3.13 Handoff, the report a round returns, and what the next round reads first

**A round starts by reading the five inputs of §3.12, in this order**, so that the diff at its end is measured against the files rather than against memory:

1. **`data/<identifier>/loop_state.json`** — what each layer holds now, each with the command that showed it; a field that has not been re-read is not a fact yet.
2. **`loop_state.json`, last `history` entry** — which round is open, which leaves are still not `done`, what was pruned and why.
3. **the thesis** — claims and open slots as they now stand, not as the last session remembered them.
4. **the draft's hash and section list** — so the diff at the end of this round is measured against the file, not from memory.
5. **the corpus index** — what is on the shelf with a note, and what the last pass said it could not obtain.

**The history has a fixed shape, and it is appended, never rewritten.** Two kinds of entries only:

```
{date, kind: add|prune|refocus|reweight|pause|resume|close|feedback,
 key, from, to, why}
```

**`kind:"feedback"`** carries the owner's words verbatim in `why` (one sentence, the original) and `key` (the leaf affected, or `root`). **`kind:"reweight"`'s `why` must carry the sentence "cutting observation: …"** — it is the only basis for the next round's cut.

An entry is written when something actually changes on the tree. **A change with no `history` entry did not happen**, whatever was said in the conversation.

**Two feedback items that contradict each other are not averaged.** Both are recorded, the newer one is applied, and the conflict is raised in one sentence with the evidence that would settle it. A silent average is the one outcome that loses information both ways.

**Rows that cannot be matched are not blended.** A comparison table assembled from runs under different settings is not a comparison; each row states its setting, and a row that cannot be matched is moved to its own table. This holds in both instances, whatever the field calls the setting.

**Each layer of that reading is a reading, not a recollection.** A layer is present or empty because a command showed it — a listing, a count, a grep — and the answer carries that command with the number it returned. A README that says where the outputs live is evidence about the README; the directory is evidence about the project. A position built from the first kind of evidence produces a next item that repairs a defect the project does not have, and the error is expensive precisely because the reasoning around it is sound.

**A round's end state is two lists, and the second one is written down.** What will exist — which rows, which anchors, which sections with which headers — and **what will deliberately not exist**: the quantity that stays unestimated, the section that stays a skeleton, the row whose anchor is `not seen`, the boundary that is stated as a boundary rather than explored. The second list is not an omission to be filled later; it is a decision, and a reader who is not told it will read its absence as work not yet done and start inventing a substitute. Stating only the first list is how a round ends with more claims than it can pay for.

**Choosing the next item is a reading of the position, not a preference.** Before any work is named, the project's position is stated as what exists and what is empty, layer by layer: the intent and whether it is falsifiable, the corpus and whether it can carry an argument, the data and what it cannot support, the baseline and whether it reproduced, the results table and which rows are still holes, the draft and whether it has a place for a number to land, the footing and whether any row is anchored. **The most suitable next item is the earliest on-ramp item whose absence blocks the most items behind it**; ties go to whichever choice makes a row possible. A list ordered by "what I feel like doing" and a list ordered this way look identical until the second round, when only one of them still has somewhere to put its numbers.

**The report that comes back is written for the owner, in three movements, and it is read once.** A round ends with a report whose reader is the person who commissioned it, not the executor: **what changed**, **what state the project is now in**, **what is blocking**, in that order, one movement per question. Inside a movement, one paragraph describes one layer — the table, the draft, the ledger — because a paragraph that carries a state and its three defects at once cannot be checked by the person reading it. Numbers stay; **implementation detail moves out of the prose**: a broken path in a sync script, an unescaped underscore that crashed the build, are findings, and findings belong in a short list after the prose, never inside the sentence that is supposed to say where the project stands. And a term the owner has not used before is either replaced or projected onto the disk in the same sentence ("signature" = the four-field marker on each table row), because a report that needs a glossary has already failed as a report.

**When the obstacle was this document, the round's product is a feed.** A defect found during an exam is fixed upstream in the same turn: the section that failed, then the rule file, then the case, and a memory only if the finding is about this machine. The delivery says which section was edited and what the next exam would now check — otherwise the same failure reappears under a new case number and looks like a new finding.

### 3.14 Placeholders: one for every missing piece, and a map that runs both ways

**A placeholder** — a named gap with an owner and what it blocks — is how a missing piece stays visible, and it works in both directions.** A gap with no placeholder is invisible to the next session; a placeholder with no section that needs it is a promise nobody collects. The report is the same object: every section is a road, every claim is a plot, and the two must reach each other. This section fixes the two rules that keep them reaching.

**Rule one — missing material is left empty, and the emptiness is named.** A number that has not been measured is not estimated, not "approximately", not taken from a neighbouring paper's protocol. It is a **placeholder**: an explicit, greppable, empty slot that says what will fill it and what it blocks.

| Missing thing | Placeholder form | What it must name |
|---|---|---|
| a run not yet done | `% PENDING(<id>): <what fills it> <- thesis §<x.y>` plus a visible `--` in the table cell | the run id or the command, and the section that cannot close without it |
| a reading not yet extracted | the same, with the key and the page | which paper, which table, which row |
| a decision the user has not made | `% DECIDE(<id>): <question> — options: a / b` | the two options and what each costs |
| material that cannot be obtained | `% ABSENT(<id>): <what> — searched <where>, <result>` | the query, the date, the outcome |

Three consequences, and they are not stylistic:

- **A placeholder is empty in the render.** If the compiled PDF shows a plausible number where a placeholder should be, the placeholder rule was violated — and a plausible number is the one defect a reader cannot detect.
- **A placeholder has an owner and a blocker.** `PENDING(run-r1)` without "blocks <section> and <section>" is a note, not a road: nobody knows what to run first.
- **A placeholder outlives the session.** It lives in the `.tex`, not in the conversation, so the next session greps `PENDING|DECIDE|ABSENT` and gets the whole work queue in one command.

**An empty place is filled by naming it, not by importing a rule.** When the measurement, the map or the threshold does not exist yet, the pass records the absence with an owner and a blocker; it does not reach into another project, another paper or another field for a plausible substitute. Importing a layout, a threshold or a definition is how a project quietly acquires a state it never had — and the acquisition is invisible afterwards, because the imported thing looks like a decision. The test is one question: where in this project was this number, path or rule written down before now? If the answer is "nowhere", it is a placeholder, not a finding.

**Rule two — every placeholder is marked at both ends.** Each section file carries a header comment naming the thesis section it implements, the claims it carries, and the artefacts it needs; each of those claims names its section and its placeholder back. The map is bidirectional, and a one-way road is a defect in one of the two files:

```latex
% SECTION 4.2 <- thesis §4.2 "count = faces x k^2"; claims C2, C3
% NEEDS: tab:count (k in 1,2,4 x 3 scenes) ; PENDING(run-k-sweep)
% HANDS OVER: <quantity> = <value> <unit> to <section> and <section>
```

A section with no such header is a section nobody can check against the plan; a thesis slot with no such header pointing at it is a slot that will be quietly dropped.

**Three greps, run before a round is called finished:**

```bash
# placeholders: the work queue, and nothing else
grep -rnE "% ?(PENDING|DECIDE|ABSENT)\(" <sections>/
# every section says which thesis slot it builds
grep -rn "^% SECTION" <sections>/
# every thesis claim has at least one section or one placeholder pointing back
grep -c "thesis §" <sections>/*.tex
```

**A count is a pointer, not a verdict**: these two greps tell you only how many sentences hang on a slot and how many back-references exist; **whether the right sentence hangs there must be seen by opening those lines** — the count right and the sentence wrong is dearer than no count at all.

Two failure modes this catches, both invisible in prose: **a claim with no placeholder** (the thesis promises a table no section will ever produce) and **a road with no plot** (a section that writes beautifully about something the thesis never claimed — the surplus that later has to be cut).

**Paving is what makes the next round cheap.** An unnamed hole gets filled with invention; a named hole gets filled with work — the queue in §3.15 is what turns that sentence into a command.

### 3.15 Placeholder and header grammar: one shape for every sign

A placeholder is only useful if its shape is fixed: one whose keys or order vary between files cannot be counted, and a count is the only thing that tells a round where its missing work is. §3.14 says a sign must exist. This section fixes **the shape of the sign**, so that any session — and any script — can read the whole road network without asking what this particular author meant.

**Material: one block, five lines, first five lines of the file, keys in this order.**

```
% SECTION: <n> <- thesis §<x.y>[-§<x.y>]
% CLAIM: <C-ids, semicolons> <one clause each>
% NEEDS: <artefact> ; <artefact> ; <placeholder-id>
% HANDS: <artefact> -> §<x.y>
% STATUS: draft | measured | blocked(<placeholder-id>)
```

The keys are fixed and the order is fixed. `SECTION` takes one arrow `<-`; `HANDS` takes one arrow `->`; nothing else in the file uses either arrow, so `grep '->'` is the handover list and `grep '<-'` is the mapping list. `STATUS` has exactly three values, and `blocked` names the placeholder that blocks it — a section is never "almost done".

**Signpost: one grammar, four fields, pipe-separated.**

```
% PENDING(<id>): <what will fill it> | owner: <run id / key + page / person> | blocks: §<x.y>, §<x.y> | since: <YYYY-MM-DD>
% DECIDE(<id>): <the question> | owner: <who decides> | blocks: §<x.y> | since: <YYYY-MM-DD>
% ABSENT(<id>): <what could not be obtained> | owner: <where it was searched> | blocks: §<x.y> | since: <YYYY-MM-DD>
```

Four fields, always the same four, always separated by ` | `. The `what` field is a noun phrase — not a sentence, not an apology, and **never a number**: a placeholder that contains a plausible number is a fabricated number wearing a sign, and the linter fails it.

**One namespace for ids.** `run-*` (an experiment), `read-*` (an extraction from a key), `decide-*` (a user decision), `absent-*` (unobtainable). Lowercase, hyphens, no dates inside the id. Ids are unique across the whole body — two sections may not both invent `run-r1`.

**One visible form per missing thing.** In a table: `--`. In prose: `\emph{[pending: <id>]}`. Nothing else: not "TBD", not "n/a", not a blank cell — a blank cell is indistinguishable from an editing error, and the whole point of the sign is that it is visible from the road.

**The linter is part of the round, not a nicety.** Ten checks, each one a defect a reader cannot see:

| # | Check | Why it fails the round |
|---|---|---|
| 1 | the five header keys, in order, on lines 1–5 | a section without them cannot be mapped to the thesis |
| 2 | every `SECTION` names a thesis § that exists | a header pointing at a section the thesis never posed |
| 3 | every `HANDS` target is a section that exists | a handover to nowhere |
| 4 | id namespace and uniqueness | two different holes with one name get filled once and reported twice |
| 5 | four fields, in order, in every sign | `awk -F'\|'` is the queue; a missing field drops a row silently |
| 6 | `what` contains no digits | a fabricated number hiding as a placeholder |
| 7 | `blocks` targets exist | a placeholder that blocks nothing is a note, not a placeholder |
| 8 | `STATUS: blocked(...)` ⇒ that id exists in the file | a section blocked by a hole nobody wrote down |
| 9 | `--` cells ≤ number of signs in the file | a bare dash that nobody owns |
| 10 | every visible marker `\emph{[pending: <id>]}` in the prose has a sign with that id | a marker with no sign is a hole nobody will fill, and it will be read as an editing slip |

**What this buys at the next round.** One command prints the whole work queue, sorted by what it blocks, with owners:

```bash
python3 report/final/assemble/lint_roads.py --queue
```

A session that starts with that table does not have to decide *what to do*; it decides only *whether to do it now*. That is the difference between a queue and a conversation: a session that has the queue decides when to run something, not what it should be.

### 3.16 Acceptance: what a finished report must look like, and what

**Acceptance is the third phase's gate** (§3.19.2): a report that has not passed the recheck checklist is not finished, however good its tables look. it is read against

A finished report is **complete as a document and incomplete as measurements** — those are compatible, and confusing them is why drafts are either padded or paralysed. Complete as a document means every section says something falsifiable and every missing number is a sign (§3.14); incomplete as measurements means the holes are real holes, named and owned, not smoothed over.

**Three tiers of properties, judged separately.** They fail for different reasons and are fixed by different work; collapsing them into one "is it good" judgement is how a report with fine prose and no argument passes.

**Tier 1 — countable, against the corpus's distribution.** Recomputed from the current build, never quoted from an older run; the reference is the sample set's `[min, max]`, and the median only says thick or thin.

| Feature | Where it is computed | Passing rule |
|---|---|---|
| pages · words · sections per chapter | the build, per chapter | inside the sample `[min, max]`; outside on the high side is allowed if the extra pages carry a table or a reading |
| citations per 1000 words | body text, per chapter | inside `[min, max]`; a chapter below the minimum has a citation promise it is not keeping |
| figures · tables per chapter | body text | a chapter claiming a comparison with no table is not thick, it is assertive |
| references (distinct keys) | bibliography | ≥ the sample minimum, and every key held with a note |
| words per paragraph | body text, per chapter | inside the corpus band; far **below** it means one-sentence paragraphs stitched into a list, far **above** means a wall of text |
| an exemption, when a band genuinely does not apply | `% EXEMPT: <feature> — <reason>` in the section file | the reason must name the structural difference (e.g. this chapter is prerequisites while the corpus's same-numbered chapter is methods), and the acceptance read reports `exempt`, never silently `in` |
| first-person density | body text | inside the corpus band; the band is per venue, not zero |
| sentence length (words per sentence) | body text, per chapter | inside the corpus band; far below it reads as a list, far above as a wall — both are the same defect of rhythm |
| connectives per 1000 words (however · therefore · consequently · moreover) | body text, per chapter | inside the corpus band; a chapter below it presents findings without relations, above it argues where it should report |

**Tier 2 — readable, and the windows are the six listed here, each read as a yes/no per section.** Each window is a yes/no per section, read by eye after the tier-1 numbers are in:

| Window | What "pass" looks like |
|---|---|
| claim before evidence | each section's first two sentences say what it will establish; the evidence follows |
| every claim anchored | each claim carries a reading (`value + setting`) or a sign (`PENDING(id)`) — never a bare adjective |
| collision stated | for every claim the report calls new, one sentence names the nearest work and the difference, quoted from that work |
| boundary stated | each chapter ends by saying where its claim stops holding |
| handover | each chapter ends by naming what the next one takes from it |
| one name per concept | a glossary-level check: no concept carries two names, no name carries two concepts |

**Tier 3 — perceptual, read blind.** One reader who has not seen the notes or this document reads the compiled PDF once, and answers five questions on a 1–5 scale. The blinding is the point: a reader who knows the placeholders exist will forgive them, and a reader who does not will report them as defects — which is exactly the reviewer's behaviour.

| # | Question | Fail signal |
|---|---|---|
| 1 | after one reading of the introduction, can you state the claim in one sentence? | the claim needs the method section to be understood |
| 2 | does each chapter answer the question its own title asks? | a chapter titled "results" that reports setup |
| 3 | does the related work read as an argument, or as a list? | paragraphs that could be reordered without loss |
| 4 | are the missing pieces visible as gaps, or discovered as surprises? | a reader who only learns at the end that the control run is missing |
| 5 | where would a reviewer write "compared to what?" | any claim of improvement with no row beside it |

Pass: no item at 1–2, and at least two at 4–5. A report that scores 3 everywhere is not accepted — it is the shape of a document nobody will argue with and nobody will cite.

**A criterion that cannot tell the two directions apart is not a criterion.** Every acceptance check must be able to fail: state what a passing report looks like *and* what a report with the defect looks like, and confirm the check answers "no" to the second. A window that any draft satisfies — "the introduction motivates the problem", "the results are discussed" — measures nothing and reads as a check while certifying everything. The test is one sentence: name the draft that would fail this, or delete the check.

**Read against what, exactly.** Three references, used for three different things, and never interchanged:

1. **the sample corpus** (the 11 theses in the project) — for *distributions and grammar*: how long a chapter is, how a section opens, how a contribution is phrased. Copied as shape, never as sentences.
2. **the venue's benchmark papers** — for *what a reviewer expects to see*: which table is mandatory, what an ablation must contain, what "state of the art" is allowed to mean this year.
3. **the shelf** — for *whether a sentence is true*: one key, one page, one reading. A sentence can match the corpus's grammar and still be false; the shelf is the only reference that can catch that.

**What the acceptance read may not do.** It may not fail a report for having signs — a report with ten named holes and a clear queue is *better* than one with ten invented numbers. It may not pass a report because the prose is fluent. It may not compare against a paper that solved a different problem; the nearest neighbour in the collision check is the only fair comparator, and it is named in the sentence.

### 3.17 Sentences, and the spine that answers the two questions

A report is not judged sentence by sentence in isolation, but a report fails sentence by sentence first. Six sentence types carry everything; a sentence that is none of them is either decoration or a claim in disguise, and both cost the reader.

| Type | Required shape | Fails when | Belongs |
|---|---|---|---|
| **claim** | "X is Y, because Z" — falsifiable, no hedge | it survives any data ("plays an important role") | section openers, chapter openings |
| **evidence** | "value · setting · source" — a number is never alone | the setting is missing, so nobody can compare | after a claim, in tables' company |
| **difference** | "A does P; we do P but Q" — the neighbour's own words first | it summarises the neighbour instead of quoting it | where the report calls something new |
| **boundary** | "this holds for W; outside W it does not, because V" | it is an apology rather than a limit | chapter ends |
| **handover** | "chapter N takes X from here" | it names a chapter that does not use X | chapter ends |
| **sign** | `PENDING(id) · owner · blocks` (§3.15) | it is an apology for missing work | wherever work is missing |

**What goes into a section file, and in what order.** The six types above are the language; this is the shape a section takes when the language is used. A section that cannot be read top to bottom in this order is either missing a move or has one twice.

| # | Slot | What is written | Rule |
|---|---|---|---|
| 1 | **header** | the five keys of §3.15, on lines 1–5 | written before the prose; a section without it has no owner for its gaps |
| 2 | **claim** | one paragraph: what this section establishes, and what would refute it | first sentence falsifiable; no "we then describe" |
| 3 | **evidence** | the readings that carry the claim, each with value · setting · source | a number without a setting is deleted, not footnoted |
| 4 | **difference** | one sentence naming the nearest work, quoted, and what changes | only where the report calls something new; if it is not new, cut the claim instead |
| 5 | **boundary** | where this holds, where it stops, and why | last paragraph of the section, not a footnote |
| 6 | **handover** | what the next section takes from this one, by name | one sentence; if nothing is taken, the section does not belong here |
| 7 | **signs** | `PENDING(id)` inline for anything not measured, with the table cell left `--` | no estimate, no "approximately", no borrowed protocol |

**Every requirement carries the cost of its absence, and the cost is paid by the next round.** A rule stated without that cost is decoration, and a round that follows it knows the shape but not the reason — which is why rules copied this way collapse the moment the project differs from the one they were copied from. Three consequences are worth naming, because they are what makes the loop iterate rather than restart:

| If this is missing | Next round pays | Where it shows |
|---|---|---|
| the round's diff (four numbers, one sentence) | re-reads the whole draft to find out what changed | the ledger row, or the absence of it |
| the named layer that was skipped | assumes the skipped layer is done, and builds on it | the same row's `layers moved` column |
| a sign with owner and blocker | either plots a number it does not have, or forgets the gap entirely | the queue (`lint_roads.py --queue`) |

**This file is written as rules with section numbers; that is the wrong shape for an account of the work.** The numbers exist so a rule can be found again, not so it can be quoted instead of applied. When the work is explained — in a defence, in a hand-over, in the introduction of the paper itself — copy what the rules require, never their form: a paragraph of this file turned into a paragraph of speech is a paragraph about the file. The same holds for the slots above: they are named here so that a section can be checked, not so that a sentence about the section can recite them.

**A report is a line, not a set of headings.** The reader is not asking what the report contains; the reader is asking where the project stands and what that means for what happens next. So the sections are not parallel boxes — each one takes the project from a state to the next state, and the account has to make that movement visible: this was open, here is what closed it, this is what it left open. A reader who finishes a section and cannot say *what stage the project is now in, what that stage means — what it has established, what it has made possible, what it has closed off — and therefore what must come next* has been given a table of contents with paragraphs under it. The stage is a fact (the control run has not happened); its meaning is the claim that fact carries in the argument (so every number about cost is still an estimate, and no section may present one as measured). A report that states stages without their meaning has told the reader where it is without telling them what it means.

**The three opening moves are the line's beginning, and everything after continues it.** The problem (whose it is, quoted, with a reading that shows how much it costs), why it matters (what becomes possible that was not), and what this work contributes (who can do what now, at what price) are not three sections to be filled — they are the first three moves of one argument, and each later section is that same argument continuing under a heavier burden of evidence. A section that could be moved anywhere else in the document without changing how it reads is not on the line; it is an appendix that happens to be bound in the middle.

**Every section consumes what the previous one produced.** The previous section's leftover — a premise it had to assume, an open slot, a cost it could only name — is this section's input; the section that does not consume anything is either misplaced or unnecessary. This is why the order is not free: the order is the argument.

**A sequence of headings written as prose is still a list.** "First, the ledger row; second, the named layer; third, the five carriers; fourth, what must not be established" is the document's own table of contents, recited — the paragraphs could be reordered without changing the reading, which is the test: **swap any two paragraphs; if the passage still reads the same, it was a list.** The repair is not shorter sentences but a chain: each paragraph opens by consuming the previous one's result ("so the row is there, and the row is what makes the next question askable"), and closes by leaving the next paragraph something it must answer. Enumerating is what a report does when it has nothing to say about the relations between its parts. The swap test alone is not enough, because a writer with no document at all can satisfy it: the chain must also be checkable against the stations — swap two paragraphs and the sentence that consumes the previous station's leftover stops making sense, which is a defect that fluent prose cannot hide.

**Talking about the work, rather than about this file.** The rule may be named once, in parentheses, and only after the thing it governs has been said — and the test is countable rather than a matter of taste: **in any paragraph that explains the work, the subject of its sentences is the work, not this file.** "The control run has not happened, so the row is a sign with an owner and three sections waiting on it" is a sentence about the work; "§3.14 requires a sign instead of an estimate" is a sentence about the document, and a reader who has never opened the document learns nothing from it. A paragraph with two or more sentences beginning "this file", "§", or "the rule" is a paragraph about the manual: delete it and say what the work is instead. The same test the reader applies: say it aloud to a colleague; if they have to ask what a section number is, it was a citation, not an account.

**Four things the section owes before it can be called written.** The slots above say what the section contains; these four say what its non-prose parts must do for the reader, and a section with every slot filled and none of these four is finished in shape and unfinished in obligation:

- **the table owes its setting** — dataset, split, resolution, hardware, in the caption and again in each row. Without it a reader subtracts two rows produced under different settings and reports the difference as the method's effect.
- **the equation owes its symbols** — each defined in the sentence that introduces it, units stated where they can be checked. Without it a reader re-derives the expression under the assumptions of the paper we borrowed it from.
- **the figure owes a way to be wrong** — the caption says what to look at and what would look wrong. Without it the picture is taken as support for a claim it was never about.
- **the citation owes its sentence** — attached to the sentence it supports, which would be false without it. Without it the reference list reads as a survey and the sentence as our own finding.

A section that skips one of these is not "almost done": the reader's error is already determined, and it will be made in the next round rather than this one.

**The section is written in this order and read in another.** Work proceeds claim → evidence → difference → boundary → handover, because that is the order in which each can be checked; the reader encounters claim → difference → evidence, because that is the order in which a claim can be doubted. The file keeps both: the slots are present in the first order, the sentences inside them are written for the second.

**One claim per paragraph, and the claim comes first.** A paragraph whose topic sentence is a citation, or a definition, or a date, has no claim; it is a note that will be cut in revision.

**The chapter's five moves are borrowed from the corpus; the corpus's victory story is not.** The sample chapters agree on five moves: reopen the field in one sentence (never "as described in chapter 1"), name the single obstacle the chapter attacks, put the assertion before the evidence, enumerate conditions one variable per item, and close on a boundary that points at the next chapter's question. Copy the moves — they are the genre working — and never copy the outcome sentence: a sample that reports a method "revolutionising" a field is telling its own result, not a shape available to ours. The moves are borrowed for what they let a reader do; the verdict is earned by our own readings and signs.

**The abstract is a projection of the written body, not a promise about it.** Every sentence in it must be recoverable from a section that exists: the claim from the introduction, the price from the results table, the boundary from a chapter end, the next step from the queue. An abstract written before those sections exist is a plan; when the body moves, the abstract is re-derived rather than edited, because an edited abstract drifts into claiming what no section carries.

**The three questions every version of the introduction has to answer, and where each is answered.** These are the paper's questions, not the exam's four (§3.13); the exam asks how the project stands, the introduction asks what the paper claims. They are bound: a problem with no significance is a curiosity, a significance with no contribution is a wish, and a contribution with no problem is a feature looking for a reason.

| Question | Answered by | What makes the answer fail |
|---|---|---|
| **What is the pain point?** | one quoted sentence from a benchmark paper (or two, agreeing), plus one reading that shows the pain is quantitative | a topic dressed as a problem; a pain point that only the author feels |
| **Why does it matter?** | the capability that exists after the work and does not exist before, with its cost named in the same breath | a benefit that any method in the field already gives; a benefit with no cost stated, which reads as marketing |
| **What does this work contribute, under that problem and that significance?** | one sentence naming the change that a reader can perceive — who can do what, at which moment, that they could not do before — with the cost of that change in the same sentence; every clause of it traceable to a reading or a sign | a contribution stated as a property of the method ("we introduce X") rather than as a difference in what someone can do; a contribution that would survive the work being wrong; a contribution whose cost appears only in the limitations |

All three answers live in the introduction, and all three are **re-answered** at the end: the conclusion says the same three things in the past tense, with readings attached. A conclusion that introduces a new benefit is a second introduction, not a conclusion.

**The spine: seven stations, and every chapter sits on one.** The order is the reader's, not the worker's (§2–§3), but the dependency is the worker's: each station consumes what the previous one produced.

```
1 pain point (quoted)  ->  2 why the existing routes cannot fix it  ->  3 what premise we change
   ->  4 what that premise buys (count and appearance as inputs)  ->  5 what it costs, measured
   ->  6 where it stops holding  ->  7 what the next worker should run first
```

| Station | Lives in | Carries | Proven by |
|---|---|---|---|
| 1 pain point | introduction | the quoted sentence + one reading | the shelf, one page |
| 2 routes cannot | related work | one line per route, each ending on what it cannot give | the four-column grid |
| 3 premise changed | method | the substitution, stated once | position/count/colour formulas |
| 4 what it buys | method + results | budget before the run, re-texture without retraining | the two knobs, one table |
| 5 what it costs | results | fidelity, bytes, and where the loss sits | the band table |
| 6 where it stops | results + conclusion | template dependence, single scoring source | the failure cases |
| 7 what to run next | the signs and the queue | three runs in order, with owners | the instance's queue command |

**Paving shows itself as a hand-over, not as a promise.** The test is behavioural, and it takes five minutes: hand a reader the compiled PDF and the queue, and ask them to state **the next three runs in order, with owners, and which section each unblocks**. If they can, the report is paved, whatever its prose is like. If they cannot — but the prose still reads well — the document is a report about work, not a report that lets work continue.

**And that is how the narrative becomes clear rather than decorative.** Each section's last sentence must open the next section's first question (§3.19.2 C). Stations 1 and 2 make the pain point *someone else's quoted problem*; stations 3 and 4 make the contribution *the answer to that problem and nothing else*; station 5 makes the cost *the price of that answer*, not a caveat bolted on; station 6 keeps the claim from overreaching; station 7 hands the reader the queue. A reader who can retell those five moves in one breath has understood the paper; a reader who cannot was given sentences, not a spine.

**The spine is verified as a chain, not asserted as a list.** Each station is only present if the body contains the sentence that carries it, in the chapter that owns it, and that sentence consumes what the previous station produced. A mapping table written from the plan is a hypothesis; the same table written after locating each carrier sentence is a status. Where a station has no carrier yet, it is a sign (§3.14), not a silent gap.

### 3.18 When the report is done

The conditions are the ones in §5, applied to the whole document rather than to a claim; they are not repeated here, because a second copy of a list is a second number to keep in sync (this file has already had to fix "five exit conditions" against a list of six).

Two conditions are specific to a multi-round report and are not in §5:

| Condition | Check |
|---|---|
| every placeholder is either filled or listed as a blocker | `grep -rE "(PENDING\|DECIDE\|ABSENT)\\("` returns only slots the ledger names as open, and each names its owner |
| every section is attached to a thesis slot, and every slot to a section | the `% SECTION` headers and the thesis's slot list are the same set, both directions (§3.14) |

A section that fails one of these is not "done pending polish" — it is open, and the next round's ledger says so.

### 3.19 Three phases of every round: pave, work, recheck

**A round is not one activity.** It is three, in this order, each with its own product: **paving** leaves a road (a skeleton, a `run.py` that runs up to the unimplemented point, placeholders carrying `% PENDING`), **work** leaves a reading, **recheck** leaves a **maintained, placed** artefact (checked, aligned, fit for the report). **The thesis is the start, the work is the core, the recheck is maintenance and settling** — all three belong to the loop, and miss one and the next round starts from scratch.

**Two qualifiers that get dropped.**

1. **Paving includes maintenance, debugging and debunking.** It is not "pave once before starting", but every time a paper enters the library, code lands, or a citation changes, someone goes back and levels the road: is the paper really in the library, is its conclusion still bound to the same thesis site, has someone else's implementation quietly substituted the mechanism we claim. **This work produces no new readings, which is exactly why it is skipped first; skip it once and every round after runs on a crooked road.**
2. **Paving faces the whole document, including the sections already written.** Introduction and Related are the two sections written first and rechecked last: their citations must equally be in the library, equally bound to a site, and their background must equally set up the next chapter's motive. **"It is already written" is not an exemption — the opposite: the key they set is what every section after follows.**

**The wish decides which rows are live.** The list is not all done each round but **taken as a subset by wish type**; change the wish and the subset changes — which is exactly why the list must be complete:

| Wish type | Rows live now | Not live, but do not delete (the next type will use them) |
|---|---|---|
| **paving type** (the current one) | all of §3.19.1 + §3.19.2 A (papers and assets) | rows like "boundary reading" under result truthfulness can wait |
| **reproduction type** | §3.19.2 A + all of B | "handover" under C, landing, can wait |
| **writing type** | all of §3.19.2 C + "recheck of written sections" in §3.19.1 | asset download can wait |

**The lists below are open.** They are **working lists**, and they keep growing with each wish: the current wish is paving, so the list is long; the next wish is reproduction, and other rows will appear. **Only as the rows fill out can one round of bottom-layer work be complete, robust and grounded. One rule governs additions: a new row says which wish type it serves.**

#### 3.19.0b The thesis and the work have lists too (the **start** and **core** segments, also open tables)

**The thesis (start) — a three-line entry check, and missing one means everything after is rewritten:**

| Check | Criterion | Failure shape |
|---|---|---|
| the pain point is citable | one quotable sentence (which paper, which page) | a "pain point" I summarised myself |
| the significance is measurable | one sentence landing on a measurable quantity (volume / duration / editability) | "important", "promising" |
| each contribution matches the trio | every contribution points at a column of the main table or at a section | contributions that match no column |

**The work (core) — six lines, and missing one means the round did not run:**

| Check | Criterion | Failure shape |
|---|---|---|
| one command | rerunnable from a clean environment, input paths hard-coded in config | parameters typed by hand, paths on the command line |
| one variable per change | differences from the reference implementation listed item by item, one changed at a time | six variables changed together, and a red run names nobody |
| readings land on disk | `outputs/` holds json / csv / figures, and every number cited in the body points at file and line | terminal output only |
| conditions from one source | dataset, split, metric and budget written in one place | two sections each stating their own setting |
| failures logged too | interruptions, timeouts and crashes all enter `results.jsonl` | only successes recorded |
| stop condition | "under what condition this round stops" is written first (cost, time, boundary) | it stops when the money runs out |
| cost discipline | **smoke first** (run the smallest command, then scale) / budget hard-coded per item (steps · elapsed · devices) / **never wait blind**: one command (including `sleep`) may not exceed 300 seconds, once it runs you keep reading, **anything that looks deadlocked or diverging is stopped at once**, no "let us wait a little longer" / parallel only for independent items, one polling point / **`stop` at the end with verified output** | going straight to full scale; discovering at minute 40 what died at minute 2; the machine still billing after the run |

**A machine nobody is watching is money burning.** The dearest error in a round is not one wrong number, it is **starting a command and going off to do something else**: it may be stuck in the `dataloader`, it may be NaN by step three, it may hold the device while computing nothing. **Those three look identical when nobody reads the log**, and the only difference between them is whether anyone stops it early.

So "monitoring" is not a good habit but **this layer's hard discipline**: **one command (including `sleep`) runs no longer than 300 seconds**; longer and you cut it into blocks, each returning one reading; **progress stalled, loss diverging, memory climbing, log no longer growing — stop first, then investigate**. **One stop costs a minute; one burnt budget costs a whole round.**

#### 3.19.1 Paving checklist (paving: make the next round runnable) — **this table keeps growing**; a new row states which wish type it serves (paving / reproduction / writing)

**Read this table against the tree, one row at a time**: each row is a thing the next round must be able to do without asking anything, and a row whose criterion cannot be shown on disk is a row not done.

| Action | Criterion | Failure shape |
|---|---|---|
| the paper is in the library | the PDF is under `workspace/literature/`, `references.bib` has the key, the page is retrievable | citing a paper never downloaded, a key pointing at nothing |
| code downloaded so it can be evaluated | the repo to be evaluated is in the workspace and runs one command | "download it when needed" |
| conclusions bound to thesis sites | each paper's conclusion hangs on a thesis section node (`% PENDING: <what> ← thesis X.Y`) | papers and claims each saying their own thing |
| skeleton + `run.py` | runs up to the unimplemented point and stops, the exit line pasted into the pass block | a README with no entry point |
| the `paves:` line | all five fields `slot · asset · prior · package · unlocks`, with the `package` path openable | a road reported whose path does not exist |
| **paving the recheck of written sections** | every background sentence in Introduction / Related points at a paper in the library, and that paper says the same thing | written, therefore unchecked |
| **the conclusion–site two-way table** | each paper's conclusion → which thesis site; each thesis site → which papers support it; **a row empty on both sides is a dead end** | one direction only, the other end dangling |
| **the debunking record** | the moment "another mechanism passing under our name" is found, append one row to `## feedback` (action, reading, correct practice) | said aloud this round, back again next round |

#### 3.19.2 Recheck checklist (recheck: maintain, debug, debunk) — **this table grows whenever the wish changes**; the more rows, the more one bottom-layer round can actually check

**A. Papers and assets**

| Action | Criterion | Failure shape |
|---|---|---|
| existence | every citation opens its PDF and turns to that page | a key with no text |
| binding agreement | the paper's sentence and the body's sentence say the same thing | the quote says A, the body uses it as B |
| library agrees with the index | the search log's row count, the library's file count and the bib's key count agree | three places, three numbers |

**B. Truthfulness of results**

| Action | Criterion | Failure shape |
|---|---|---|
| the action is a real action | the result comes from `outputs/` produced by this repo's command, and the command reruns | **another mechanism passing under our name** (SDEdit read as score distillation) |
| figures agree with the body | every annotation in a figure has a synonymous sentence in the body, and the reverse | figures say good, body says bad |
| narrative logic | the result's direction, magnitude and conditions sit in the same convention as the claim | comparing across changed conditions |
| robustness | at least one boundary (views, seeds, budget) has a reading | a single point taken as the conclusion |
| detail in the body | every choice affecting reproduction is written | key parameters only in code |

**C. Landing in the report**

| Action | Criterion | Failure shape |
|---|---|---|
| the repository is tidy | someone else can run the same number from the README | three v1/v2/final copies in the directory |
| the README points at assets | every figure and table says which command produced it and which path it lands in | a README about motivation |
| the README carries a reportable conclusion | one line of conclusion + conditions + source | results with no conclusion |
| section handover | each section's last sentence raises the next section's first question (one handover line); **one or two sentences of transition, no restating what has been said**; the Introduction's last paragraph must read as the research motive | sections as islands, joined by "in summary" |
| the read | **it reads smoothly and does not lose pace** (short sentences, one thing per paragraph), and afterwards you can state the pain point, the significance and the contribution | two pages in and still unclear what is being solved; fluent but the claim does not stick |
| **the README states the section it feeds and the approach** | each package README says "which section of the report / how that passage is written (what comes first, what after) / what to watch (traps, conditions, things not to say)" | a README about how to run the code |

**D. Meta-rules for the recheck itself**

| Item | Rule |
|---|---|
| who | **the lead** rechecks and writes the conclusion into the dispatch; the executor does not edit the state file and does not conclude on the lead's behalf |
| when | ① new assets entering (papers / code) ② a citation or number in the body changed ③ before each round closes ④ **before writing a section that is "written first"**, such as the Introduction |
| product | one line of reading: how many items checked, how many closed, who owns each unclosed one; **unclosed items must be named**, no "basically fine" |
| found means written back | one of three places: the literature library or index, that package's README, or that sentence of the body; **report without changing and it returns unchanged next round** |
| readings enter the state | the recheck conclusion goes into `## EXIT-READINGS` of `data/<identifier>/loop_state.json` (how many checked, how many closed), and the overturned old conclusion is appended to `## feedback`; **a recheck written into a conversation did not happen** |

#### 3.19.3 The interfaces between the three segments

- **Paving's product is work's input**: a work item must point at a road already paved (the `paves:` line); if it cannot, pave first.
- **Work's product is recheck's input**: the recheck reruns no experiment, it only asks "did the reading come from there, and is it written in the right place".
- **`id` is the first interface**: every layer's hand-over starts with `id: <identifier>`, and the context and wish are located under `data/<id>/` by that id. **Losing the id loses "which wish this is"** — with several in flight, no product can be attributed, however good it looks.
- **Recheck's product is the next round's foundation**: each inconsistency found is written back to one of three places — the library or index, that package's README, or that sentence of the body. **Report without changing and it returns in the same shape next round.**

## 4 What this changes about the thesis document

The thesis is written **before** the results exist, so it is not a plan the results obey; it is the **space of stories the results will choose among**. That is why it is written as branches, not as a claim:

- each open slot carries the two or three forms its sentence can take, keyed to the result shape that selects it; choosing a branch costs one sentence per slot, and if a branch forces the Introduction to be rewritten, the branch was drawn too late;
- the thesis records, for each slot, whether it was written **before** or **after** the result arrived — the same disclosure the paper owes its reader.
- each chapter that will run code names the pinned asset (`repo · commit · snapshot path`) and the order the work happens in — control row, then the increment on the same protocol, then the cost against both — so a later pass neither re-clones nor re-derives it.

A thesis that reads as a single confident story before the data exist is not more committed; it is unrevised.

## 5 Exit

**These seven are the read and narrative criteria, not statistical ones.** Word count, citation density and citation count are **gates**: falling short means not handed over, and meeting them **does not mean passing**. Passing is judged by **whether a reader walking the pages stops** — whether what each sentence states can be pointed at a row of results, whether that sentence has a neighbour to be compared with, whether the Introduction promises something the results cannot carry (**a citation that exists only to decorate a sentence is itself a defect**, not a bonus). **The two easiest fake passes**: many citations, all decoration; enough pages, every section restating someone else's conclusion.

- Every headline claim traces to a result row and to an anchor, or is marked `not seen`.
- The paper states which analyses were pre-specified.
- The Introduction contains no claim the results cannot carry, and no citation that exists only to decorate a sentence the results would not support.
- The two checks of §1, run on this paper's own draft, classify it the same way they classify the corpus described there.
- The thesis has a pass log, and the last pass changed nothing.
- Every `code-asset` and `baseline` has a pin and a workspace entry that runs without the upstream repository's layout; every unobtainable or unbuildable candidate is a `rejected` row with its reason.
- **Every headline claim has a neighbour, or says why it has none.** The claim's row carries `aligned-on:` (dataset · split · metric · budget) and the neighbour's own row; a claim whose neighbour is missing is written `not comparable — <what differs>` **in the draft**, not dropped. **The other conditions can be satisfied by a paper comparing itself to itself; this one cannot.**

### Citation admission: a number passes four gates before it enters the body (revision of 2026-11-16)

**This section governs "may it be cited", not "is the result good".** All four gates pass before it enters the body; miss any one and that number can only appear in the draft as `not seen` or `not comparable`.

**Gate one: input class.** The input behind every number states whether it is `real` (a capture / a dataset) / `synthetic` (programmatic, a synthetic benchmark, a self-made scene) / `derived` (processed from the first two). **A number with no class is treated as `synthetic`.**
**Gate two: the producing command.** One command rerunnable from a clean environment; parameters typed by hand, an item left out, or a reliance on "it was run last time" all count as non-rerunnable. It must be in `manifest.json`.
**Gate three: `path:line`.** Every number cited in the body points at a line of a file on disk; one that cannot is an **unowned number** and is demoted on the spot to uncitable.
**Gate four: the impostor check.** Whether this number came out of the mechanism it claims: is `runs/` there, does `sha256_12` match, has a cheaper path been substituted. **A swapped mechanism is fabrication: it may not enter the body, and it must be written into the feedback.**

**A synthetic input has one fixed place: the control-experiment column, with `not comparable` in the same sentence.**
It may not serve as main evidence. The cell it occupies in the main table reads `not comparable — <what differs>` (input class / steps / resolution / view set), and "put the number in and note it beside" is not allowed. The same rule: a control-experiment leaf's weight may not exceed the main-line leaf it supports — otherwise the tree props real conclusions with synthetic material.

**A retired product needs a written declaration, and citations of it in the body must be zero.**
Write `DEPRECATED-<date>.md` in the product directory: which files, why retired, why kept (as evidence that "it once ran this way"), and the restore condition (which input, then which protocol). Every place in the body that cited it returns to a placeholder; it may not be quietly left in.

**The only progress convention is "citable rows", not "planned coverage".**
A main table has some number of rows and columns, and some number of cells can enter the body — that numerator is the progress. Reporting "dispatched / returned / paved" as a percentage to the owner treats activity as achievement; **the tree's weighted progress exists to schedule work and may not be reported as achievement.**
One self-check: **"if the deadline were now, how many numbers would land in the body?"** Unable to give a cell count means you are fooling yourself.

### How comparison writing lands: take the skeleton, insert your claims, then check sentence by sentence

**"Write against the samples" is not reading a model text once and writing by feel.** Four steps, and missing one produces "prose that looks like a paper":

1. **Take the criteria**: the table in the samples directory's `README` (criteria / metadata) is this venue's **passing shape** (which blocks each section needs, the order of blocks, which kind of sentence belongs in which position). **Copy that table to the head of the section first**, and tick each cell as you write.
2. **Take the skeleton**: pick one sample of the same chapter type and write its **paragraph functions** one line each ("this paragraph gives the conclusion first → this one gives the comparison → this one admits the boundary"). **Take the function, never the sentences.**
3. **Insert claims**: put your headline claim into the corresponding cell; **a claim that does not fit is either cut, or the section says why it needs a new cell** (a new cell carries a reason; never add one silently).
4. **Check sentence by sentence**: after each paragraph, look at the sample's paragraph in the same position — **what is that sentence giving (a number, a condition, a boundary, a turn)**; is yours giving the same thing. **A mismatch is a misalignment**, and it has nothing to do with word count or citation count.

**The acceptance criterion is §5's seven lines, not word count or citation density.** The gates (word count / citation density / line-level pointing) are in `00_pre_delivery.md` — **pass the gates first, then judge against §5**; reversed, you hand over a draft with "pretty metrics and nothing right".

### The standard for a first draft: **basically acceptable**, not "just get something down"

**Every draft that lands is "a draft written to this standard", not a placeholder.** All three must hold at once:

1. **The comparison reaches a basic level**: structure, paragraph function and what each sentence carries match the sample chapter (the four steps above). **"Prose that looks like a paper" does not pass** — it has no checkable shape.
2. **Max effort, no "later" left in the text**: every paragraph is the best you can give right now; **where you cannot write it, write `% PENDING: <what is missing> ← <anchor>` rather than covering it with a vague sentence**.
3. **Do not overwork it; leave room for the revision pass**: **the reader (the owner) will later rewrite to remove AI traces and adjust the thesis before the next revision** — so **do not change structure for "prettier", add rhetoric, or pile up transitions**; that burns the revision room in advance. **Leave blank where it should be blank, and do not spare one sentence where it must be clear.**

**Both of these fail**: **writing carelessly** (which means the round produced nothing) and **over-polishing** (which uses up the room, so the revision can only throw it away). One criterion: **delete any sentence — does the reader know one thing less?** If not, delete it.

### Choosing what to keep: cut to what can be proved, then talk about completeness

**Criterion one: which claim does it support.** Write the corresponding claim after each branch; one that cannot be written is deleted outright. One that can be written but cannot stand alone is not a branch, it is the handling of another branch's product.

> Example: the export evaluation supports no claim; with the position frozen, export equals "template + baked texture", and comparing its topological-consistency rate against Poisson reconstruction is a pseudo-comparison — we did no reconstruction.

**Criterion two: resources.** Every branch is tagged with hours, the total not exceeding 75% of budget, leaving three tenths for reruns after failure. Over budget, cut the resolution before cutting the branch: five levels to two still draws a curve, and where the knee sits goes into the limitations; delete the branch and an argument disappears.

The same action in writing is called deleting a paragraph: if a paragraph supports no claim, deleting it is cheaper than polishing — polishing useless prose only makes it harder to delete.

**Criterion three: narrative.** Whichever branch changes the paper's centre of gravity or some chapter's conclusion goes first. One that changes no conclusion goes last or out — something necessary that only fills an appendix table should not queue ahead of the main figure.

**An upstream change must be raised in the same round the branches are listed.** If a branch depends on changing the current configuration (say, sweeping constraint strength requires the position to go into the optimiser first), saying it after the run wastes that compute entirely and leaves an unsweepable curve in the report.

**A combination counts as novel only if it satisfies one of**: (a) it produces a phenomenon the single component does not, and that is measurable; (b) it changes the acceptance item, so a fact nobody had measured becomes the standard. One of the two, clearly stated, is enough; (b) is commoner and easier to attack — it must at the same time give the new conclusion (after the acceptance item changed, which conclusion changed). Neither, and it is engineering integration that belongs in the system description. Every claim also needs the strongest baseline: build a weak version and compare, and the reviewer's first sentence is "why not compare with the original implementation".

### Sketch the whole first, then colour the detail

With time short, the first reflex is "cut the scope"; the right reflex is "run the whole story through, then go back and colour".

```
wrong   perfect one detail while the other chapters stay empty
right   every chapter has something, even a skeleton; then thicken one by one
```

A drawing with only its lines still shows what it is; a drawing with one eye only leaves people unsure whom you are drawing. A report is the same: **ten skeletons beat ten empty sections**, because a reviewer first checks whether the narrative holds, then looks at the points.

Concretely:

1. Run the whole chain once by the shortest path — even with the plainest implementation and the fewest comparisons — so every section has a number to write.
2. Once it runs, go back: add comparisons, add criteria, add ablations. At that point a change risks only a locality, not the narrative.
3. The only question about "do this now" is: **without this, is there a break in the story?** A break means do it first; no break means it queues.

**Do not pre-estimate per-item hours.** Estimating by "number of unimplemented modules" is for ordering, not for declaring the work impossible. Tight time means working faster, not conceding early — reality is often faster than the estimate, especially once the implementation path is clear.

### One increment is parallel, not three phases

One step forward in the report moves three things at once: **find literature, align the narrative, fill in results**. They are not the sequence "read first, then write, then experiment"; they trigger each other as a triangle:

```
find literature → discover someone has done this route  → the "gap" in the narrative must change
align narrative → a section cannot say why this step is necessary → an experiment is needed to answer
fill results    → new data overturns the earlier statement → that section's citations must be re-chosen, and elsewhere compressed
```
```

There is one criterion: **when any one link moves, look back at the other two.** Change one alone and the report contradicts itself elsewhere — and that is the hardest class of error to find, because every section is right on its own.

### Advance by the whole story by default

Unless the user explicitly wants one section only, every step works on the whole story. Three reasons:

**One, a report is not a set of chapters but a chain of argument.** Change the third chapter's gap and the first chapter's problem definition may stop holding.

**Two, the links are parallel to begin with.** Add a paper and the narrative changes; change the narrative and an experiment is required; the result then compresses something elsewhere. Watching one section is cutting a hole in a net and sewing a patch on it.

**Three, a collection of locally correct pieces is not globally valid.** The commonest and deadliest report is one whose every section is self-consistent and whose joins are broken — the reader reaches chapter three before discovering that chapter two overturned chapter one's assumption.

Criterion: **after the change, walk from the first sentence of chapter one to the last sentence of the last chapter without the reader having to supply any logic.** This is the cross-link version of "dangling".

### Four moves fixed inside every cycle

**The four moves answer four different questions, and a cycle that only adds must inflate**: which one you are making decides what you write, not how much.

| Move | When | Criterion |
|---|---|---|
| add | a link lacks evidence | can the new sentence be refuted in one sentence? if not, it is not an argument |
| compress | two places say one thing | delete one paragraph: is information lost |
| drop | an experiment or paper unrelated to the claim | which sentence of the claim does it answer for? no answer, drop it |
| move | right content, wrong place | which chapter's conclusion does it serve? follow the conclusion |

These four are not "what you do when you run out of words". **A cycle that only adds, never compresses or drops, must inflate, and everything it inflates with is repetition.**

### How a cycle closes

Closing is not "finished writing"; it is four things at once:

```
1  every citation added passes "delete it — does the sentence still hold"
2  every section's topic sentence matches the evidence under it (same for the closing sentence after a table)
3  the whole story reads straight through, with no place needing the reader to supply logic
4  conclusions that held before were not quietly overturned by this change — look back at chapter one and the conclusion
```

Item 4 is skipped most often, because the change is far from them.

### Zero citations does not mean no literature work

The first version of a report may hold only a narrative skeleton and not one citation, and still walk the same cycle: find literature (read the main method line of that direction) → align the narrative (decide section order and the wording of the gap) → fill in results (put the numbers of existing experiments in).

**Zero citations means the basis is not written into the body, not that nothing was searched.** It also means a cycle's product can be a skeleton alone — whether the cycle completed is judged by "does the story close", not "is the body a finished draft".

### Revise section by section against the standard, not by instinct

The closing act of every cycle is to measure the report section by section against this file. **Not reading for feel — checking against the criteria, one by one.**

The order is fixed, because each item depends on the previous one's conclusion:

```
§13 skeleton and narrative  do the chapter names read as a paper's contents or a work summary; is each section's topic sentence a complete conclusion
§14 contribution classes    does each entry of the contribution list forward-reference a section number; has learned behaviour been mixed into achieved behaviour
§5  four prohibitions       meta-discourse, current state, invented terms, fast variables
§17 nine hand-over questions  cover the title and can the topic still be guessed; is the first sentence "we did X" or "the field defaults to Y"
§19 the four closing items  citations, topic sentences and evidence, whole-story coherence, old conclusions not overturned by this change
```

**The product of a revision is a diff, not "I looked at it".** After measuring each section you must be able to say what changed there and why; if you cannot, you measured nothing, you only read.

**The standard itself is tested by this round too.** If revising the report reveals that a rule conflicts with the draft — the draft already upgraded that criterion — change the standard first, then the draft. A stale ruler produces wrong conclusions, and produces them confidently. (Same source: "when adding a prohibition, search back for items teaching the opposite action" in §15's three checks.)

### Before migrating or incrementing, answer four questions

Moving material from the old draft into the new, or adding content to a section, requires answering four questions first. **If you cannot answer the third, do not add.**

```
1  what kind of information is this?   narrative (structure, order, gap wording) / literature (citations, comparisons) / results (numbers, figures, tables)
2  which move am I making?             add / compress / drop / move — four different standards, four different written forms
3  what does it contribute to the whole narrative?  one sentence naming the section and sentence it supports. If you cannot, or the contribution is one line of background, consider not adding it
4  does it introduce a contradiction?  which existing sections conflict; does resolving it require touching other chapters (if so, it goes on the stack — do not change it in passing)
```

The third question is the gate. **"This passage is well written" is not a contribution; "it proves the third chapter's gap holds" is.** Typical low-contribution shapes:

```
a fine observation that no section's conclusion depends on  → drop
a highly relevant citation no assertion cites              → drop, or demote to one line of background
an experiment that ran for hours and supports one boundary sentence → compress it into the boundary, no process narrative
```

The fourth question's product is usually **a stack**: a migration is not a series of independent edits — changing the third chapter's gap requires the first to restate the problem and the sixth to reword its boundary. Such chains walk the `task-queue` entry by entry (see §0), and before starting you write one sentence on **the migration's approach** — the same discipline as giving the survey table before touching the first word of a thesis revision.

**Migration's direction is not "move the old draft's good sentences into the new draft" but "make every piece of valid information land where it belongs in the new narrative".** The old draft organised by stage and by experiment; the new one is an argument chain, and the same paragraph serves a different conclusion in each. Moved across, it must be re-confirmed whose it serves, or what you get is "new structure plus old argument".

### The loop of advancing: judge the state before acting again

§21 governs "how to kill a hypothesis". This section governs the step after it. **It does not belong to experiments** — it governs how any action closes.

Writing code, running experiments, writing documents, delivering, changing a plan — all walk the same four rings:

```
action → observation → judgement → decision
```
Skipping the middle two rings leaves "action → action → action": every step moves and no step knows where it is. That is not advancing, it is parallel trial — and parallel trial is cheaper done in one go; done piecemeal it only multiplies fixed overhead by the count.

### 1. Observe with output measures, not process measures

**The two columns below describe the same run two ways, and only one of them says whether the thing exists**: process measures can all look normal while nothing is being learned.

| | Describes | Example |
|---|---|---|
| process measure | how much I did, how far the object moved | how many steps ran, how many places changed, what the loss was, how much the error fell |
| **output measure** | **what the object has become** | is the thing made, does the reader understand, can the other side use it |

Output measures per setting:

| Setting | Output measure |
|---|---|
| running experiments | what the product looks like, how much it covers, where it is wrong |
| writing code | the behaviour it actually shows, not how many places changed |
| writing documents | can the reader restate the claim afterwards, not how many sections were written |
| delivering | can the other side use it directly, not whether the list is complete |

The first paragraph of any report or self-check must be an output measure. Pasting a loss table only proves the model moved, not that the thing was made.

### 2. A judgement is three pieces; with one missing, do not start the next step

1. **which product is currently the best** (down to the file, the version, the sentence), not "the thing we made";
2. **which class the defect belongs to** — a class is compulsory; "good or bad" is not one;
3. **how far off it is** — consecutive numbers on the same ruler.

**The class sets the direction, the number sets the magnitude.** Without a class, "still short" yields no action; without a number, the action's magnitude is by feel. A good-or-bad judgement yields no next step, only a mood.

Grain for the classes: fine enough that **each class corresponds to a different fix**.

| Setting | Class examples |
|---|---|
| product | absent → incomplete → inaccurate → imprecise (coverage / placement / form / artefact) |
| code | does not run / runs wrong / runs right but slow / runs right but brittle |
| document | not understood / understood but not believed / believed but not remembered |

The criterion is fixed before acting and only filled in afterwards — no changing the criterion, no substituting the eye.

### 3. A decision's change must be traceable

When proposing the next step, you must be able to name **which observation of the previous step caused this change.**

If you cannot, the change came from "it looks bad", not from observation. Then this step and the previous ones are **parallel branches**, not progress — the condition did not come from the previous step, it merely queued beside it.

Parallel branches should be done in one go; piecemeal only multiplies fixed overhead by the count (for experiments, boot and loading; for code, build and deploy; for documents, a full read and a review).

**That is the whole answer to "what is the point of doing it in several passes": only when the last result changed the next condition is several passes better than one.**

### 4. The ruler checks itself first

Observation depends on a measuring instrument, and instruments break. When the eye and the number disagree, suspect the ruler first, and do not rush to explain the object.

A broken ruler is most dangerous in its chain: it produces a number → you give that number a cause → you change the next step against that cause. Every step has a "reading", it looks exactly like progress, and three wrong turns are walked in a row.

Criterion: **measure the same object once more with a different instrument.** If the two disagree, fix the ruler first.

### 5. Several steps of progress must form one line

Put several states side by side and you should see **one line moving**: the same quantity improving, the defect upgrading its class (absent → incomplete → inaccurate → imprecise).

If each state measured a different ruler or a different quantity, that is not a line but several branches; then you may say **"several candidates were tried"**, not "several rounds of progress".

This is also a self-check: if you cannot say "the same quantity is improving", those rounds did not advance.

### 6. Before a retrospective, sweep all products

**Prerequisite: list every existing run directory with its timestamp, and mark which have never been cited by any retrospective.**

The evidence is usually already on disk. Run, stored, never logged, never pulled out for comparison — each day such a thing sits there is another day of repeated guessing.

Criterion: **directories cited per round ÷ directories that exist.** If the ratio does not rise over time, the retrospective only looks at the newest round.

### 7. Exclusions are assets, not a field

Each exclusion records three things: the hypothesis in one sentence, the reading, the reason it was out. Keep them as a list you can pull up at any moment.

**The whole point of memory is not stepping in the hole again.** So the list reads "next time X appears, do Y first", never "on such a day this happened".

Each retrospective does two things: merge the new exclusions into the list, and check whether the road this round intends to walk is already on it.

### 8. Progress is defined by products

Writing documents, editing memory and giving retrospective reports are not progress in themselves. The only standard: in the full context, has "the currently best product" improved.

If it has not, the round is zero, however many pages of methodology it produced. Memory guards against repetition, it is not output; reporting it as output replaces "I made something" with "I was diligent".

---
