# Audit procedure: the closed-loop strategy documents

**What is audited: every document that serves the overleaf loop** — the core loop `results-first-narrative.md`, the method `strategy-roleplay/skill.md`, each layer's role document `01-supervisor.md` / `02-lead.md` / `03-executor.md`, and the writing standard `docs/writing/skills/`.
**Purpose**: after enough practice and accumulated lessons, use this file to strengthen the loop's guidance — the core loop, the skill and every layer's agent are all in this table. It is executed before and during the audit.
**Trigger**: repairing a role document, reviewing a layer's window, coordinated adjustment, white-box audit.
**Product**: one report whose last three lines are `DELIB:` / `AXES:` / `FEEDS:`.
**Discipline**: read only, change nothing; the audited documents are byte-identical afterwards.

---

## 0 How an incident reaches a document

1. **Someone failed**: one reproduction got a step wrong (written by feel, guessed, invented a reading).
2. **Read the action sequence**: look first at **what it actually did** (`locate` / `wander` / `guess-write` / `verify`), not at what it said.
3. **Find the earliest impossible step**: a failure surfacing at the executor layer does not mean the executor layer is wrong. **Walk back from the failing action to the first place where "this layer should have known, but its document does not say"** — that is the document to change. **If you cannot walk back to any place, the failure itself was not recorded clearly — go back to §0a and complete it (action sequence + first-impossible judgement), and change no document.**
4. **Change in place, change no arrangement** (authorisation in §0c): afterwards you must be able to say "next time this situation arises, that layer will read which sentence".
5. **Re-issue the reproduction**: the criterion is **the action sequence changed** (it used to `guess-write`, now `locate` comes first), not "this time the result was right".

## 0a Incident record: without this table, every later step is an impression

Each failure lands one row, **fields fixed**; a failure with a missing field may not proceed to localisation:

| Field | Content |
|---|---|
| id | `<date>-<n>` |
| Layer seen | the layer where the failure **was seen** |
| Action sequence | that session's `* read_file / write_to_file / execute_command` order, pasted as is |
| First impossible (initial judgement) | the first place walked back to + one sentence why |
| Evidence | `context:<line>` (the user's words) or `path:<line>` (the sentence the document lacks) |

## 0b What each of the three documents governs (for localisation)

**The symptom picks the document**: guessing which document is at fault is how an audit spends a round in the wrong file.

| Symptom | Which document first | Why |
|---|---|---|
| every layer complied, and the result is still unusable | the core loop `results-first-narrative.md` | the exit lacks a condition; however correct the layers are, they cannot stop |
| nobody knows what a step is for | `strategy-roleplay/skill.md` | the method never put that step in |
| a layer does not know what it should know | that layer's document | its window / obligations / instruments are missing a cell |
| it should know and it is written, but it did not read it | outside this file: the **reproduction criterion** | the criterion never checked actions, so no document is missing |

## 0c Who does what

- **The owner (the user)**: sets the bar (D-class evidence comes only from his mouth) and decides whether to change anything.
- **The auditor**: finds the earliest impossible step, supplies `prov:`, **and changes it in place** (below).
- **Three constraints on changing in place** (without them there is no authorisation): **one place per round**, **fill §0d's prediction table first**, **the change carries `prov:`**. With all three you write directly, without waiting for approval — **wait a round and the context that saw the site is gone, and what gets written is usually an imagined gap.**

**Why in-place change is authorised**: the auditor holds the first-hand evidence (action sequence, line numbers on both sides, dry-run result); handing it to another person converts evidence into hearsay. **Hearsay always loses half, and the half lost is exactly "why this place".** So: **find → fill the prediction table → change → attach a reproduction**, one line to the end; the owner keeps **the right to stop**, not a right of approval.

## 0d One place per round, and write the prediction first

**One round changes one document, one gap.** Change two and a better next round cannot tell which one did it; a worse one cannot tell either.

Fill this table before changing; cannot fill it, do not change — **cannot fill means "I do not yet know what I will see afterwards", which means the localisation is imprecise**:

| Column | Content |
|---|---|
| Which sentence | `path:<line>` + what it says now / what it becomes |
| Expected action change | in the next reproduction, **which step changes from what to what** (e.g. one more `read` of the neighbouring text before `write`) |
| Criterion command | the command that reads this out of that session's export |
| Failure signal | if the next session **still** shows the old action, what does that mean (wrong judgement? or another layer is also missing it?) |

## 0e The same place changed twice and still failing: doubt the criterion, not the document

Change the same place two rounds running and the next session's actions **do not change** — do not change that place a third time. **What must be audited now is the criterion**: does it read the product or the actions? could it read `guess-write` as `locate`? **An improvement the criterion cannot see did not happen.**

## 0f The core loop has no actions to read — dry-run it

The core loop (exit and conditions) is not exposed by any layer's actions; its symptom is **every layer complied and the result is still unusable**. Audit it by **dry run**: take a finished draft and judge it against the exit, item by item —

- an item that **passes, while that draft is in fact unusable** → the item lacks a definition (e.g. it requires "has neighbouring work" but not that the neighbour sits in the same setting);
- an item that **cannot be judged** (it takes a human to explain) → the item is unobservable, i.e. absent.

One item out of the dry run, one item changed; then dry-run the same draft again, **checking whether it flips from "passes" to "fails"** — if it does not, the new condition is still an adjective.

## 0g With no failure case: dry reading

You need not wait for an incident. **Give each layer only its own window and let it answer what its layer must produce** (lead: what this round builds and what the manuscript reads like; executor: what exists when this item is done and which sentence it lands on). **Where it cannot answer is a gap**, and it is an X1 gap, not "style".

Dry reading has a second use: **the product exposes misalignment before failure does** — a lead unable to say "compared with what" means the fence gave no neighbouring work, and you need not wait for the draft to go wrong.

## 1 Inputs: what must be in hand before auditing

**Seven inputs, each with a location and a stated fallback**: an input whose location you cannot name is an input you do not have, and the fallback is what you write instead of improvising.

| # | Input | Location | If unobtainable |
|---|---|---|---|
| I1 | the thesis (the status questions' original requirement) | the full context, given as `context:<start>-<end>` | write `missing: thesis provenance` |
| I2 | each layer's most recent correction | the full context, given as `context:<line>` + one verbatim sentence | write `missing: lesson lineage`; **that layer may not conclude** |
| I3 | the four current role documents | `strategy-roleplay/{skill,01,02,03}.md` | stop |
| I4 | the core loop document | `results-first-narrative.md` | stop |
| I5 | project state | boss context, wish file, code root, experiment ledger, assembly directory, state file | write `missing: <which one>` |
| I6 | instrument state | `.agent-ide/skills/*/SKILL.md` (each tool's purpose and invocation form) | write `missing: tool list` |
| I7 | the writing standard | the project's `docs/writing/skills/` `00_` entry and its mapping table (pointed at by the boss context's `WRITING:`) | write `missing: WRITING entry` |

**Window coverage**: the small context must reach "the last user message before this round"; if it does not, write `missing: <time span>`, and **never substitute an earlier span** (R1b).

---

## 2 What is audited: identity first, structure second

### 2.1 Three pieces of evidence per layer (one missing = that layer was not audited)

**One row per layer, three cells each, and a cell you cannot fill is the finding** — not a reason to widen the row.

| Evidence | What to look for | How to write it |
|---|---|---|
| the thesis requirement | why this layer exists, in the owner's words | `context:<start>-<end>` |
| lessons | which day, for what it was corrected, the words | `context:<line>` + one verbatim sentence; **the owner layer may write `n/a — he is the source of the bar, no corrections on record`** |
| document landing point | which section carries it | `path:<line>`, or `doc gap: <path> §<section>` |

**The conclusion sentence (the only acceptable form)**: `<layer>: it would do <what> wrong in <which situation> → the document therefore gained <which sentence> → <path>:<line>`.
Cannot produce this form = no conclusion.

### 2.2 Six axes (audited in §2.3's order until the break point; satisfied ones get `path:<line>`)

**Six questions, each answered with a path or a declared gap, never with an adjective.**

| Axis | Question |
|---|---|
| X1 window completeness | with only its own window, can it answer what its layer must produce |
| X2 use of project state | code root / data / corpus / experiment ledger / assembly / state file: which it reads and what for |
| X3 use of instrument state | which tool it calls, which `SKILL.md` holds the invocation form, which tool produced the reading |
| X4 inter-layer linkage | can downstream resolve every upstream noun to a path; can upstream prevent every downstream failure; give a sample of the message passed |
| X5 wish reachability | each clause in four hops: who carries it → which action → which reading → which section of the body; `path:<line>` per hop |
| X6 observable behaviour | can a breach of this guidance be caught by `grep` |

### 2.3 The order of the six axes, and when to stop

With limited time, this order: **X5 (wish reachability) → X1 (window) → X2 / X3 (state and instruments) → X4 (linkage) → X6 (observability)**. The reason is that X5 is the terminus: **its break point decides whether the other five are worth auditing** — if a clause cannot reach the body at all, patching the window first only makes the idling tidier.

**Stop rule**: when X5 shows a break point, audit only up to that hop and stop to write the report; **once the break is fixed, the next round starts again from X1**. A report that fills in every axis is usually a report that found no break point.

## 3 How changes are recorded: two classes of source, one field

**Two sources, one field**: every change states where it came from, or it is recorded as invented.

| Class | Content | Evidence may come only from | How to write it |
|---|---|---|---|
| **D, the requirement side** | status questions, behaviour prohibitions, delivery form, criteria | the user's words | `prov: D <context:<start>-<end>>`; **when not yet exported, write `prov: D this session（verbatim）`** |
| **S, the structural side** | window, ecosystem list, tool invocation forms, state file | the wish's clauses + the state as actually read | `prov: S <clause> + <path>:<line>` |

**A change without `prov:` is recorded as fail.**

**Three dialectic steps** (compulsory for each proposed change): expectation (one observable sentence) → **counter-example** (was it refused in the context? is there contrary evidence in the state?) → keep or withdraw.
Skipping the counter-example = no dialectic. **The report contains at least one withdrawal**; all keeps means no real dialectic happened.

**Dialectic and evidence**: a D-class counter-example is found in the context; an S-class counter-proof is found on disk (the file does not exist, the tool lacks the capability, the reading does not match).

---

### 3.1 Look before proposing: never add what already exists

Before adding a rule, search the documents for the same thing said otherwise (`grep -n` on three or four keywords). **If it exists, write `已has: path:<line>` and turn the proposal into "move / rewrite / add a criterion", adding no new section.** Two copies of one meaning in a directory are harder to find than a missing sentence.

## 4 Closing

**Four lines, and every number in them is countable from the report itself** — which is why the counting rule comes before the format.

```
DELIB: <small-context spans read>,<lines of the four docs skill+01+02+03>,<dialectic points>,<linkage points>
AXES:  <X1 gaps>,<X2>,<X3>,<X4>,<X5>,<X6>
FEEDS: <D-class items>,<S-class items>
ITER:  <rounds>,<last round's conclusions overturned>,<documents covered>/5
```

**The four documents = `skill.md` / `01` / `02` / `03`; `results-first-narrative.md` is counted separately.**

**All three numbers must be countable**: every number in the report is followed by a command or a line range (e.g. "9 dialectic points = the 9 lines of report §4"). **Uncountable = padded = fail.**

---

## 4b The audit itself advances in rounds too

**One audit is not one sweep.** A round of audit must **simultaneously** touch the core loop, `skill.md` and every layer's document, but **they are opened round by round**: each round pushes one contradiction to the point where it "can be changed", and the other layers merely record "seen this round, not expanded". That way one audit covers every branch instead of only the most conspicuous layer.

**What every round must do (missing one = not a round)**:

1. **Reread the four documents in full** (not as remembered from last round);
2. **bring one new piece of evidence** (a new action sequence / a new context passage / a new dry-run result); **a reread with no new evidence is not a round**;
3. **state where last round was wrong** — one sentence, pointing at last round's specific conclusion. **Cannot write it = this round is a repeat**;
4. **land exactly one change**, filling §0d's prediction table;
5. **register it**: a `## ITER <n>` subsection containing "this round's new evidence / last round's conclusions overturned / this round's change / left for next round".

**Convergence (all three at once to stop)**: the latest round found **no new break point**; **every listed contradiction has a home document** (core loop / skill / some layer); **every layer's six axes have each been opened at least once** (not filled in — opened).

**Compulsory in the report**: `ITER: <rounds>, <last round's conclusions overturned>, <documents covered> / 5` (five = core / skill / 01 / 02 / 03).
**Two rounds or fewer with no overturn recorded → treated as not iterated**: an audit report that never overturned itself usually just tidied up its first impression.

## 4c Criteria may come only from documents, never invented

**Every criterion must carry a source**: `exp: <path>:<line>`, pointing at a **guidance sentence** in that role document or `skill.md` (it says "what to do"), **not at a written verdict** (it says "this counts as passing").

**Role documents may not contain verdict answers.** They give guidance — what to read, what to answer, what to hand over; **"does it count as passing" is not in a role document**, it is set by the reproduction test's criterion (`exp:` plus action sequence, §2 of this file). **Writing a verdict into a role document is handing the answer to the person being examined**: it will hand in the answer, and what is measured is transcription, not capability.

So `exp:` cites the **guidance**, and the criterion is **the observable form I derive from that guidance** — the two must not be mixed: the guidance sentence is the document's responsibility, the criterion is the audit's. **An item with no `exp:` is an invented criterion: it does not score, does not enter the report, and may not be used to conclude.**

**The report's order is fixed**: first the **criterion sources** (one line per `exp:`), then the **actual actions** (`* read_file` / `write_to_file` sequence), and only then the gap. **Writing it backwards — "I think" first, then a reason — is invention.**

**Four common inventions, each forbidden**:

| Invention | Example | Correct practice |
|---|---|---|
| taking "a requirement I wrote into the prompt" as expected behaviour | my own D1–D5 clause criteria | the prompt sets only the **input**; expected behaviour is taken from the role document as `exp:` |
| taking "the document contains this line" as implemented | citing a sentence of `02-lead.md` to conclude "it will comply" | check whether **this session's actions** deliver it, with the criterion still from `exp:` |
| writing a verdict into a role document | adding "a missing three-part receipt counts as fail" to `02-lead.md` | **not allowed**: role documents give guidance; "does it pass" stays in the reproduction test and this file |
| taking "the result is right" as "the behaviour is right" | the product looks good, so tick it | judge whether the action sequence lands on the step `exp:` names |

**One sentence**: what is audited is **the gap between the document's expectation and the actual actions**, not the gap between my taste and the product. **Criteria uninvented is what makes a report useful.**
## 5 Prohibitions

1. Citing this file's line numbers (`docs/audit-deliberation.md:<line>`) twice or more → treated as not having read this file.
2. The report containing `更好` / `更清楚` / `更完整` / `更充分` → recorded as fail (self-check and give a reading before delivery).
3. Giving only a number and not the sentence form (§2.1) → treated as no conclusion.
4. Using the document's own words as the thesis or a lesson → treated as invented evidence.
5. A change proposed with no `prov:` → treated as invented.
6. Concluding without an action sequence (no `* read_file` order pasted) → treated as not audited.
7. A `DELIB` / `AXES` / `FEEDS` number with no command or line range behind it → treated as padded.

---

## 6 This file drifts too: keep only "drift shape → the clause that now blocks it"

**A method document carries no dates, no case numbers, no "what happened on such a day".** Those belong to the ledger; written into a method document they become one round's instance record — useless in another project, and read as a rule. **Only "what shape we once drifted into → which clause blocks it now" is kept here**; git keeps the time.

| Drift shape | The clause that blocks it now |
|---|---|
| auditing only the executor, never the lead's and owner's windows | §2's three pieces of evidence (every layer is asked "what would it do wrong in public") |
| one round of audit, with four document edits counted as four rounds | §4b round-by-round increments (reread in full / new evidence / where last round was wrong) |
| gaps written as "missing", never as whose requirement is missing | §3's D/S classes + `prov:` |
| dialectic with only an expectation and a conclusion, no counter-example or withdrawal | §3's three steps, with at least one withdrawal |
| the three closing numbers padded | §4's "`DELIB:` / `AXES:` must be countable" |
| a gap found and thrown back at the user | §0c in-place change (one place per round / prediction table / `prov:`) |

### Survey the whole text before repairing

The first act of repair is not the change but the survey. Reversed, it is wasted work: conspicuous problems (a wrong citation, a broken reference) give a feeling of progress the moment they are fixed, while global problems (should this chapter exist at all) are expensive and give no immediate feedback, so they get skipped — and half an hour later the chapter that most needed deleting is still in the table of contents.

Fill the survey table row by row, five columns, and a row with a column missing is not filled:

| Chapter | What it records | Is the body harmed if it is deleted | Status (how many verified) | Verdict (keep / merge / demote) |
|---|---|---|---|---|

The third column must give the reason deletion was considered. "Keep" alone does not count — "keep" is not "considered". Write "considered deleting; X would break, so keep".

**Pointed at one place, sweep the whole class.** What someone points out is usually one case, not the whole problem. Fix that one, then immediately run the same ruler over the class: list every candidate, judge each against "does it meet the reason just given", and conclude keep, delete or change for each. Fixing only the named place makes the other person your scanner — most visible when deleting: remove one appendix and the other two must be re-measured against the same reason.

**Before deleting, check content, not labels.** The question before removing a section is not "does anyone write the words 'see appendix'" but "is what this section carries still in use elsewhere". `grep` on labels checks document links; `grep` on content checks dependencies, and only the latter exposes the knock-on edits early. Also check cross-file references (does another document point at it), and read the changed region after deleting to confirm the join.

**With the survey unfinished, do not touch the first word.**

Close the repair with one acceptance sentence: **"of N chapters, M passed the deletion test; these chapters were demoted."** Cannot list that sentence = no survey was done.

### Sweeping has no upper bound

"Do not expand indefinitely" is the wrong instinct. In one file, problems come in groups: find one mixed-up term and the same batch usually holds five; find one number that does not match and there are more nearby.

**Criterion: the third occurrence of the same class of problem is not "an incidental find", it is a class not cleaned out.** Stop then and sweep by class, rather than fixing one by one.

The cost is direct —

```
one full sweep      20 minutes, one pass
five separate fixes 10 minutes each = 50 minutes, plus rebuilding context each time
```

Dearer is what gets missed: the same class of problem left in the file is rediscovered next round, and the comprehension cost is paid again.

**The only exception**: fixing one place produces a new class (not a new instance). Then stop and land the rule, because continuing to sweep only produces new classes.

### 1. Decide first whose eyes are used

Answer one question before reviewing: **where do this review's dimensions come from?**

If they all come from this file's clauses, the review can only find problems that "violate a known rule" — **an angle no rule covers is never found**. Write "a chapter may not be called a capability comparison" and the next unforeseen strange name still slips through. Adding clauses is patching; adding a perspective is changing the method.

So the order is: walk the material as a reader first, and return to the clauses afterwards.

| Perspective | Looks only at | Catches |
|---|---|---|
| defence committee | table of contents + conclusions + figures | does the chapter name read like a paper, do conclusions carry numbers, is the contribution stated in one sentence |
| reviewer | the first three sentences of the introduction + the contribution list | does the gap hold, does each contribution have evidence |
| peer | related work + method | is the novelty really new, are the recent strong works missed |
| reproducer | experiment setup + parameters + state | can it be run by following this, which item is missing |
| my future self | state lines + todo | which conclusions are guesses, which data never actually ran |

**Minimum: the defence committee and the reproducer perspectives every time.** They expose the dearest errors — a wrong chapter name makes the whole document read as a work report, a missing parameter makes it irreproducible. The other three are picked by how mature the material is.

While walking, do one thing only: **pretend this is the only material you have, walk it in that role's reading order, and note where you stick.** Do not think "which rule does this satisfy" while reading.

### Read is a compulsory action, not an option

Pick the wrong tool and everything stays shallow. `grep` gives only matching lines, `sed` gives only line ranges, and neither tells you "what this passage is about as a whole". Edit files with them and you edit the letter; read the whole section and you edit the logic. The former produces sentences with no meta-discourse; only the latter finds that the section never answers its own heading.

**Four compulsory occasions; miss one and the round is not credible:**

```
start of a review round   read_file the whole text (600 lines in three passes), no sed sampling
before touching anything  read_file the whole section, not ±3 lines
each pop of the stack     read_file the range that entry involves
after a batch of changes  read_file one paragraph either side of the changed region, confirm the join
```

The criterion is simple: **if the round ends without having read the audited object in full, the conclusion is not credible — however many places were changed and however clean the stack**.

Symptom table:

```
grep-only edits    sentences comply, paragraphs still scatter; the same class reappears one line down
sed sampling       you see an isolated line, not its place in the paragraph
reading in full    you can answer "what is this section arguing, does it answer its heading"
```

### 2. Read the context before judging

**Before changing any section, read that section in full plus one section either side.** Conclude from one line, one sentence, one fragment and the change will conflict with the context — a common shape: a phrase is wrong in isolation and right in context, because the previous paragraph already qualified it.

The reading has a floor: **the whole section + the last paragraph of the previous section + the first paragraph of the next**. Those three decide what the section's job is, what it inherits, and whom it hands to.

### 3. Structural judgement is human, not a script

A script can check two things only: **existence** (is this word here, is this section here) and **counting** (how many places, how long, what share). It cannot check three:

```
is this passage right          needs understanding the content
should this section exist      needs judging which thing it corresponds to
will changing this conflict    needs reading the context
```

So the script's place is: **once the structure is settled, use it to find omissions**. Used the other way round — run the script first and patch against its FAIL list — it turns the document into "a compliant product where every word appears", which reads as assembled.

One rule of thumb: if a section's edits can be fully automated, that section should not have been written by a person; and if a script returns the same FAIL several times while you keep rewording to please it, the check itself is wrong — fix the check first.

### 4. Investigation conclusions must point at evidence

Deep investigation (why the code is written this way, why it failed last time, whether a parameter was copied over wrongly) is not within "one read and judge". Such a conclusion has one legal form: **pointing at specific content in a specific place** — which line of which file, which passage of the log, who said what in which round of the context.

Three forbidden forms:

```
filling in by inference   "probably the warm-up path differs"   → must give both actual implementations
attributing from memory    "that anomaly was the learning rate"  → must give the parameters and the symptom then
appealing to common sense  "this kind of method usually needs X"  → common sense does not explain this project's failure
```

Take evidence before investigating: read that code, open that log, search the context for the words. If you cannot get it, say "cannot get it" first, and never fill the hole with inference. **A cause filled in by inference does second-order damage**: the code is changed against the wrong cause, the problem does not go away, and there is one more change nobody understands.

Likewise, do not "do whatever comes to mind" while investigating: verify one hypothesis at a time, and it must be able to point at evidence. Changing three places before running again is abandoning attribution.

### 5. After changing, read back — three checks, and only by reading

All scripts green ≠ readable. **Any substantive addition or deletion (changing a criterion, merging sections, moving a paragraph, deleting a conclusion) requires opening the file and reading it, not just grepping keywords.** `grep` checks whether a string is present; reading checks whether the two passages still hold together — the latter no script can replace.

Three checks; missing one means the change is not done:

| Check | Action | Typical residue |
|---|---|---|
| contradiction | read two paragraphs either side of the change, then scan the whole text for anywhere that says the opposite | the criterion was upgraded while another section keeps the old one; the state changed while elsewhere still says "verified" |
| redundancy | is what the change wrote synonymous with any paragraph in the text | one mechanism explained in both the body and an appendix; one reason stated in both the introduction and the conclusion |
| dangling | walk from the section's first sentence to its last; is there any step the reader must complete themselves | the previous paragraph says "this method" while it has been moved elsewhere; the causal link under "therefore" has been deleted |

The reading is not confined to the changed place: **read everywhere it is mentioned** — change a number and read every paragraph citing it; change a term and read every occurrence.

**When adding a prohibition, specifically search back for items that teach the opposite action.** A prohibition says "do not do X", an operational instruction says "do Y"; the two moods never collide literally, so a keyword grep misses them. The method is to run the whole library by topic word and look only at the paragraphs that teach an action — on the day "write no state" was added, both "mark each number: verified / partial / not done, pick one" and "every number carries its state" were still teaching people to write state, and both were more specific than the new prohibition.

The test for redundancy is not "do the words look alike" but **delete one paragraph: has information been lost**? A little lost means merging, not deletion; nothing lost means pure repetition.

**Changing one place is not completion.** Every change leaves places elsewhere needing synchronisation, and the default act after a change is to make them all at once, rather than waiting for the next review round to find them.

### 6. Treat the symptom or the cause

Before each fix, ask "why does this place exist at all", then act.

```
symptom treatment   delete that comparison table, keep the codes in the body as they were
cause treatment     the body calls it "level X", and the table is no longer needed
```

The test: after this change, will the same class grow elsewhere? If yes, it is symptom treatment. Symptom treatment's result is "this place is better"; cause treatment's result is "this class no longer appears".

There is one exception: when the cause cannot be treated for now (too expensive, depends on something external), patch it, and write beside the patch "this is a patch, and the cause is what". Without that sentence the patch gets read as design.

### 7. Conclusions land by default

Any reusable judgement — a criterion, a method, a lesson, a boundary — has the default action: **write it into the skill or memory and report what was written**, without waiting for an instruction.

The wrong question to ask about "should I write it": did the user ask. The right one: next time this situation arises, will this be used? If yes, write.

The only legal reason not to write: it holds only this once (a one-off configuration, a specific number, the current progress). Say explicitly "this is not written because it expires", rather than skipping in silence.

After writing, report the location: file, line, or memory id. A "recorded" with no location cannot be checked.

### 8. The retrospective after a mistake (five steps, missing one = not done)

When a mistake is pointed out, the easiest thing is to apologise and the hardest is to point back and sweep. Five steps in order:

**One, record the error.** Which file, which line, what situation, what the correct action was. Write the trigger as "what I should ask myself before acting", not "what the user will say" — the latter hands the right to intercept to someone else, and the premise becomes "someone must scold me".

**Two, point back.** Which rule should have blocked this, and why it did not. Check all four causes:

```
does not exist at all   → add an item
written too abstractly  → turn it into an executable action
no path that reaches it → say at which step it would be recalled
placed too far back     → move it to where you look before acting
```

**Three, change that rule.** Put it where it can block, written as an action not a principle. "Before writing a file, report: which file, what changes, why, and wait for one assent" is an action; "be careful" is not. Merge with a similar existing item rather than adding.

**Four, sweep the class.** Extract the **error type** from this one place and sweep the whole text by type, not by grepping that word.

```
searching literally  search "the real decision" → finds only that sentence
searching by type    the type is "displaced subject" → hits "this section", "this document", "here": 11 places
```

How to extract the type: ask "what is the error here, essentially". A displaced subject, an abstract quantifier, an invented term, or a state written as a conclusion? You have proposed a type only when you have a description that covers other places. If you cannot, you understood only this sentence.

**Five, verify.** Can it be blocked the next time this situation arises; if not, step two judged wrongly — redo it, and do not add another rule.

Recording only "this was wrong" explains the past and blocks nothing. Fragmentary records — the error logged, with no pointing back and no verification — replay the same class of error after every follow-up question.

### 9. The error-type library

When a mistake is pointed out, consult this table first: if it fits an existing type, execute its "treatment" directly; if not, add a row.

| Type | Identifying feature | Treatment |
|---|---|---|
| displaced subject | the subject is "the decision / this section / this paragraph", not the object of study | rewrite with the object of study as subject; pure layout notes are deleted |
| abstract quantifier | "one place", "that place", "several", "some" with unclear reference | land on a concrete object: ordering, occlusion accumulation, initial opacity |
| invented term | the phrase never appears in papers of the same line ("an error the optimiser can absorb") | split into ordinary words, put the mechanism in the body |
| colloquial | "several things", "cannot find it out", "do not use" in a heading | standard term + a full judgement sentence |
| symptom as heading | the heading describes the symptom ("the curve still looks good with the dimension wrong") | heading states the method's judgement, the symptom drops to an illustration |
| self-assessment chapter name | capability, growth, gains, reflections, comparison | replace with a decision-style name; not a first-level chapter |
| fast variables in the text | next step, current progress, codes, accounts | move out of the document or turn into state strength |
| ledger as content | comparison table, mapping table, conversion table | remove one of the two sources, maintain no bridge |
| fixing only the named place | one case fixed, the class untouched | go back to step four and sweep |
| conclusions not landing | understanding reported, nothing written | see §7: write by default and report the location |
| file name as title | the first line is `# <project> the thesis`, `# draft` | a paper title carrying object and action |
| mixed units | `<N> seconds` and `<M> h` in one document | unify: Chinese documents use seconds / hours, keep symbols only for things like GB |
| unexpanded abbreviation | SDS, SH used from first appearance | expand in brackets at first use; domain-standard metrics like PSNR, SSIM, LPIPS, OCR are the exception, where expansion only bloats. Everything non-standard is expanded; in a Chinese document write bbox as 包围盒 |
| missing format pieces | no abstract marker, no keywords | add `摘要` and `关键词` (4–6, semicolon separated) |
| inverted length weight | front chapters 26%, core chapters 24% in total | the core chapters (method / validation) should outweigh any single non-core chapter |
| reader-facing meta-discourse | "the reader should see at a glance", "the reviewer will ask" | delete, or turn into the fact it was meant to state |
| subsection name pointing at a document element | "the four incidents in the table", "that table above" | use the object of study as subject |
| numbers not matching content | "four questions" followed by five items, "two follow-ups" followed by three | count after writing; the number follows the list |
| one list inconsistent in several places | a switch written in three places as three kinds, six items, then three again | pick one as authoritative, the rest point at it |
| state words conflicting with facts | a run that did not hold recorded as "not done"; "the first three levels ruled out" while level one was never done | check each with the trichotomy: did it run, is the product there, does the conclusion hold |
| stale section numbers | the chapter count changed while a table still says "lands in: eight" | after every renumbering, scan all "§X" and landing-point columns |
| internal identifiers in the body | account names, `data/seed.txt`, `metrics` field names | write only "recorded in the metrics file", never the path |

**This table's value is that it grows, not that it is complete.** A table with no row ever added shows no retrospective happened; a row with only adjectives and no identifying feature is of no use next time.
