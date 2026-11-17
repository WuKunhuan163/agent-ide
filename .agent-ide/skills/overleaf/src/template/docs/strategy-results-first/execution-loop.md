# Working order: results → footing → narrative

**Where `data/<identifier>/` is**: `<tree>/docs/strategy-results-first/data/<identifier>/` — the material sits beside these documents, not at the project root. `<project root>/data/` is a different tree and will never hold it; a path written `data/<id>/…` below is that one.

**This file states the loop; the vocabulary lives one level down.** A reader holding only this file knows the shape of a round but not the nouns of the field it is run in: which quantity a row carries, what a "protocol" is called here, what the venue prints. That is by design — the loop is shared, the words belong to the instance (`src/template/instances/<id>/docs/strategy-roleplay/executor-notes.md`). Two consequences follow. An answer built on this file alone is correct in shape and silent in words; it must say so rather than supply a vocabulary. And when the words do exist in the instance, they are quoted, not paraphrased — a renamed quantity is a new quantity.

## What the name means: comparison writing, kept closed

**Writing a report for the first time leaves no standard in hand**: what a paragraph owes its reader, what counts as a standing opening, which sentences say nothing — none of that is in the grammar, all of it is in other people's finished work, and time does not allow learning it from zero. What benchmarking buys back is the *overall impression* of a finished report: the sections they have are the sections we have, their prose is our prose, and their way of narrating and of showing a result is ours. One comparable sample is put on the desk as a ruler, so that the draft first looks the part and is improved afterwards — a report that will not come together usually has the wrong skeleton rather than too little thought, and copying the skeleton of a finished piece is faster than inventing one.

**This section states what benchmarking is for; how a sample is read is the next section's business.**

## How a sample is read

1. **Read the shape.** Each sample carries a metadata record: for every section, its opening sentence, whether that sentence organises the paragraph, how many paragraphs it has, how many sentences per paragraph, how many citations per thousand words, and a note on how the paragraphs advance. Those numbers are what the section has to fit.
2. **Write the position table.** One line per paragraph of the sample. Each line names what that paragraph gives the reader: a field, a turn, the practice that stands today, the cost of that practice, the pivot. The output is a table of positions — not a paragraph to imitate.
3. **Put each claim in a position.** A claim with no position has two moves: cut it, or keep it and add one line saying this section needs another position, and why a reader cannot follow the pivot without it. A claim pushed into a position it does not fit reads like a paper and argues nothing.
4. **Read every sentence for what it gives.** A number, a condition, a boundary, a turn. A sentence that gives none of the four is deleted, not polished.

**Kept closed means the table is not filled once and left.** A position left empty is a question for the next run; the reading that comes back either fills it or shows the position was wrong, and every sentence standing on the old table is rewritten. So the product of benchmarking is a table that keeps changing, not notes taken once: a version that can be handed over comes first, and the rounds after it raise the floor.

**Either half alone fails in a way a reader can point at.** Table filled and the numbers taken from the abstract rather than from a run: the section reads well and its first claim has no source. Readings listed in the order they were produced with no turn position: the numbers are all there and the reader never learns what was wrong with the practice being replaced.

## What a round is

A round does one thing: it picks the next piece of work worth doing, does it, reads what came out, and writes down what that can be read against — the footing. Only then does a sentence of the paper earn its place.

The order does not reverse. The result is read before the sentence is written; a sentence written first is a promise the data has not yet kept.

Two moves close the round: the reading goes into the position table, and every sentence of the paper standing on the old table is rewritten.

The round reports one number rather than a list of activity: how much of what the owner asked for now stands on evidence. If that number cannot be recomputed from a file on disk, it is not a number.

## 1 Shared operations

Nine steps, one thing each, run in number order. Every step has three parts: actions, on-disk contract, criteria and breach.

A contract is a hard constraint, and four parts make it: file and directory, fields and their values, the moment of writing, a countable check. A check is a count, never an adjective.

Every dispatch carries one `<wish>`, taken from that item's identifier in the wish list. From then on state lives under `tmp/compare-loop/<wish>/`; a different `<wish>` is a different space, two spaces share no file, and reading across them is read-only.

Four rules hold for every step: state lives only under `tmp/compare-loop/<wish>/`, the body goes where the instruction points; read a file's hash before writing it and merge when it differs from last round's; intermediate output lands in `tmp/compare-loop/<wish>/tmp/` and is cleared before delivery; a round never overwrites an older round, earlier rounds are archived into `tmp/compare-loop/<wish>/archive/<round>/`, append versus rewrite is read from that section's moment of writing, and the workspace hangs on the project's existing data directory.

`<round>` is the integer in `tmp/compare-loop/<wish>/round.json`, incremented when a round opens. A blocked action is replaced inside the same step; the user is asked only after every route has failed, with one stack row; anything new found on the way goes on the stack and the work continues.

### 1.1 Turning the thesis into questions

What the idea is: the condensation of what the final report wants to present — what is shown, on what grounds, and where it stops. Not how it was produced, and not the process. The report expands it; when the two disagree, the idea's sentence is corrected first, and no paragraph of the report is deleted to preserve it.

Boundary one: the idea ends at the Conclusion. Its last section is the conclusion; there is no bibliography, no reading list, no citation-entry block.

Boundary two: a citation has exactly one form in the idea — the hook 〔key〕, attached to the sentence it supports. The entry behind the key — year, venue, volume, pages — never enters the idea; it lives in `report/final/assemble/references.bib` and in the `10_corpus/` registry.

Boundary three: citation management touches two places only — the report's prose, and the literature registry (`10_corpus/INDEX.md` and the package directories). What is fed back into the idea is the hook, never the entry: 1.10 writes hooks.

Boundary four: a hook exists only after it is registered. A key may appear in the idea only when `references.bib` carries the entry and `10_corpus/` carries the package; an unregistered hook is `dangling`, and the same round either deletes the sentence or registers the source — it does not survive the night.

Boundary five: the idea carries no work-log — no todos, rounds, script paths or line numbers. What it promises the reader is conclusions and grounds, not the state of the work.

Boundary six: the idea takes no appendages of the report — no abstract, keywords, list of figures or tables, acknowledgements or table of contents, and no second copy of the report's chapter titles. The first sentence of each section is that section's conclusion, so a reader of first sentences alone still learns what each section holds.

Numbering: the idea and the report carry two numberings, one-to-one but never interchangeable. The idea's section numbers (1.1, 1.2, 2, 3 …) follow the argument; the report's (§1 Introduction, §2, §3.1 …) follow the prose. That the digits coincide is a coincidence, not an identity. The correspondence is registered section by section rather than inferred from equal numbers: each report section opens with `% SECTION <report number> <- thesis §<idea number>`, and each idea section ends with `→ report §<number>`. Change the numbering on one side and the other follows through the map, one side at a time; using an idea number as a report number, or the reverse, dissolves two tables of contents into one.

Distillation: the idea is the report distilled — not its abridgement and not an outline. The report may carry finer paragraphs, more transitions and more qualifications; the idea keeps only the conclusions, the grounds and where they stop. Both must hold at once: every report paragraph points back to an idea section, and every judgment in the idea has a landing place in the report. A judgment without a landing place is either moved out of the idea or written into the report — the idea does not keep a sentence the prose never cashed.

What arrives is a direction: cut the size, run a comparison. A direction cannot be written into the body and cannot be handed to an experiment — it has no truth value, and when it is done nobody can say whether it was met. This step turns it into answerable questions: one question, one criterion, so that answered and refuted are both decidable on the spot.

Its product governs three steps: paving leaves placeholders per question (1.3), running opens one experiment row per question (1.4), and drafting must trace every section's claim back to a question.

Actions:

1. Create one record per question in `tmp/compare-loop/<wish>/questions.json`; write `question` as a question, one thing per sentence.
2. Write `answered_if` and `refuted_if`: what would count as answered, and what would count as refuted. Each is one observable condition; "works better" is not one.
3. Write `section`: the section of the body where this question is answered. No landing place: `status: dropped`, with the reason in `note`.
4. Write `arms`: at least two mutually exclusive candidate answers — A lower, B lower, no difference. Fewer than two means the question can only come out one way, which is not a question.
5. Mark `provenance`: `user`, `prior`, `literature` or `ours`.
6. Write `pain_quote` as key plus the quoted sentence; without a quotation, keep `status: open` and write "to be confirmed" in `note`.
7. `needs_new` takes `yes` or `no`: whether answering it needs a new run. A `yes` row either has an experiment row in 1.4 or states why none exists yet.
8. How the rewrite is done: lift the verb phrase out of the client's sentence — "bring it down", "run a comparison" — and turn it into one yes-or-no or one comparison question; one direction yields several questions that do not depend on each other, and the ones that cannot be split record their order in `note`.
9. When the direction changes, rewrite rather than append: the affected rows get `question`, criteria and `section` rewritten in place, the old ones go `status: dropped` with `direction changed` in `note`, and `tmp/compare-loop/<wish>/invalidations.json` lists item by item the `pid`s, experiment rows and paragraph numbers that die with them. A `yes` row either has an experiment row in 1.4 or states why none exists yet.

One record, values illustrative:

```
{"qid": "q1", "question": "At equal budget, is A's error below B's?",
 "answered_if": "A's error is below B's by more than their run-to-run spread",
 "refuted_if": "A's error is not below B's, or the gap sits inside the spread",
 "arms": ["A lower", "B lower", "no difference"],
 "provenance": "user", "section": "4.2", "pain_quote": "<key> · <sentence>",
 "needs_new": "yes", "status": "open", "note": ""}
```

On-disk contract: file `tmp/compare-loop/<wish>/questions.json`; fields `qid`, `question`, `answered_if`, `refuted_if`, `arms`, `provenance`, `section`, `pain_quote`, `needs_new`, `status`, `note`. `status` takes `open`, `closed`, `refuted` or `dropped`. The invalidation list of a direction change: file `tmp/compare-loop/<wish>/invalidations.json`; fields `id`, `changed_qid`, `kills` (a list of `pid`s, experiment rows and paragraph numbers), `why`, `round`.
Written when: at the start of a round; a thesis change rewrites the row in place and appends nothing.

`qid` is the downstream `claim_id`: `footing.json` in 1.6, `claims` in 1.9 and the cross-section check in 1.9 all use it, and no second identifier is coined.

Criteria and breach: rows with a missing field number zero; rows whose `arms` hold fewer than two number zero; rows with an empty `answered_if` or `refuted_if` number zero. A row missing either criterion does not enter the question table, cannot supply a placeholder to 1.3, and cannot appear as a claim in the body. A `needs_new: yes` row with no experiment row in 1.4 and no explanation fails the pass.

### 1.2 Comparison and verdict

A set of finished pieces is the ruler, not a single one: the position comes from the set's distribution, never from one piece. Measured against one piece alone the only verdict available is "like it" or "not like it", which says nothing about where this draft stands.

Actions:

1. Build the set: pieces of the same register and the same page band go into `samples/`, each logged with its register and page count; where only one can be found, record why no set exists.
2. Measure each piece: one row per section per sample in `samples/<sample>.position.json`, carrying `gives` and `words`, `sentences`, `paras`, `cites_per_1000`.
3. Fold the range: one row per section in `samples/<set>.range.json` — `min`, `max`, `median`, `n`. A section whose `n` is one is a reference and never a criterion.
4. Write the position table: what each section and paragraph of this draft must deliver, taken from the range and from each piece's `gives`, never from one piece's wording. It lands in `tmp/compare-loop/<wish>/position/table.json`, one row per paragraph — `section`, `para`, `gives`, `words_target`, `cites_per_1000_target`, `source` (which row of `samples/<set>.range.json` it comes from), `order`.
5. Record the judgement: for the same section of this draft, judge where it sits in the set — below the floor, inside the range, above the ceiling — with a page or paragraph reference, into `tmp/compare-loop/<wish>/position/<sample>.json`.
6. Swap the set or move the floor: recompute the range whole, record which set and which range in `basis`, push the change onto `tmp/compare-loop/<wish>/stack.json`, and judge every finished section again — never only the new ones.

On-disk contract, three files:

- `samples/<sample>.position.json`: fields `section`, `gives`, `words`, `sentences`, `paras`, `cites_per_1000`, `basis` (which set and which range this row rests on).
- `samples/<set>.range.json`: fields `section`, `min`, `max`, `median`, `n`, `basis`.
- `tmp/compare-loop/<wish>/position/<sample>.json`: fields `section`, `judgement`, `basis`.
- `tmp/compare-loop/<wish>/position/table.json`: fields `section`, `para`, `gives`, `words_target`, `cites_per_1000_target`, `source`, `order` — which range row this paragraph writes to.

Written when: the per-piece rows and the range rows are written once the set is chosen; a new set or a moved floor rewrites both whole.

Criteria and breach: one row per section per sample, rows with a missing field number zero, one range row per section — a missing section fails the round. The position table holds one row per paragraph with a non-empty `source`; rows missing or carrying an empty source number zero, and the paragraph count of the body and the row count of that table differ by zero. A range that exists only as a string inside `verdict.target`, with no `samples/<set>.range.json` on disk, fails the round — a range with no file cannot be re-checked and is no ruler at all. A section with `n` of one states in `basis` that it is a single piece and no criterion; using it as a criterion judges the round invalid. A row with an empty `gives` is an idle row and enters the coverage row of 1.2.

Measure this draft against 1.2's ruler, item by item, and return pass or fail.

One baseline measurement follows the ruler at once — it records the starting point and is not expected to pass; every later round ends with another, measured the same way so the numbers compare.

Actions:

1. Compute `target` and `current` per row, for instance size, citations per thousand words, position coverage, literature gap, placeholder gap. How many are measured follows what this round needs to see, not a quota; anything extra gets a row of the same shape, and the count enters this round's `rows`.
2. `target` comes from the range in `samples/<set>.range.json` or from the index, and `target_source` records the path; the size row takes `min` and `max`, never a single piece.
3. `current` is measured a fixed way: size counts pages, words and floats in the built output; citations per thousand words divides through the body's word count; coverage compares position rows against `sections.json`, section by section; the literature gap counts `paper` rows and gap rows in `stack.json`; the placeholder gap counts `open` rows in `placeholders.json`.
4. `verdict` takes `pass` or `fail`.
5. Every failed row carries one `next`: `section`, `action`, `target`.

On-disk contract: file `tmp/compare-loop/<wish>/verdict/<round>.json`; fields `round`, `rows` (`name`, `target`, `target_source`, `current`, `status`), `verdict`, `next`, `readings` (two sets, `open` and `close`, of three integers each: the previous `verdict` value, open placeholder rows, open stack rows), `skipped` (step numbers not taken, with the reason).
Written when: the size row and the citation-density row of a section are measured and written the moment that section is finished; the remaining rows and the `verdict` follow at the end of the round. One round, one file.

Criteria and breach: rows in `rows` with a missing field number zero and rows with an empty `target_source` number zero; a row without a source does not count, and empty rows number zero. A row whose `current` has not moved for two rounds records `fail`, its `next` says `escalate: user`, and one row enters `tmp/compare-loop/<wish>/stack.json`. Each stack row carries `dedupe_key` (one row per gap) and `priority`; a pass pops at least one row, or it has not started. A `target` taken from this draft is void and is re-read; while `verdict` is not `pass`, the round does not close.

### 1.3 Laying the road

Plan first, place afterwards: which section answers which question, on which number, behind which section. The skeleton is written once that is settled. Laying without planning is writing whatever comes to mind, and what gets handed over is a collage.

Actions:

1. Order the argument: from the range file and the question table, write per section what claim it stands on, which `qid` answers it and what it waits behind, into `tmp/compare-loop/<wish>/plan.json`. A section with no claim is marked `no-claim` with the reason it stays.
2. Scout: for every number still missing, look for its supply on disk — the data, a runnable entry, the source on the shelf, a command that reproduces it. What exists goes into `supply` (path plus command); what does not goes into `gap` (what must be built, and by whom).
3. Build the skeleton: sections and their order follow the `section` sequence of `samples/<sample>.position.json`; no section absent from that file is added, and each section carries at least one sentence.
4. Leave placeholders: one row per missing number in `tmp/compare-loop/<wish>/placeholders.json`, and `% PENDING <pid>` on its own line in the body.
5. Entry raises: `raise NotImplementedError("<pid>: <waits_for>")` where nothing is implemented.
6. Mark state: `state` takes `open`, `filled` or `dropped`; a filled one moves to `filled` with the hash of its passage.
7. Record obstacles: a named paper with no repository, an unobtainable full text, compute or time running out, a run that fails after honest attempts — `note` records the obstacle and the routes tried, and one row enters the regurgitation list as 1.5 rule 8 requires; the placeholder stays `open` rather than being deleted for being hard.
8. Reserve a missing upstream section: compare this section's `gives`, the position table and the section order of the samples. When all three point at one section the idea does not have (present in the samples, present in the position table, absent in the idea), the gap is a high-confidence finding rather than a guess. Record a row in `plan.json` with `action: reserve`, naming where it sits in the idea, what it gives, and which section's prose will rest on it; record the same row in that round's `idea-feed.json` with `idea_section` holding the reserved slot. A reservation is not written at drafting time: the chapter is written, and the section is inserted into the idea at 1.10. Low-confidence gaps are not reserved — a reservation made on a hunch is harder to clean up than a missing section.

On-disk contract, two files:

- `tmp/compare-loop/<wish>/plan.json`: fields `section`, `claim_id`, `needs` (list of `pid`), `depends_on`, `order`, `risk`.
- `tmp/compare-loop/<wish>/placeholders.json`: fields `pid`, `section`, `waits_for`, `owner`, `question`, `supply`, `gap`, `blocks`, `state`, `note`.

Written when: planning and scouting finish before the skeleton is written, and both files are written when that section is settled; every placeholder state change updates its row at once.

Criteria and breach: every section has a row in `plan.json`, carrying either a `claim_id` or `no-claim`; a dependency cycle, or a section with no owner, fails the round. A `reserve` row fills `idea_section`, `gives` and the section whose prose will rest on it; a reservation missing one of the three does not count, and the number left unconsumed by 1.10 at the end of the round is written into `verdict` `readings`. Every open placeholder carries `supply` or `gap`, and one with neither is void. A row with an empty `owner` is void and its gap may not stay in the body. A `pid` list with an owner is the input list of 1.4: one open row maps to one experiment row or to one `blocked` note. An entry that reaches unimplemented code exits non-zero and prints its `pid`; an entry that writes an empty result file is rejected and rewritten.

### 1.4 Running for a number

Produce the numbers a drafting need requires: one number, one experiment, run until the number can be written into the body.

Position: a placeholder in 1.3 has no source for its number, and 1.5 holds no material for it — the run does not exist, or what exists is not enough.

Actions:

1. Fix the target: in that placeholder, state what the number must satisfy — which sentence uses it, under which four settings, and what magnitude counts as enough.
2. Before building the list, settle four things: interpreters and dependencies, where compute is reachable (this machine, a cluster, a scheduler), the experiment scripts and configs already there, the conventions for logs and result directories. Of these four, what exists is reused, not rewritten; what is missing is looked for in the project first, and only then built, with one stack row saying why.
3. Build the list: one row per experiment in `tmp/compare-loop/<wish>/experiments.json`, with `id`, `serves` (a `pid` or `claim_id`), `entry` (the command), `needs` (data, weights, compute), `expects` (which `number_key`), `state`.
4. Order the list: run first the one most likely to yield the target number in one go, the rest by dependency; `state` takes `queued`, `running`, `done` or `blocked`.
5. Run: get the smallest command to print one number first, then scale to the full set; `entry` is paste-ready in a clean environment; the number goes straight back into `tmp/compare-loop/<wish>/intake.json` and its placeholder turns `filled`; the row is rechecked by 1.5, and only then recorded `indexed`.
6. When it will not run, repair in place: dependency, path, seed, memory, data split — each repair appends one line to `fixes`. Three repairs in the same place without progress means a different route: another implementation, another dataset, a smaller scale; a smaller scale writes into `degraded` what was reduced and which criterion it affects.
7. A newly found problem goes onto `tmp/compare-loop/<wish>/stack.json`, and the next row starts at once; the pass never stalls on this one.
8. A `blocked` row carries three things — the objective obstacle, the routes already tried, and the adjustment proposed (lower the expectation, change a setting, rewrite the narrative, change the sample) — and pushes one row into `tmp/compare-loop/<wish>/regurgitation.json`. Shrinking the target quietly does not count as an adjustment; only the written one does, and shrinking it unwritten is cutting corners.

Not allowed: "it has been run" reported without a number; a nearby number standing in for the target; a criterion bent to fit the result; a reduced scale left unrecorded; an unfinished run recorded `done`.

On-disk contract: file `tmp/compare-loop/<wish>/experiments.json`; fields `id`, `serves`, `entry`, `needs`, `expects`, `state`, `number_key`, `fixes`, `degraded`.
Written when: the list is built; every finish, failure or route change updates its row immediately.

Criteria and breach: every row carries a `state`. A number an order of magnitude away from the same-setting literature sends the setting back for a check before it is believed; where no cause is found, the row takes `suspect` and one stack row. A `done` row must have its counterpart in `tmp/compare-loop/<wish>/intake.json`, or it fails the pass and returns to `running`. A `blocked` row states what is missing and who supplies it. Closing criterion: every placeholder covered by this drafting need holds a `filled` record, or is `blocked` with its gap named item by item.

### 1.5 Intake

Register the results as an index: which file holds each number, which run produced it, under which settings it is read. Results are not re-run; intake is checking and indexing, not reproduction. Material has two sources — what the client handed over at the start, and what 1.4 produced; both are registered with the same fields, and the rows 1.4 writes back are rechecked here.

Actions:

1. Open every item and look at its contents: a table at the cell, a figure at the annotation, a log at its last lines. Registering from a file name or a directory name counts as not done.
2. Create one record per item in `tmp/compare-loop/<wish>/intake.json`: which number it yields, which version or run produced it, and the four settings it is read under (`dataset`, `split`, `metric`, `budget`).
3. Check the settings one by one. Each of the four points at the sentence in the body that will use it and at the figure it becomes; all four pointing somewhere records `state: indexed`, one that points nowhere records `incomplete`, contents unreadable records `unreadable`.
4. Check each item sensorially and land every check on a place: which page the number sits on, which row and column of which table, and how far apart the two numbers are; whether the heading's wording is the same word as the column name; the sample size as written and the magnitude the claim sentence uses; whether pages and row numbers run without a gap. The result goes to one `flags.json` row — `where` names page and cell, `evidence` names the two numbers.
5. On fabrication, omission, weakness or doubt: `state: suspect`, plus one row in `tmp/compare-loop/<wish>/flags.json` — `kind` as `fabrication`, `omission`, `weak` or `doubt`; `where` and `evidence` (page, cell, the command line as typed); `needed` (what would settle it).
6. A suspect item never becomes a conclusion in the body. Mentioning it has one condition — a matching `flags.json` row: the body writes `% PENDING <pid>` plus "to be confirmed", and `pid` points back at that row. No row, no mention.
7. Where the target number is absent from disk, or present but unusable, go to 1.4 and open one experiment row for it.
8. A number that contradicts a claim of this draft is registered like any other, the same `qid` takes `status: refuted`, and `tmp/compare-loop/<wish>/regurgitation.json` gets one `kind: conflict` row carrying where the number sits, the claim sentence as written, and the affected paragraph numbers. Hiding the counter-example is not allowed, and neither is bending the claim to fit a number that has not been rechecked.

On-disk contract: file `tmp/compare-loop/<wish>/intake.json`; fields `id`, `what`, `path`, `source_version`, `number_key`, `setting`, `state`, `evidence`, `note`; `state` takes `indexed`, `incomplete`, `unreadable` or `suspect`. File `tmp/compare-loop/<wish>/flags.json`; fields `id`, `kind`, `where`, `evidence`, `needed`, `raised_to`, `state` (`open` / `answered` / `closed`).
Written when: each item is written the moment its check ends; rows written back by 1.4 take `state` after review.

Regurgitation list: file `tmp/compare-loop/<wish>/regurgitation.json`; fields `id`, `kind` (`conflict` / `impossible` / `expectation` / `basis`), `where`, `tried`, `proposal`, `needs_user`, `state` (`open` / `answered` / `dropped`). Anything that cannot move forward because of an objective obstacle or because it contradicts a claim lands here, and it is raised with the delivery before the worker retires.

Criteria and breach: one row per item, `state` present, `setting` and `evidence` filled. An item registered without being opened is not done and is registered again. A `suspect` row without its `flags.json` counterpart fails the pass. Re-running an experiment in place of checking its settings is treated as cutting corners, unless the user asked for the re-run.

### 1.6 Admitting numbers

Only numbers that can be checked alone enter the body: who produced it, under which settings, what it can be read against, and which sentence carries it.

Actions:

1. Admission: rows are built only for numbers 1.5 reviewed as `indexed`. A number `incomplete`, `unreadable` or `suspect` never enters the body; one already there is withdrawn and a stack row opened.
2. One row per number in `tmp/compare-loop/<wish>/footing.json`, `claim_id` naming the `qid` it answers and `section` naming where it lands.
3. `source` holds the file path plus the producing command; a number whose command cannot recompute it takes `not-reproducible` and stays out of conclusion sentences.
4. `setting` carries the four fields — `dataset`, `split`, `metric`, `budget` — taken from the intake row rather than written afresh.
5. Units and digits: `unit` names the unit and `scale` the conversion (percentage, per-mille); the body never rounds to a different number of digits than `value`.
6. Derived numbers: an average, a difference or a percentage carries `derived_from` (the `footing` rows that entered it) and `formula`; one without both stays out of the body.
7. `against`: the comparison key plus its four settings. The search is fixed — the same section first, then the shelf by `metric` and `budget`; where neither yields one, `not-seen` with the searched range in `note`, and four settings short or mismatched also takes `not-seen`.
8. `line` names where the number appears — paragraph, float or abstract — and numbers inside figures, tables and the abstract get rows too; being drawn on a figure is no exemption.
9. Consistency: the same number reads identically in abstract, body and table; `value` governs — the body is corrected around it, and changing `value` follows rule 11.
10. A number whose `against` is `not-seen` carries no comparison in the body — higher, lower, better, compared with, close to are all barred — and stays out of the conclusion.
11. When a number is re-run or corrected at intake: the old row takes `state: superseded` and keeps its `round`, the new row carries the new `round`, and the body moves to the new row; two rows never stand available for citation at once.
12. A number that cannot be produced is judged for runnability first — runnable goes to 1.4 as an experiment row; not runnable pushes one row into `tmp/compare-loop/<wish>/stack.json` and the next placeholder is filled without stalling.

On-disk contract: file `tmp/compare-loop/<wish>/footing.json`; fields `claim_id`, `section`, `value`, `unit`, `scale`, `source`, `setting`, `against`, `derived_from`, `formula`, `status`, `state`, `line`, `round`. `status` takes `seen`, `not-seen` or `not-reproducible`; `state` takes `current` or `superseded`.

Written when: before a number enters the body; a correction appends a new row and marks the old one `superseded`, never editing it in place.

Criteria and breach: every number in the body has one `current` row with a matching `value`, and the paragraph or float its `line` names exists — a miss fails the round. A derived number recomputes from `derived_from` and `formula`, and a mismatch voids it. A `source` that will not run while `status` is not `not-reproducible` judges the step undone. Comparison sentences in the body may not outnumber the rows whose `against` is not `not-seen`. A `suspect` or `superseded` number appearing in the body is recorded `dirty` by 1.9.


### 1.7 Thickening

Add literature and narrative detail. Fixed order: look up, fetch, convert, read, file, stack.

Actions:

1. Look up the shelf by `key`, by title, by DOI. A hit is used as is and never downloaded again.
2. Fetch the full text: if an interface for full texts exists (a search API, a preprint source, an institutional repository), or the project already holds the text, take it from there rather than from a browser page; only where no interface exists are the routes tried by hand, publisher page, preprint server, author page, institutional mirror in that order; a channel that fails is replaced by the next at once; do not wait on one.
3. Convert on arrival: if the ecosystem has a parser that keeps tables, captions, formulas and section headings, use it to produce the structured text beside the source under the same `key`; if it has none, one stack row records the substitute adopted. That text is the reading copy. Screenshotting page by page, retyping, or scanning the PDF by eye judges the step undone.
4. Read the whole text: locate by search in the parsed text, read the method and results sections, transcribe the four `setting` fields and the four `comparison` fields and note the pages they sit on; a paper earns a citation only when it moves a claim this section already makes — otherwise it is recorded as `cites: background` and takes no argument slot; every quoted sentence is copied verbatim from the body, never from the abstract, never paraphrased.
5. File: write three places in the same pass — `literature/meta/<key>.json`, `literature/notes/<key>` (a record file, format as the project keeps it), one index row.
6. Stack: an unobtainable full text, a missing setting field, an absent reproduction entry, a newly found problem — each writes one row into `tmp/compare-loop/<wish>/stack.json`, and the next entry is taken immediately; one entry never halts the pass.
7. A batch arriving at once is worked as a batch: deduplicate by `key`, DOI and title, file each item, then rebuild the index and check the count; a duplicate keeps one row and records the other path in `note`.
8. Every filing writes one citation entry at the same time, into whichever citation library the template uses: `key`, authors, title, year, venue, DOI or URL. That library is the single exit for citations; the body cites keys and never types entries by hand.

On-disk contract: file `literature/meta/<key>.json`; fields `key`, `title`, `venue`, `year`, `locator`, `status`, `input_class`, `setting`, `comparison`, `reading`, `purpose`, `cites`, `verified`, `note`. `status` takes `held`, `held-method-only`, `held-unverified`, `requested`, `not-obtained`; `setting` carries `dataset`, `split`, `metric`, `budget`. Stack file `tmp/compare-loop/<wish>/stack.json`; fields `id`, `kind` (`paper` / `setting` / `entry` / `defect`), `opened_by`, `what`, `criterion`, `owner`, `state` (`open` / `done` / `dropped`).
Written when: every filing writes its three places in the same pass; a stack row is written the moment it appears.

Criteria and breach: the three locations agree in count; a disagreement is repaired in the same pass and the repair recorded in that key's `note`. A record whose `status` is not `held` supplies no number. A record with only an abstract and no body is `held-method-only` and supplies no number. A full text that could not be obtained and left no stack row fails the pass. Only after every channel has been tried does a `requested` row appear, and it is raised to the user in one message together with the rest. An `open` stack row is never deleted for lack of time; only `done` or `dropped` closes it.

### 1.8 Drafting

Write the sentences the position table calls for, and leave the places with no number as placeholders. Drafting is for a reader, not for handing in: read how others wrote this kind of paragraph before the first sentence, and read the paragraph back as a reader when it is done.

Actions:

1. Read the others first: for each paragraph this section will hold, read a paragraph of the same job in the sample set, sentence by sentence — not the `gives` summary but the sentences themselves, and say what each one does (states the conclusion, gives the basis, names the cost, draws the boundary, hands over to the next paragraph); a paragraph whose moves cannot be named has not been read. One row per paragraph read goes into `tmp/compare-loop/<wish>/voice.json`: `section`, `para`, `sample`, `page`, `move` (what this step does), `pattern` (ten to thirty characters copied verbatim — the sentence shape or the turn), `use` (which paragraph of this draft, and which step, follows it).
2. A `pattern` must be findable in the sample's own text; one that cannot be found is void — a paraphrase from memory is not reading. If the reading still leaves no sentence shape for this paragraph, read another sample; never start from "roughly like this".
3. Then read the writing conventions: the writing entries in project memory and the sample's `gives`, and carry what transfers into the sentences — an abstract follows five moves (state, gap, method, finding, boundary) as one page of prose, an introduction follows three (establish, gap, this work), length and citation density follow the measurement convention, and citation format follows its single source. Where a convention and the sample disagree, the sample's position wins and one line goes into `note`.
4. Write one paragraph per row of `samples/<sample>.position.json`; the first sentence of each paragraph carries that paragraph.
5. How a paragraph opens: the first sentence states the paragraph's conclusion and names its object, the second gives the basis — a number, a source or a comparison — and the rest carry cost and boundary; one paragraph makes one point, and past the `sentences` figure on that row of the position table it is split.
6. Where the paragraph needs a number of this draft that is not on disk, write `% PENDING` and create a row in `tmp/compare-loop/<wish>/placeholders.json` naming `waits_for` and `owner`.
7. Mark every finished paragraph's source: a claim, a citation key, or a row of `tmp/compare-loop/<wish>/footing.json`. A new claim first gets a row in 1.1, then its sentence.
8. Take structural and positional problems back to 1.3 and 1.2; do not change structure while drafting.
9. Write where the instruction points: the body goes into the directory and file names the client named — the ones the project's own architecture already holds — never a path invented along the way and never a parallel tree. With no location named, follow the existing structure; ask once only when no structure exists, and from the answer on, keep it fixed.
10. The template governs: write inside the commands, environments and styles the template provides; a change to the template's preamble gets a row in `tmp/compare-loop/<wish>/stack.json` saying why it cannot be avoided; floats and other display objects use the environments the template already defines; file names and the include hierarchy follow the template rather than a new hierarchy.
11. Compile after every section: errors and warnings go to zero before the next section starts, and a draft that does not compile is not a draft. Where the template's requirements and the project's directory conflict, satisfy the template so it compiles, keep the location as instructed, and put the conflict into `tmp/compare-loop/<wish>/regurgitation.json` for the client to settle.
12. Read it back: first as the author — every sentence points at the claim, the key or the number it carries; then as a reader — what does this sentence tell me, and what am I left to guess. A sentence that leaves something to guess gets a row in `stack.json` and is rewritten on the spot, then read again; both passes are recorded in `read_back` of `voice.json` (`author`, `reader`, `guessed`).
13. Write one section at a time: the moment a section is finished, measure it in 1.2B against its position row — words and citations per thousand words — and do not start the next section until it holds.
14. Write prose by the paragraph, whole: a paragraph added or rewritten goes into the file as a paragraph. Scripts, `sed` and string replacement that patch sentences inside the body are not allowed — sentences assembled that way have no author, and they read like a machine wrote them.
15. Register: the body is academic written prose only — declaratives in the third person, each sentence carrying a claim and its evidence in the same breath. Four families are banned: slogan-like antithesis ("the first fails, the other two lose their footing"), metaphor and personification ("loses its footing", "only a slogan"), spoken connectives and hedges ("basically", "obviously", "we feel"), and advertising adjectives ("significantly boosts", "far superior", "greatly relieves"). After delivery, grep the banned list; the hit count must be zero.
16. Four hard edges of register, each countable: one, declarative sentences only, one claim per sentence, mean length 45 words or fewer for the section and any sentence over 60 split on the spot; two, third person only — "we", "our" and "I" are rewritten as passive or unnamed subjects; three, tenses split by job, present for the method and past for runs and readings, never mixed inside a section; four, every sentence carries its evidence (a key, a number, a derivation) or is deleted — sentences without evidence do not enter the body, including transitions and postures. Paragraphs add three: the first sentence states the conclusion and names its object; one paragraph serves one claim; no bullet marks, and no template connectives such as "firstly", "secondly", "in this section". Register is not style: a sentence without evidence cannot be checked, and drifting person and tense make method and result indistinguishable.
17. Look through the draft as a white box before looking at the linkage. Three questions in order; no answer, no writing: one, does this paragraph belong in this document — right place, right grain against its neighbours, and nothing pulled in from a section that owns it; two, does the claim land — a key, a number or a derivation, or it is deleted; three, which region of the idea will this feed once written. The first two are about the document alone; the third is the linkage. Decide whether the section stands on its own before deciding what it sends back — the other order writes prose for the sake of the feed.
18. Drafting feeds the idea, and the idea is located by sense. The moment a section is finished, send the result back to its region: locate by content — the heading, the section's `gives`, the opening sentence's claim — never by matching numbers (idea §3 and report §3 are different things, see 1.1). Every row in `idea-feed.json` carries `located_by`, naming the sentence or heading that located the region. Before sending, confirm three slots: the intake inputs (the `intake` rows of 1.5), the footing slots (the `footing` rows of 1.6), and the code environment (which package, which command, which seed). One missing stops the round until it is filled; prose does not go on over a gap.
19. What the feed turns up is triaged. A single-point problem — a wrong key, a number that does not reconcile, a sentence filed under the wrong section — is fixed on the spot: same round, re-run, state rows updated. A systemic problem — a whole section missing from the idea, numberings misaligned across the board, an argument chain with no landing place in the prose — is not fixed in this round: it goes into the delivery report under "systemic problems", with its symptom, its reach and the action it needs, delivered with the round. A round that does not report a systemic problem leaves it to be rediscovered next round.
20. Read the two neighbouring sections before writing, and state each seam in one sentence: the new paragraph catches the end of the one before it and hands its own end to the next; a seam nobody can read is a break, and a break is mended by changing the seam rather than adding a transition. Neighbouring faults are fixed on the spot — a point made twice, a conclusion before its grounds, an unbroken long paragraph, a stale number — with `path:line` in the delivery, never filed as a todo.
21. No comparison table, no draft: two columns — the readings of comparable published prose (which papers, sentences per entry, citations per thousand words, how many statements of what was left, and how each was counted) and the same readings for this section, counted the same way. Without the table what changes is wording, not prose.
22. No number without a source: `path:line`, and for corpus statistics the file, the pattern and the denominator. A number inherited from upstream is re-checked the same way — one bad figure upstream is then copied into the feed, the readings and the body.
23. Register is checked by a countable list: scene-setting openings ("a shopper stands before…", "imagine you…"), rhetorical questions, first person, colloquialisms, imperatives — each counted, and the count must be zero.

On-disk contract, two files: `tmp/compare-loop/<wish>/sections.json` (where the section lands, and its hash) and `tmp/compare-loop/<wish>/voice.json` (one row per paragraph: `section`, `para`, `sample`, `page`, `move`, `pattern`, `use`, `read_back`); `sections.json` fields `section`, `hash`, `claims` (claim ids in that section), `placeholders` (list of `pid`), `file` (the file this section lands in), `round`.
Written when: once per section written, updated section by section, never rewritten whole.

Criteria and breach: sentence count and citation density are counted against `sentences` and `cites_per_1000` in the position row — those two are the contract edge and stand in for nothing below. Hits on the banned register list number zero; the list is the one in step 15. Every paragraph holds a `voice.json` row with a non-empty `page` and `pattern`, and paragraphs missing one number zero; rows whose `pattern` cannot be found in the sample's text number zero; paragraphs short of a `read_back` field number zero. Two or more in-place sentence patches in one paragraph fail the round, and that paragraph is rewritten whole. The first sentence is copied out on a line of its own; if that line says what the paragraph is about and which sentence is the conclusion, it passes, otherwise the paragraph is rewritten. What is judged is the copied line, not the length of the paragraph. A sentence without a source is recorded `unsourced` by 1.9 and is deleted or demoted to a placeholder.
24. The idea follows the paper's own subsection shape, not a scaffold: each chapter `## N. Title` holding `**N.k Subsection**` items that open with a claim and read as the skeleton of prose. Label lines such as `Job`, `Narrative arc`, `Potholes` must appear zero times: they are my notebook, not the paper's way of writing.
25. Skeleton before colour, across the whole manuscript: every chapter has its skeleton subsections in the same round, and "this round only the first sections" is not a skeleton. Chapters without a skeleton must be zero.
26. Potholes close the chapter: the last subsection is "Open items and where the readings come from", one line per missing item naming the runnable entry that fills it (`PENDING(fill: <entry>)`). "To be filled", "later", "will show" standing in for `PENDING` must be zero.
27. Paving is a sentence, not a tag: the chapter ends on the interface of the next chapter's first sentence, worded as handing over. Tag-style `Paves` lines must be zero, and the seam is checked by reading the last sentence of one chapter against the first of the next.
28. Open the full texts before claiming a benchmark: at least three papers, reading the title sequence, the opening paragraph, the first result sentence and the limitation sentence, and writing all four into the readings. A claim of benchmarking supported only by regular expressions must occur zero times.
29. Reading a paper means four things: the `<title>` sequence (the real names of chapters and subsections), the first paragraph (how the problem is opened), the first result paragraph (what is reported first), and the limitation sentence in the discussion (where limits live). Fewer than four is not reading.
30. Citation state lives in `references.bib` alone, one `% footing:` line per key. Any use of "benchmark" in a reply must be accompanied by a paper title and a `path:line`; missing either means the paper was not read.
31. The shelf's shape is a contract: one paper, one flat package, holding only the body (`paper.pdf` or `paper.xml`), the reader output (`chapters/`) and `meta.json`. Group folders, `README`, `INDEX` and `tools` inside a shelf must appear zero times; an index is either generated outside the shelf or does not exist.
32. Write the names down before moving anything: every move or rename is listed as old-name to new-name in that round's readings, and the list is checked afterwards. Moving without a list must occur zero times. A symlink is a copy, the body has one home, and links are verified the moment the move finishes.
33. Destructive tidying runs dry first: print and count what will be deleted or moved, then execute; anything irreversible is copied outside the repository first. Deleting without a copy must occur zero times.
34. A package is the smallest citable unit: if it has no body (`no paper.pdf`) or no reader output (`reader: none`), the numbers it would support may not enter the prose. Every cited number must point at a package with all three parts.
35. Point at the shelf before citing: every key is first found as a package on the shelf (directory name or `meta.title` matching the key's author and year). Not found means not written. Keys written without a package must number zero, and each key in the prose must be traceable in the readings to `workspace/literature/<package>/`.
36. A first-hand citation has three parts: body, `chapters/*.md`, and `meta.json`, plus a `path:line` inside `chapters/` given in the reply and the readings. A package missing any part may only appear as `PENDING(fill: <entry>)`, never as an established number.
37. Stop when the shelf is a mess: any of these counts as mess — group folders, `README`/`INDEX`/`tools`, empty directories, a package name that does not match its title, a `meta.title` that is a placeholder (equal to the package name or ending in `· 01_source`), a broken link. No comparative drafting begins while the mess stands; tidying and drafting never share a round, and the tidying round delivers readings only, no sentences.
38. Tidying invents nothing: no new ledgers, no empty `chapters/`, no `notes.md` passed off as reader output, no regular-expression counts passed off as reading. A tidying round reports four numbers — packages, packages with all three parts, packages without a body, packages unread.
39. The shelf's mess is a task, not an excuse: the readings open with one fixed line, "shelf: packages N / complete M / no body X / unread Y". Rounds without that line must number zero, and while it is absent every comparative sentence in that round counts as unverified and may not be cited.
44. The package name is the citation key: a literature directory's name equals its `references.bib` key character for character, and access is one path, `<literature>/<key>/`. Names that disagree with keys must number zero; a rename changes both in the same round, with the list recorded in the readings.
45. Shelf and bibliography mirror each other: every package has an entry under the same key, and every `held` or `shelf-only` entry has a package of that name. `not seen` marks only keys the bibliography knows and the shelf does not, and those may not carry a claim of having been read. The difference on either side must be empty.
46. Split to the bottom: the tidied tree holds no subdirectory with twenty or more mixed entries and no transit folder named `v1_patched`, `misc` or `old`; both counts must be zero.
47. No bins: `find <package> -type d \( -name '_deprecated' -o -name '_misc' -o -name '_tmp' \)` prints nothing, and every file under the temporary area's `unrecognized/` carries one line saying why it could not be classified.
46. Hand-off products live under `tmp/` only: case products go to `tmp/reproduce-test/<id>/out/`, and the only other `out/` in a repository is a rebuildable data product (`00_data/build/out`) kept out of version control. A third `out/` is pollution and must number zero.
47. A figure starts from a sentence, not from data: write down the sentence it carries (with a `path:line` in the readings) before drawing; a chapter with no figure must number zero.
48. Three files per figure: vector PDF, 300 dpi PNG, and a caption kept beside it. The caption's first sentence is the figure's conclusion, the second gives the reading and n. The re-run command lives in the package's `figures.py` docstring, not in a separate note.
49. Figures come from a package, never from a scratch script: one command in `<package>/figures.py` redraws all of them into `<package>/output/figures/` and `report/final/figures/`. Figures with no re-run entry that reach the prose must number zero.
46. The package name is the short key: a shelf directory's name is also its `references.bib` key, in the form author-year or a run of title words, lowercase, `a-z0-9` only, at most 32 characters, unique across the shelf. One work keeps one package; duplicates are absorbed and removed. The old-to-new list is written into the readings before any rename, and afterwards the difference between directory names and bib keys must be empty.
47. Literature has one address: `<literature>/<key>/`. Prose citations, intro documents, script constants, run records (`run.json`, `summary.json`) and reader output all use it. Paths that no longer resolve must number zero; a historical record that still points at the old layout either moves to the new key or marks the field `path_at_run`.
48. The key map comes before the rename: the round builds old-key to new-key, every old key in the prose and the intro must appear in it, and an old key with no landing place is either dropped or given a package that round. Unresolved keys must number zero, and renaming, mapping and re-citing happen in one round, never across rounds.
49. Loop products live under `tmp/compare-loop/<wish>/`: readings, feeds, state and drafts all sit in that one directory, and a `loop/` at the project root must number zero. No relative paths: a citation reads `<project root>/tmp/compare-loop/<wish>/<file>`.
50. `tmp/` is not versioned, so nothing kept there counts as delivered: each round's `readings.md` and `feed.json` must write their conclusions back into the prose or the idea document within the same round (`1.10`). A feed that exists only under `tmp/compare-loop/` counts as not fed.
46. This clause sets no threshold of its own: key shape and length follow `1.8-56` only (`<first author surname><four-digit year>`, at most 20, year last), and any older wording that disagrees is void. What remains here: one work keeps one package, duplicates are absorbed and removed; the old-to-new list is written before the rename, and afterwards the difference between directory names and bib keys is empty.
52. No audit lives only in the reply: every round that inspects the shelf lands as `tmp/compare-loop/<wish>/readings.md` (intake, comparison, drafting, checking, feed) plus `feed.json` (each row carrying `located_by` and `downstream`). An audit that exists only in prose counts as not performed, and such rounds must number zero.
53. Two identities, one content rule each. A container package that holds subpackages: its own level holds subpackage directories only — loose files zero, non-subpackage directories zero; no `README.md`, `data/`, `common/`, `tools/`, `docs/` or `config/` may sit there. A note belongs in each subpackage's own `README.md`, data belongs in the subpackage that reads it. A leaf package holds exactly four slots: `src/`, `conf/`, `out/`, `README.md` — `kit/` lives inside `src/` because a copied tool is source; what sits beside `src/` is `conf/` (parameters) and `out/` (products), never `kit/`. One directory carrying both identities is a breach, and such directories must number zero.
54. Numbers have one shape: `NN_name` at the top (two digits), `NN.M_name` on the second level inheriting the parent number, `NN.M.K_name` on the third; children number consecutively under the parent, no gaps; a file's number matches its directory. Renaming updates every reference and re-runs once in the same round, with the rename list in the readings.
55. Junk has a list: `.DS_Store`, `__pycache__`, `*.pyc`, `*.log`, `*.tmp`, `*.bak`, `*~`, `* 2.*`, dated snapshots such as `results.<date>.*`, `.ipynb_checkpoints`, empty directories. Print the list before deleting, record the count afterwards; upstream clones live only under `_upstream/` with source URL and commit.
56. Results sit in their own place: source writes only its own `out/`; `out/` holds only what one command from `src/` rebuilds, plus a `MANIFEST.json` (command, time, inputs); a hand-edited product goes to `out/manual/` and is named in the readings.
57. A shared layer is a breach of the layer package, not an optimisation: no level may hold `common/`, `core/`, `shared/` or `tools/` directories; shared logic exists only as a copy at `<package>/src/kit/`, whose `__init__.py` opens with where it was copied from and when, after which each copy diverges freely. Lifting logic to a layer to save a few lines counts as a breach, and such directories must number zero — one copy per package is preferable, because only then can a single package be audited, a reproduction case be scoped to it, and a change leave the neighbours untouched.
58. A package lands on the idea first: every package has one row in `tmp/compare-loop/<wish>/packages.tsv` with four columns filled — `package` (the directory), `idea` (the section number and title it supports), `slot` (the place the result feeds, as a section of `report/final/<number>.<name>.tex`), `product` (the file under `out/`). Rows with any column empty must number zero.
59. What cannot be located is reported, not tolerated: a package whose `idea` cell cannot be filled goes into `stale.tsv` (`package`, `last_touch`, `reason`, `disposition`: absorb, move to `_upstream/`, delete), and the readings open with one line "unlocatable N". New package work does not start while `stale.tsv` is non-empty.
60. Stake the hole before building the package: before a new package exists, write three things — the sentence in the idea that needs it, the `\ref` in the manuscript waiting for it, the file name that will appear under `out/`. Missing any one, the package is not created; the hole is written as `PENDING(fill: <package>/out/<file>)` and replaced in the round the package lands.
61. Intake and holes reconcile in the same round: the product in `out/`, the `PENDING` in the manuscript and the section in the idea must agree letter for letter in number and file name; disagreements must number zero. When a package is renamed, its row in `packages.tsv` and its placeholders move with it; renaming the directory alone fails `1.9-40`.

62. Tidying has states, and the states live in the name: four reserved prefixes carry them — `_upstream/` (an outside clone, with URL and commit), `_deprecated/` (kept as evidence, never cited), `_staging/` (untidied, may not be cited), `_shared/` (cross-package, origin noted). Every other directory name says what the package is, not how far it has been tidied; a state word inside a normal package name must number zero.
63. A tidy lists before it moves: over the given root — the whole `workspace`, one container, or a subdirectory inside a leaf — walk it recursively, judge every bottom package as `ok`, `nonconforming` or `not-a-package`, and write `tidy.tsv` (`path`, `kind`, `state`, `evidence`, `plan`) before touching a byte. A round that moves first counts as not done.
64. A tidy runs one package at a time: take one `tidy.tsv` row, finish it, retake three readings (top-level entry count, entry exit code, sha of `out/`), then take the next. Batch moves are allowed only inside one parent, and only with `git mv` recorded.
65. A tidy proves it changed nothing that matters: a `sha256` list and the entry output are taken before and after, and the numeric difference must be zero; only three columns may differ — path, file position, row order. A non-zero difference rolls that package back and records an `impact` row; "it looks the same" is not a pass.

66. A subdirectory passes four questions before it counts as a subpackage: does it have its own entry (one command producing its own product); does it own an `out/` whose numbers some section of the idea cites; does it hold its own row in `packages.tsv` with `idea` and `slot` filled; is its code anything other than a variant of the parent's (same script name, same imports, only configuration differs). All four yes makes it a **subpackage**; configuration only, or no code at all, makes it an **arm**; code without a product that duplicates the parent's entry makes it a **residue**; no code, no product, one note — the note folds into the parent and the directory goes. The verdict goes in the `kind` column of `tidy.tsv`.
67. Numbers belong to real subpackages: the `NN.M.K_` level holds subpackages only, and an arm or a residue never takes a number — an arm folds into `conf/` (one file per configuration), a residue goes to `_deprecated/` or is deleted. Directory names containing `arm`, `branch`, `old`, `bak` or `tmp` must number zero; that state is carried by the `_` prefix and by position under `conf/`.
68. Arms and residues name their destination: a `kind=arm` or `kind=residue` row carries `folds-into:<target file>`, `deprecate` or `delete` in its `plan`, together with which file was absorbed. After the round those directories must number zero; an empty directory left behind, or the same configuration copied into both the arm and the parent, counts as not handled.
69. A tidy splits to the bottom; moving a heap into one folder is not a tidy: a directory that still holds "one subdirectory with twenty or more mixed entries" or "a transit folder named `v1_patched`, `misc`, `old`" counts as untidied, and the count must be zero. The test is that every entry lands in one of the four slots or the project's temporary area — there is no fifth destination.
70. What cannot be classified leaves the package: anything whose kind is unclear — source, parameter or product — moves to the temporary area's `unrecognized/`, name kept, with one line saying why it could not be classified. No `_deprecated/`, `_misc/` or `_tmp/` may sit inside a package as a bin, and such directories must number zero.
71. Filing instead of classifying counts as idling: a tidy has four moves — into a slot, folded into an existing file, out to the temporary area, deleted with authorisation. A fifth move, "collect it into a folder for later", makes the package untidied and bars an `ok` row in `packages.tsv`.
72. Tidying and audit both return to the idea: every package gets a row in `anchor.tsv` whose `idea` reads `毕设立意.md:<line> 第 N 节`; every product under `out/` hangs off that row, and `anchor` holds `anchored` or `no-anchor` only. A `no-anchor` product may not be cited as a conclusion or enter the body.
73. High-confidence debt is cleared at once, any one of three hitting: the input a product cites no longer exists; one metric differs from the current `out/` by an order of magnitude with no rerun record; the filename carries an old date while every number in it is a placeholder. A hit moves to the temporary area and is recorded `deprecate` in `tidy.tsv`; a doubt that misses all three goes on the delivery's "suspect products" line, never left silently in `out/`.
74. In-package sanity and mergeability are counted: files under `src/` and their import edges (`grep -c '^from\|^import'`); two directories importing each other, together under 200 lines, with no consumer beyond one entry point, count as mergeable, and the plan goes to `audit.tsv`'s `merge_plan`. Readability has one test — after the merge the entry still runs on one command.
75. `out/` holds four kinds only: `results.json`, `MANIFEST.json`, `runs/<run>/seed<NN>.png`, `manual/<original name>` for hand-edited files. A delivery note with `.md`, a snapshot with an old date, an ad-hoc csv — none may sit at the top of `out/`: notes go to the delivery, snapshots to `manual/`, the rest to the temporary area.
76. A deletion carries an evidence card first: every removed file or directory records three things in `tidy.tsv`'s `evidence` — the verdict (`stale` / `fake` / `unreferenced`), the command that read it, and the impact (how many files cited it). Missing one of the three bars the deletion; the delivery lists what went, by class and count.
77. `src/` is refactored along the idea's lines, not merely merged: `module_map.tsv` holds one row per module (`module` / `idea` / `duty` / `entry`), `idea` reads `毕设立意.md:<line> 第 N 节`, `duty` is one sentence on what that module does for the idea; a directory whose name is a dataset while its content is code is renamed by its `duty`; the only entry is `src/run.py`. After the refactor the entry exits as before and each `out/` product keeps its sha, and both readings go back to `audit.tsv`.
78. A number is the level, and no digit may be dropped: the layer root reads `0x_`, the second level `0x.y_`, the third `0x.y.z_`, two digits per segment with the parent's number first; `1.1_` or `1.10_` fails on both counts. Siblings run without holes, and a hole has two lawful forms only — a `_staging/0x.y_<note>` placeholder, or a line in `gaps.tsv` giving the number, the reason and the round that fills it. A hole with neither counts as untidied.
79. Literature and notes found inside a package are routed on the spot: literature (a pdf or md with authors, year or DOI) moves into the literature library and gets a `refs.tsv` row, leaving zero `*.pdf` inside packages; notes (`summary.json`, `run.json`, trial pngs, `try_*.py` and the like) never serve as in-package evidence — they become the `README.md` "observations" section: one sentence of observation, one of condition, one of conclusion, citations written `[@key]`, the rest moves to the temporary area.
80. Building and intake are one action in two directions: when a package is built (`2.10`) the first step writes `README.md` with four parts — the idea section it answers (with the line), the command that runs it, the product it leaves, and an "observations" section holding `PENDING(obs)`; when it is intaken (`2.13`) that section is aligned with `anchor.tsv`'s `idea`, and a missing reference gets a `refs.tsv` row, with the entry added to `workspace/literature/` when the shelf lacks it — metadata only, never an abstract.

### 1.8A Eight hand-offs, six fields each

A hand-off is one "who gives what to whom". With an incomplete contract it degrades into "I assumed you had it". Each hand-off below carries six fields: trigger (when it starts), product (its name and place), criterion (the command and the line it is read from), failure path (who stops and does what). A hand-off with an empty field may not be reported as complete in that round.

| Hand-off | Trigger | Product | Criterion | Failure path |
|---|---|---|---|---|
| commission to idea | the owner states this round's single goal | the matching section of `workspace/<project>立意.md` | section count equals the map's; empty sections 0 | more than one goal: stop and ask once, never guess |
| idea to report chapter | a chapter's skeleton is complete | `report/final/<n>.<name>.tex` | the `% STATUS` line agrees with the idea section | fix the status line first, do not write prose |
| shelf to citation | a key is about to be written | a `path:line` inside `chapters/` | key-to-package coverage M = N; citations without a `path:line` 0 | drop the citation or add the package; no hedged sentence |
| package to number | `output/` has a fresh product | the number in the prose plus the file and line | every number greps back to the product; numbers without a source 0 | fall back to `PENDING(fill: <entry>)` |
| figure to prose | a script produces the figure | `report/final/figures/<name>` | one command regenerates it; the referenced path exists | withdraw both figure and citation; no stale figure |
| report to build | prose is finished | `assemble/*.pdf` | compile exits 0; pages and warnings recorded | fix the build before writing new sections |
| case to executor | the case is written | `tmp/reproduce-test/<id>/PROMPT.md` and `out/` | the existence check prints nothing; first line `id:`; zero fences inside | a non-empty check forbids hand-over |
| executor to read-back | products land | `verdict` in `card.json` | every criterion carries pass or fail, never "basically fine" | a vague criterion is void and gets rewritten |

Four hard rules:

40. Six fields or nothing: each hand-off reports six values (trigger, product, criterion, failure path — the criterion being a command or a threshold), and hand-offs missing a field must number zero. Words such as "handed over" or "aligned" count as missing fields.
41. Every round ends with three lines in `tmp/compare-loop/<wish>/handoff.md`: what changed (file and section), who takes the next leg (person or layer), and where to read (one command or one `path:line`). Rounds without that file must number zero.
42. Keep the previous version: before any section-level rewrite, copy the file to `/tmp/<project>_b<round>.md` and put that path in the readings. Rewrite rounds without a backup path must number zero.
43. Failure escalates on a threshold, not on a mood: twice failed on the same criterion, the third round stops and writes which command failed at which line, recorded in the first paragraph of `tmp/compare-loop/<wish>/readings.md`. Items failing three rounds in a row must number zero — their appearance escalates the decision to the owner instead of another self-attempt.

### 1.9 Checking the draft

After the edit, check four classes of hard defect.

Actions:

1. Check every sentence's source: a claim, a citation key, or a row of `tmp/compare-loop/<wish>/footing.json`. With none of the three, delete the sentence or turn it into a placeholder.
2. Check `tmp/compare-loop/<wish>/questions.json`: a row missing `answered_if` or `refuted_if` does not enter the question table.
3. Check `tmp/compare-loop/<wish>/placeholders.json`: a row missing `waits_for` or `owner` leaves the body.
4. Check the shelf index for every citation key: a key that does not resolve leaves the body.
5. Check float numbers and cross-references: every pointer to a figure, table or section that does not exist is repaired until it does.
6. Check for leftover `% PENDING`: one occurrence in a delivery round records `verdict: dirty`.
7. Check claims across sections: the same `claim_id` in introduction, method and discussion reads word for word, compared on three things only — the number, the unit, the qualifying phrase; a difference in any one of them makes two wordings, which are reconciled or one is removed.
8. Check location and template: files outside the directory the instruction named number zero; every change in the template's preamble has a matching `stack.json` row, and places without one number zero; places where the include hierarchy departs from the template number zero; the whole document builds from scratch with zero errors.
9. Check asset entry points: every figure, table and script carries a rerunnable entry, a version or commit, and one command that runs without the upstream layout; assets missing an entry or a version number zero, and each one is repaired as it is found.
10. Check the citation exit: every key in the body resolves to an entry in the citation library, and the entry carries authors, title, year, venue and DOI or URL. A missing entry or a missing field is filled item by item; a citation that cannot be completed leaves the body. No hand-typed entry appears in the body.
11. From the second occurrence of one `kind` on, each occurrence goes to `tmp/compare-loop/<wish>/stack.json`, and the pass clears them down to the last one.
12. Record this round's result.
13. Check the register: banned-list hits, sentences without evidence, bullet marks and mean sentence length, all four. `tmp/compare-loop/<wish>/register.json` records the four readings and the line numbers of over-long sentences; the banned list is the one in 1.8 step 15. Any non-zero count records `dirty`, and `next` names the paragraph to rewrite back at 1.8.
14. The sensory retelling is a closing condition: before handing over, four sentences — what story this section tells, which sentence was fed in, what the reader sees on either side of the change, and which downstream section it feeds; a missing sentence or an empty verb such as "this chapter introduces" records `dirty` and the round does not close.
15. Checking recomputes; it does not cite last round's conclusions: three counts, each run again — whether every number traces to a `path:line`; whether every added citation key resolves; and whether the comparison table's two columns were re-read after drafting (one column before, one after).
16. Before delivery, read the feed against the body: `grounds` is a file plus a line, or a stated counting method; rows saying "as above" or "see previous" must be zero; a number in the body with no source in the feed either leaves the body or gains a source.

On-disk contract: file `tmp/compare-loop/<wish>/audit/<round>.json`; fields `round`, `unsourced` (section plus sentence number), `questions_missing_criteria` (`qid`), `placeholders_missing_owner` (`pid`), `unresolved_keys`, `verdict` (`clean` / `dirty`).
Written when: once per round after the edit, on disk as the check ends.

Where a failed check goes: every `dirty` item names its return step in this round's `verdict` `next` — a sentence, a paragraph or a structural fault goes back to 1.8 and that paragraph is rewritten; too little literature or a citation that will not carry the claim goes back to 1.7; a number missing, mismatched or not reproducible goes back to 1.4. When none of the three routes is open (cannot run, cannot find, cannot write), one row goes into `stack.json`, `next` reads `escalate: user`, and the step does not stall.

Criteria and breach: all four arrays empty records `clean`. A round recorded `dirty` does not close, and its changes do not count toward 1.2's `current`.
17. Skeleton check closes the round: chapters equals chapters with a skeleton; pothole items equals `PENDING(fill` lines; "Open items" subsections equals chapters; any mismatch means unfinished.
18. Scaffold residue check: `Job`, `Narrative arc`, `Potholes`, `Paves` appear zero times in the idea. A chapter map, if kept, is a plain table whose every row points at a product that exists on disk.
19. Contract-work rule: rewriting more than three chapters in one round means re-laying the whole document in the host project's existing idea shape; one chapter revised is not evidence the whole reads.
20. Shelf check: packages equal top-level directories; packages with all three parts, packages missing a body, and packages with `reader: none` are each counted in the readings; group folders, README, INDEX and tools inside a shelf must number zero.
21. Moves and deletions are reconciled: the round's readings carry an old-name to new-name list whose length equals the moves made; deletions equal the dry-run list; a shelf of symlinks reports zero broken links.
22. Key-to-package coverage: the prose uses N keys and the shelf yields a package for M of them; M must equal N, and the difference is listed by name. A non-empty difference fails the round.
23. Six shelf checks, one command each, each zero or empty: group folders, `README`/`INDEX`/`tools`, empty directories, packages whose name misses their title, placeholder titles, broken links.
24. Every citation carries a `path:line` inside `chapters/`; citations without one must number zero, and a `path:line` pointing at a file that does not exist counts as missing.
25. Six fields, item by item: the round's readings end with a small table, eight hand-offs by four columns (trigger, product, criterion, failure path). Empty cells must number zero.
26. Three hand-off lines and a backup: `tmp/compare-loop/<wish>/handoff.md` complete, and the `/tmp/<project>_b<round>.md` path in the readings; missing either fails the round.
27. Out-of-scope edits zero: entries in `git status --short` outside the whitelist for this round must number zero, and any unexplained entry is listed by name.
28. Keys and packages agree character for character: every line of `ls workspace/literature` has an entry under the same key in `references.bib` and the reverse; both differences are produced by one command each and must be empty.
29. Where `out/` sits: `find <repo> -type d -name out -not -path '*/tmp/*'` may print only `00_data/build/out`; one more line fails the round.
30. Figure check: every `.pdf` in `report/final/figures/` has a `.caption.txt` beside it, so figures without a caption number zero; each figure has one re-run command, and the byte change after a rebuild goes into the readings.
31. Figures against narrative: every figure is cited in the prose (`\ref` or a path), so uncited figures number zero, and every "see Figure" sentence names its figure.
32. Three checks on keys: directory count equals bib key count; the difference on either side is empty; the longest directory name is at most 32 characters.
33. Three checks on keys: directory count equals bib key count; the difference on either side is empty; the length threshold is the one in `1.9-36` (at most 20), not a second number set here.
34. Location check: `find <project root> -maxdepth 1 -type d -name loop` prints nothing, and the number of directories under `<project root>/tmp/compare-loop/` equals the number of wishes in flight.
35. Three checks on key shape: directories not ending in a four-digit year number zero; directories longer than 20 characters number zero; directories with an empty `meta.year` number zero, or all of them sit in the readings' undetermined table and none is cited in the prose.
36. Clauses must not disagree: the same quantity given two different thresholds in one file must number zero (grep the quantity, e.g. a key length stated as both 32 and 20); a hit is fixed on the spot and the readings are retaken.
37. Two commands decide the kind: a layer package has zero `.py` files; a leaf package's top level holds only `src`, `conf`, `out`, `README.md` and nothing else.
38. Six junk checks, one command each, all zero: `.DS_Store`/`__pycache__`, `*.pyc`/`*.log`/`*.tmp`/`*.bak`/`*~`, `* 2.*`, dated snapshots, empty directories outside `.git`.
39. Numbers: children run consecutively under each parent with no gaps, and a directory's first segment equals its parent's first segment; mismatches number zero.
40. `out/` closes: every leaf package's `out/` carries `MANIFEST.json`, and every file under `out/manual/` is named in the readings.
41. Location closes: the row count of `packages.tsv` equals the number of second-level packages; rows with an empty `idea`, `slot` or `product` number zero; the row count of `stale.tsv` equals the N in the readings' first line.
42. Holes reconcile: every file name inside a `PENDING(fill: <package>/out/<file>)` appears in the `product` column; misses number zero.
43. Numbers agree: every `report/final/<number>.<name>.tex` named in the `slot` column exists; pointers to missing files number zero.
44. Numbered directories stand on their own: every `NN.M.K_` directory owns a non-empty `out/` and a row in `packages.tsv`; a miss counts and the total must be zero.
45. Split to the bottom: the tidied tree holds no subdirectory with twenty or more mixed entries and no transit folder named `v1_patched`, `misc` or `old`; both counts must be zero.
46. No bins: `find <package> -type d \( -name '_deprecated' -o -name '_misc' -o -name '_tmp' \)` prints nothing, and every file under the temporary area's `unrecognized/` carries one line saying why it could not be classified.
47. Arms and residues name a destination: `kind=arm` or `kind=residue` rows carry `folds-into:`, `deprecate` or `delete` in `plan`, and those directories must number zero after the stocktake.
48. Shared layers: `find <workspace> -type d \( -name common -o -name core -o -name shared \)` prints nothing, and every `<package>/kit/__init__.py` opens with its origin and date; either missing fails.
49. Container emptiness: for each directory holding subpackages, `find <dir> -maxdepth 1 -type f | wc -l` prints 0, and `find <dir> -maxdepth 1 -mindepth 1 -type d` lists subpackage names only; either failing is a breach.
50. Idea anchoring: `awk -F'\t' 'NR>1 && $2!~/毕设立意\.md:[0-9]+ 第 [0-9]+/' out/anchor.tsv | wc -l` prints `0`; `awk -F'\t' 'NR>1 && $4!="anchored" && $4!="no-anchor"' out/anchor.tsv | wc -l` prints `0`.
51. Debt disposition: `awk -F'\t' 'NR>1 && $5!="deprecate" && $5!="keep"' out/anchor.tsv | wc -l` prints `0`; a `deprecate` row names its temporary-area target.
52. Audit: `awk -F'\t' 'NR>1 && $4!~/^(keep|merge:)/' out/audit.tsv | wc -l` prints `0`; every `merge:` row carries the exit code of the entry run after the merge.
53. Allowed-list check: `find <package>/out -maxdepth 1 -type f ! -name 'results.json' ! -name 'MANIFEST.json' | wc -l` prints `0`; `find <package>/out -maxdepth 1 -type d ! -name runs ! -name manual | wc -l` prints `0`.
54. Refactor equivalence: `awk -F'\t' 'NR>1 && ($5!=0 || $6!="same")' out/audit.tsv | wc -l` prints `0`, and `awk -F'\t' 'NR>1 && $2!~/毕设立意\.md:[0-9]+/' out/module_map.tsv | wc -l` prints `0`.
55. Numbering: `find <layer> -maxdepth 1 -type d -name '[0-9]*' -exec basename {} \; | sort` must show two-digit padding with the parent's number first; any name matching `^[0-9]\.` counts as one failure, and a hole absent from `gaps.tsv` as another — both must be zero.
56. Literature and notes: `find <package> -name '*.pdf' | wc -l` prints `0`; `find <package> -name '*.json' ! -path '*/out/*' | wc -l` prints `0`; `find <package> -name '*.png' ! -path '*/out/*' | wc -l` prints `0`.
57. README four parts: `grep -c '毕设立意\.md:[0-9]\|^## 观察\|^## 跑\|^## 产物' <package>/README.md` is at least `4`, and `PENDING(obs)` appears at most once, only while the observations section is unfilled.

### 1.10 Feeding the idea back

The situation: the draft is delivered and checked, and the ecosystem holds an idea document — `workspace/<the design document>.md` and its Chinese introduction. An idea that lags behind the draft is what the next round will use to overwrite the draft.

What is done:

1. Fix the scope: for each section this round changed, find its counterpart in the idea. A section with no counterpart is registered in `stack.json` and a section is added in the right place of the idea within the round — never as a new file.
2. Write it in: the claims, the price and the boundary that this round established go into those sections, placed by the idea's own structure (problem → claim → evidence → boundary → chapter by chapter). The sentences are academic prose, the same register as the body.
3. No work-log language: `TODO`, `this round`, `done`, `next` never enter the idea. The idea describes the research, not the progress of the work.
4. As a pair: the English body and the Chinese snapshot are both written in the same round, with the same section count on both sides. One side alone counts as not done.
5. Record the readings: sections changed, sections matched in the idea, sections added — into `verdict` `readings`.

Written contract: `tmp/compare-loop/<wish>/idea-feed.json`, fields `section`, `idea_section`, `action` (`insert` / `rewrite` / `reserve` / `none`), `located_by` (the sentence or heading that located the region), `note`.

Written when: after 1.9 passes and before the round closes; a round that fails the check does not feed.

Criteria and breach: every section this round changed has a row with a non-empty `idea_section`, rows missing number zero; occurrences of work-log language in the idea number zero; a round that writes one side of the pair only is recorded `unmet`. A delivered draft with no feed is likewise `unmet` — an idea behind the draft is harder to notice than a badly written paragraph.`dangling` hooks in the idea number zero, and so do `@` entries and bibliography sections — either one is a breach, returned to 1.1 by boundary two and four.Rows missing on either side of the map number zero — every report section carries `% SECTION`, every idea section carries `→ report` — and so do pointers to sections that do not exist.

## 2 Nine small loops

Each loop runs on one dispatch bound to one `<wish>`; everything it produces lands under `tmp/compare-loop/<wish>/`, never in another space and never at the root of `tmp/compare-loop/`.

Five rules hold before any loop:

1. Open with three readings: the `verdict` value in the previous `verdict/<round>.json`, the count of `open` rows in `placeholders.json`, and the count of `open` rows in `stack.json`. Close with the same three; the difference is what this round actually moved.
2. Steps join only through files on disk: each step's close writes its product path and its counts into that step's contract file, and the next step starts from the path the previous one wrote rather than from memory.
3. The numbered order is the default route, not the only one: each loop's "Order" line is the shortest path. Halfway through, a missing number sends the work back to 1.4, thin literature to 1.7, a paragraph that fails to 1.8; the loop resumes once that step is done. A step not taken is recorded in `rows` of `verdict/<round>.json` with one line saying why; a step skipped without a row makes the round `unmet`.
4. Anything discovered on the way — a missing paper, a missing setting, a missing entry, a defect — pushes one row into `stack.json`, and the loop continues; work the user has not interrupted is finished.
5. A criterion is written as a count: which table is counted, and what number closes it. A criterion without a count is not a criterion.

Every loop closes at 1.2B and re-runs 1.9 after the edit. Before the round closes, 1.10 feeds the idea back; a round that does not feed is recorded `unmet`. When 1.2B returns `fail` or 1.9 records `dirty`, the round records `unmet` and keeps both lists.

### 2.1 No results yet; the introduction is drafted

Situation: the thesis question is settled, no experiment has run, and three introduction sections must go out.

Opening readings: `open` rows in `tmp/compare-loop/<wish>/questions.json`, sections in `samples/<set>.range.json`, entries in the shelf index.

In hand: `tmp/compare-loop/<wish>/questions.json`, the range rows of `samples/<set>.range.json`, the shelf index.

What is done: before writing, put down the sentence each of the three sections answers and point it at a `qid`; before the first sentence, read other introductions as 1.8 step 1 requires — three paragraphs per section, their shapes into `voice.json`, and a paragraph that cannot be read that way is not written; each section writes its conclusion first, then its basis — a source, the figure the range gives that section, what the approach costs others; build after each section and never start the next on a broken one.

Order: `1.1 → 1.2A → 1.3 → 1.8 → 1.2B`.

Not allowed: any number of this draft in the body — invented, estimated or copied from an older draft; the same sentence twice for bulk; a citation absent from the shelf; "to be confirmed" written as "confirmed".

Criteria: every paragraph of the three sections holds a `voice.json` row with all three `read_back` fields, and paragraphs missing one number zero; occurrences of this draft's numbers in the body number zero, every written form counted — digits, number words, percentages, ranges, and the word "about" in front of them; words and citations per thousand words of the three sections inside the range; five rows of `verdict` all `pass`.

Breach: this draft's numbers appearing once or more make the matching `verdict` row `fail`, and those numbers stay out of `current`; a key absent from the shelf is recorded `unsourced` by 1.9 and the sentence is withdrawn.

Close: rows missing in `sections.json` number zero (`section`, `hash`, `file` all filled), `verdict/<round>.json` written, and the `open` count of `placeholders.json` carried into the round's readings.

### 2.2 The readings have landed; the numbered sections are drafted

Situation: readings and the commands that produced them sit on disk, and one or more placeholders wait on them.

Opening readings: `indexed` rows in `tmp/compare-loop/<wish>/intake.json`, `open` rows in `placeholders.json`, rows in `footing.json`.

In hand: the `indexed` rows of `tmp/compare-loop/<wish>/intake.json`, `placeholders.json`, and the position-table row of each section involved.

Order: `1.5 → 1.2A → 1.6 → 1.8 → 1.2B`.

A few looks first, for instance the unit and digits, where the number sits against the range — inside, below the floor, above the ceiling — and whether its magnitude matches the same-setting literature; where one of the three disagrees, settle the setting before writing. Decide which `claim_id` the sentence carries before writing it; a sentence carrying none is cut.

Not allowed: two numbers side by side while `against` is short; the gap between two runs reported as an improvement; "about", "close to", "same order of magnitude" standing in for a missing number; a whole section rewritten under the name of filling a gap; a `suspect` item used as a conclusion.

Criteria: every number in the body has a `current` row in `footing.json` whose `source` command runs; numbers of this draft without such a row number zero; the placeholder gap is 0, or every `open` row carries `waits_for` and `owner`.

Breach: a number in the body without a `current` row is recorded `dirty` by 1.9 and the sentence withdrawn; a comparison left side by side while `against` is short makes that `verdict` row `fail`.

Close: rows added to `footing.json`, N placeholders filled and M still open, both counted from the tables, carried into the round's readings.

### 2.3 The deadline arrives first

Situation: the deadline is here, part of the results came back, and the draft must take shape.

Opening readings: `open` rows in `tmp/compare-loop/<wish>/placeholders.json`, `open` rows in `flags.json`, `open` rows in `questions.json`.

In hand: any `indexed` material, the position table, the placeholder table, `flags.json`.

Order: `1.1 → 1.2A → 1.3 → 1.8 → 1.2B`. Same order as 2.1.

A placeholder's fate is decided before writing, for instance one of these: one someone can fill stays `open` with that name in `owner`; one that cannot be filled takes `dropped` with the reason; a missing source takes `requested` with the channels tried. A fate outside these three records in `note` what it is and what it waits on, and still holds one row in `placeholders.json`; the body carries the placeholder, never the word for its fate.

Not allowed: placeholders deleted to look complete; "not seen" recast as "preliminary result" or "the trend is clear"; a `suspect` item written as a conclusion.

Criteria: rows in `tmp/compare-loop/<wish>/placeholders.json` missing `owner` or `waits_for` number zero; this draft's numbers in the body number zero; `open` rows in `flags.json` with an empty `evidence` number zero.

Breach: a placeholder deleted without a `dropped` record makes the round `unmet`; "not seen" written as a conclusion is recorded `dirty` by 1.9.

Close: `verdict` records "shape delivered, measurements outstanding", and the `open` counts of `placeholders.json` and `flags.json` enter the round's readings.

### 2.4 Thickening only

Situation: no new run; one section grows thicker — more sources, more of what others did, more of what it costs.

Opening readings: entries in the shelf index, paragraphs in that section, the literature-gap value from the previous `rows`.

In hand: the shelf index, that section's position-table row and paragraphs, the literature-gap row of the previous `verdict`.

Order: `1.7 → 1.2A → 1.2B`. A batch arriving at once is worked inside 1.7: deduplicate, file each item with its citation entry, rebuild the index and check the count, return to 1.2 to update the position table, then write the prose.

The "what it changed" line carries three things: the claim added, the sentence of this section it replaces or supports, and the page; a citation missing one of the three stays out of the body. A second filing of the same paper is compared by `key`, then DOI, then title, and counts as new only when all three differ.

Not allowed: citations added without a line saying what they changed; "read" recorded as "expanded"; the gap difference left as a word; `comparison` written from an abstract alone; the same paper filed twice.

Criteria: the gap row's `current` falls against the previous round; `filed` and `still missing` both enter `rows`; the difference between index entries and filed items is zero.

Breach: a citation without its "what it changed" line is withdrawn from the body; a gap difference left as a word makes that `verdict` row `fail`.

Close: the two numbers in `rows` differ from the round's readings by zero, and that section's `hash` in `sections.json` is updated.

### 2.5 One section is reworked

Situation: the previous verdict named one section, and nothing else moves.

Opening readings: `next` rows of that section in the previous `verdict`, its placeholder rows, its position-table rows.

In hand: that section's position-table row, placeholder rows, citation list, and the `next` rows of the previous `verdict` that belong to it.

Order: `1.2A → 1.6 → 1.8 → 1.2B`.

Reading the verdict starts with three things: which row failed, what its `action` says, and what its `target` is; the three are copied at the top of the round, and after the edit each row is read again — the move from `fail` to `pass` must name the sentence that changed. A problem seen outside the verdict pushes one stack row: it does not block this round and is not ignored.

Not allowed: touching another section, including "a quick improvement" to a neighbouring paragraph; deleting a placeholder; editing from impression rather than from the verdict row; a problem outside the verdict left unrecorded — it goes on the stack.

Criteria: every `hash` in `sections.json` except that section's is unchanged; every row of `verdict` for that section reads `pass`.

Breach: another section's `hash` moving makes the round `unmet` and names the sections; a `fail` row remaining in that section makes the round `unmet`.

Close: say which section moved and which `next` row moved it, with the `hash` before and after in the round's readings.

### 2.6 Closing out unfinished experiments

Situation: the shape of the draft stands and the numbers are what is missing; this round either finishes the open experiments or records why they stop.

Opening readings: `queued`, `running` and `blocked` rows in `tmp/compare-loop/<wish>/experiments.json`.

In hand: `experiments.json`, `placeholders.json`, `intake.json`.

Order: `1.3 → 1.4 → 1.5 → 1.2A → 1.2B`.

`done` is backed by evidence such as these three: the row reads `done` in `experiments.json`, a counterpart sits in `intake.json` with `state: indexed`, and the placeholder reads `filled`. One missing sends the row back to `running`. Three failures on the same cause — one dependency, one error, one absence — make it `blocked` with `tried` and `proposal`, and the fact goes to 2.7.

Not allowed: a `blocked` row written as `done`; the long-dependency run skipped for the easy ones; a reduced scale left out of `degraded`; "it ran once" taken as "intake complete".

Criteria: `queued` and `running` both 0 in `experiments.json`; every `done` row has a counterpart in `intake.json`; every `blocked` row carries `tried` and `proposal`; `open` rows in `tmp/compare-loop/<wish>/placeholders.json` tied to this round's experiments number zero.

Breach: a `done` row short of one piece of evidence returns to `running`; `queued` or `running` not at zero makes the round `unmet`.

Close: three numbers — `done`, `blocked`, placeholders still `open` — carried into the round's readings.

### 2.7 Reflection: the number disagrees, the run will not come, the expectation moves

Situation: a hard fact is in hand. The common ones are these — a number contradicts a claim of this draft; an experiment has exhausted its routes; the thesis as written cannot deliver what the draft requires. A fact outside the list that blocks the draft, moves the thesis or moves the expectation takes this same loop.

Opening readings: `open` rows in `tmp/compare-loop/<wish>/regurgitation.json`, `refuted` questions in `questions.json`, `open` rows in `stack.json`.

In hand: the rows of `tmp/compare-loop/<wish>/regurgitation.json`, the refuted questions with their `pid`, the `sections.json` rows of the sections involved, and the `open` rows of `stack.json`.

Order: `1.5 → 1.1 → 1.2A → 1.3 → 1.2B`.

What is done: the fact goes onto the reflection list in its existing shape; back to 1.1 to change the thesis — a refuted question takes `refuted`, a changed narrative or a lowered expectation records before and after in `note`; back to 1.2 to re-judge the position table; back to 1.3 to mark the dead placeholders `dropped` with the reason; then one fresh verdict.

One fact carries four fields: `kind`, `where` (the data location or the error as printed), `tried` (each route with its result), and `proposal` (lower the expectation, change the setting, change the narrative, change the sample, or another way through). A fact missing one of the first three is not on the list; the proposal is written as concretely as it can be, and where none exists yet, `pending` goes in and the fact returns to `stack.json`.

Not allowed: the counter-example removed from the body as if it never existed; the target quietly shrunk; a contradicting number explained away as noise; a route declared dead without `tried`.

Criteria: every hard fact has a row in `regurgitation.json` with a non-empty `tried`; the affected `qid` and placeholders carry their states; `verdict` was re-run.

Breach: a fact without `tried` is void; a `refuted` question still in a conclusion sentence is recorded `dirty` by 1.9.

Close: `refuted` questions, `dropped` placeholders and the `open` rows of `regurgitation.json` enter the round's readings.

### 2.8 Re-running on outside comments

Situation: a batch of comments came back and a person has already turned it into a list of operations: re-run a run, add a comparison, rewrite a passage. The worker does not read the comments, only the list.

Opening readings: items on the list, questions in `tmp/compare-loop/<wish>/questions.json`, `queued` rows in `experiments.json`.

In hand: the list as turned into operations, `questions.json`, `experiments.json`, and the previous `verdict`.

Order: `1.1 → 1.4 → 1.5 → 1.2A → 1.2B`.

What is done: each item maps to one `qid` (a new question row is opened where it maps to none); the runs it needs are opened in 1.4 and finished as 2.6 says; results are filed and reviewed in 1.5; then one fresh verdict.

When an item maps to nothing: open a question row with `provenance: user` first, then decide whether a run is needed; an item needing several runs opens them all, and the count enters the round's readings; every section edited updates its `hash` in `sections.json`.

Not allowed: an item called "handled" without a row; one item needing several runs with only one taken; the verdict left un-run after the edit.

Criteria: every item has a row in `questions.json` or `experiments.json`; `queued` and `running` are both 0 in `experiments.json`; `verdict` was re-run.

Breach: an item without a row makes the round `unmet`; `queued` not at zero makes that `verdict` row `fail`.

Close: items on the list, items with rows, and `queued` at zero enter the round's readings.

### 2.9 Tidying the repository

The situation: a round of experiments has run and the workspace has started to rot — outputs scattered between `tmp/` and each package's `output/`, old packages stopped halfway with no record of where, one number living in three copies, paths drifted into a spelling only the author remembers. The next experiment, the next absorbed script and the next reservation all need this ground cleared first. Tidying is not neatness: it is the ground the next round stands on, and the turning of the soil before anything sprouts.

Entry readings: number of packages; rows marked `runnable` / `blocked` / `dead` in `repo.json`; entries under `tmp/`; copies of one output.

What is in hand: `experiments.json`, each package's `run.py` and `expected.md`, the table under `50_results`, the footing check under `60_footing`, the `tmp` listing.

Order: `1.4 → 1.5 → 1.2A → 1.6` — tidying drafts nothing and does not touch 1.8.

What is done:

1. Inventory the entry: every package needs one command that re-runs it, with entry, inputs and outputs written down. A package that cannot run is marked `dead` with one sentence naming what is missing.
2. Put each output where it belongs: one true copy, duplicates removed, a `dup_of` pointer in `repo.json` — no new explanatory document.
3. Call the bluff: draw five rows from the results table at random, re-run each against its footing row. A row that does not match is recorded `fake` and handled in this round, not the next.
4. Routine testing: every runnable package runs `smoke` (small sample, seconds) and must pass; `full` records wall time, seed and the hash of its output, and two runs at one seed with different hashes are recorded `nondeterministic`.
5. Regroup: package names and numbers align with the questions and chapters of the idea (RQ1/RQ2/RQ3); moves go through `git mv` so history survives.
6. Reserve: a package stopped at an unimplemented step keeps `expected.md`, a `run.py` exiting 1, and one sentence naming what it waits for, marked `blocked` — a reservation, not a broken package.
7. Absorb: take one proven piece from `tmp` (a function, a script), never a whole package; the source is written into the package, and whatever is left behind is neither deleted nor moved.

Written contract: `tmp/compare-loop/<wish>/repo.json`, one row per package: `package`, `entry`, `status` (`runnable` / `blocked` / `dead`), `outputs`, `dup_of`, `absorbed_from`, `last_run`, `seed`, `note`.

Written when: once per experiment loop closed, and never later than the first experiment of the next round.

Criteria and breach: every package holds a row with an existing `entry`, missing rows number zero; a `runnable` package's entry exits 0, and a non-zero exit is re-marked `dead` and handled in the same round; `fake` rows number zero; copies of one output number zero; whole-package copies out of `tmp` number zero; `nondeterministic` counts enter `verdict` `readings`. Starting a new experiment while last round's `fake` or `dead` is still open fails the round.

**2.10–2.13 are the four entry points for code work, and all four close on the same tree contract.** Development, retest, maintenance and locating each have a small loop, but each lands through `1.8-58` (two kinds, four slots), `1.8-59` (numbers inherit, no gaps), `1.8-60` (the junk list), `1.8-61` (results only in `out/`), `1.8-62` (each package carries its own `kit/`) and `1.8-63..66` (a package pinned to the idea and to a hole). No task may invent another shape, and "this round only touches code" is not a reason to skip the `1.9-46` container check.

### 2.10 Building a package, or adding one experiment to it

Situation: a section of the idea needs a reading the manuscript still writes as `PENDING(fill:)`, and the package may not exist yet.

Entry readings: the idea section and its sentence, the `PENDING` line number, the row count of `packages.tsv`, the row count of `stale.tsv` (non-zero means clear it first, `1.8-64`).

On hand: the sentence, a neighbouring package's `src/` to copy rather than import, reusable `conf`, the `kit/` template.

Order: `1.3 → 1.4 → 1.5 → 1.6 → 1.8`.

Do: 1. stake the hole with `PENDING(fill: <package>/out/<file>)` and write the three things (sentence, `ref`, product name) into the readings; 2. take the smallest free `NN.M` under the parent, no gap, no recycling; 3. build exactly four slots; 4. copy the tools you need into `src/kit/` with origin and date, import no other package; 5. one command reruns it, exit 0, product in `out/` with `MANIFEST.json`; 6. add the `packages.tsv` row with all four columns filled.

Lands as: the new `packages.tsv` row plus `out/MANIFEST.json`. Written in the round the package is created, placeholder and replacement in that same round.

Criteria: a new package's top level holds only `README.md`; `src/run.py` exits 0; the row has four non-empty columns; `stale.tsv` does not grow because of the new package. Any miss counts as not built.
6. The first step of a build writes the four-part `README.md` (`1.8-80`): idea section with its line, the command, the product, and an observations section holding `PENDING(obs)`; literature found on the way is fed back into the library per `1.8-79` with one `refs.tsv` row. Numbers follow `1.8-78`, padded, with the parent's number in front.

### 2.11 Retest: same input, the numbers must not move

Situation: the package runs, but running is not reproducing; a new machine or a pinned dependency shifts the numbers the manuscript already cites.

Entry readings: `runnable` rows in `repo.json`, sha of every `out/*.json`, seed and runtime in `MANIFEST.json`.

Order: `1.4 → 1.5 → 1.2b` (no drafting).

Do: 1. freeze inputs into `tmp/compare-loop/<wish>/inputs/<package>/`; 2. rename `out/` to `out.first` rather than deleting it, then rerun; 3. compare file sha, JSON key sets and every value (1e-9 for floats); 4. classify each difference as seed, float drift, dependency or real error; 5. keep both outputs until the round ends and record both sha; 6. update `rerun_at` and `sha` in `MANIFEST.json`.

Lands as: `retest.tsv`, one row per package: `package`, `first_sha`, `second_sha`, `diff_keys`, `verdict` (`same`/`drift`/`fail`). Written once after tidying and once before numbers enter the prose.

Criteria: rows equal the number of `runnable` packages; rows with equal sha under the same seed equal that number; every `fail` row appears in `stale.tsv` with its blocker. Otherwise the package counts as not retested.

### 2.12 Maintenance: an equivalent refactor moves things, never numbers

Situation: numbers need renumbering, packages need merging, `kit/` needs trimming, a container needs emptying — all moves, not a single number may change.

Entry readings: sha of every file under `out/`, each package's entry command, how many files mention the old name.

Order: `1.4 → 1.5 → 1.9` (no new content).

Do: 1. record the baseline into `baseline.sha`; 2. move only with `git mv`, no newly written files; 3. chase references with `grep -rl` down to zero, `sys.path` and imports in the same round; 4. rerun once; 5. compare sha with the baseline and call it equivalent only when equal; 6. run the two `1.9-46` commands.

Lands as: `renames.tsv` (`old`, `new`, `basis`), `baseline.sha`, the rerun comparison. Written and rerun in the same round.

Criteria: `grep -rl '<old name>'` is zero; rerun sha equals baseline; both `1.9-46` counts are zero. Any miss counts as unmaintained and its numbers may not be cited.

### 2.13 Locating: pin a package to a section and a hole

Situation: the product exists but nobody can say which section it feeds, or the idea moved and the package still points at the old number.

Entry readings: `packages.tsv` rows and empty cells, `stale.tsv` rows, `PENDING(fill:)` occurrences in the prose.

Order: `1.5 → 1.6 → 1.10`.

Do: 1. read the idea for the section it supports and quote one sentence with its line number; 2. fill `idea` with number and title, and never guess from the package name; 3. fill `slot` with the section of `report/final/<number>.<name>.tex`; 4. fill `product` with the file under `out/` that carries the number, matching `MANIFEST.json`; 5. send what cannot be located to `stale.tsv` with `last_touch`, `reason`, `disposition`; 6. write one feed row with `located_by` pointing at the `packages.tsv` line.

Lands as: the four `packages.tsv` columns, the four `stale.tsv` columns, one `feed.json` row. Written after every intake, before the prose cites a new number.

Criteria: empty cells zero; `stale.tsv` rows equal the N in the readings; every `PENDING` file name appears in the `product` column; every `slot` names an existing `.tex`. Any miss counts as unlocated and its numbers stay out of the prose.
5. Intake aligns the README observations with `anchor.tsv`'s `idea` (`1.8-80`); a missing reference gets a `refs.tsv` row and, when the shelf lacks it, an entry under `workspace/literature/` — metadata only.

### 2.14 Tidying: walk from a root to the bottom packages, move one at a time, prove nothing changed

Situation: a root is given — the whole `workspace`, one container, or a subdirectory inside a leaf — and its packages mix four states with no way to see which level should look like what.

Entry readings: directory count under the root, whether `tidy.tsv` exists, top-level entry count per candidate, sha of every `out/`, row counts of `packages.tsv` and `stale.tsv`.

Order: `1.4 → 1.5 → 1.9` (a tidy does not draft).

Six steps, one line each, and no step starts before the previous one has readings:

1. Identify. Walk down from the root; a directory holding only subpackage directories is a container, one that fits or can be folded into the four slots is a leaf, anything under `_upstream/`, `repo/` or `.git` is not a package. `tidy.tsv` carries one row per bottom package, containers take no row, and an undecidable package is `kind=unknown` and also enters `stale.tsv`.
2. State. Apply `1.8-67`: a normal name carries only content; `_upstream/` for clones, `_deprecated/` for retired evidence, `_staging/` for untidied and uncitable. Every rename goes into `renames.tsv` with the clause that justified it.
3. List. The `plan` cell says how many moves and what each one is ("`dispatch.py` → `src/run.py`"); "tidy it up" is not an action and fails the criterion.
4. Analyse. Per row, classify every top-level entry (source, config, result, document, junk), try the single entry command, and separate products from snapshots inside `out/`; write the conclusion into `evidence`, not into a new document.
5. Execute. Move by `git mv` only, no newly written files; retake the three readings (entry count, exit code, sha) and append them to `evidence`.
6. Prove. Compare with `baseline.sha`: the numeric difference must be zero (`1.8-70`); otherwise roll that package back and record `impact`. When every row is done, run `1.9-46` once more.

Lands as: `tidy.tsv`, `renames.tsv`, `baseline.sha`, `impact.tsv`, all under `tmp/compare-loop/<wish>/`. Written in the round the tidy is ordered, appended per row, closed after the last row.

Criteria: rows equal the number of bottom packages under that root; empty `state` cells zero; `plan` cells without an action verb zero; `impact.tsv` rows with a non-zero `diff` zero; both `1.9-46` counts zero afterwards. Any miss means the root counts as untidied and its numbers stay out of the prose.

### 2.15 Branch residue: decide whether it is a subpackage or another way of writing configuration

Situation: a numbered subdirectory sits under a parent (for instance `00.1_2d_diffusion/00.1.1_boundary_prompts` or `00.1.2_img2img`). It may be a real subpackage, or the shell left by a trial branch — one `README.md` and one `prompts.yaml`, or a script nobody calls.

Entry readings: file count and `.py` count per candidate, whether it owns `out/`, whether `packages.tsv` has a row for it, whether the parent already holds an equivalent configuration.

Order: `1.4 → 1.5 → 1.9`.

Do: 1. answer the four questions of `1.8-71`, one point each, and write them as a four-digit string into `evidence`; 2. read the total — `1111` is a subpackage, `0001`/`0010` is an arm folding into `conf/`, `1100` with a duplicated product is a residue going to `_deprecated/`, `0000` is a note folding into the parent's `README.md`; 3. check whether the parent still points at it ("the configuration for this arm lives in <directory>") and fix that line after folding; 4. move with `git mv` only, record `old`/`new`/`basis` where `basis` reads `1.8-71:<digits>`; 5. verify with `1.9-47` and `1.9-48`.

Criteria: numbered directories judged `arm` or `residue` number zero afterwards; both `1.9-47` and `1.9-48` print zero; the parent no longer points at a removed directory. Any miss means the parent counts as untidied and its row may not be cited.

### 2.16 Idea anchoring and in-package audit

**Situation:** a package can come out tidy and ownerless — every file in a slot, yet the products match no section of the idea; or the code splits into two halves and nobody asks whether they should merge and read better as one.

**Entry readings:** rows of `out/anchor.tsv` (equal to the package count), how many read `no-anchor`, and how many `merge:` rows `out/audit.tsv` holds.

**On hand:** `tidy.tsv`, the actual products under each package's `out/`, and `毕设立意.md`.

**In order:**

1. One row per package in `anchor.tsv`: `package` / `idea` / `product` / `anchor` / `debt`; `idea` reads `毕设立意.md:<line> 第 N 节`, section number and title copied verbatim.
2. Judge each product's anchor and write `anchored` or `no-anchor`; a `no-anchor` product is named on the delivery's line and never cited in the body.
3. Apply the three debt tests (`1.8-78`): a hit writes `deprecate` with a temporary-area target; a doubt that misses them writes `keep` and is named on the "suspect products" line.
4. Audit `src/`: count files, import edges and entry points; one row in `audit.tsv`: `package` / `files` / `edges` / `merge_plan` / `entry_exit`.
5. Merge what `1.8-79` judges mergeable, run the entry once afterwards, write the exit code back; a non-zero exit rolls the merge back.

6. Write `module_map.tsv` per the refactor clause, rename and merge by `duty`, converge the entry to `src/run.py`; run the entry and take `out/` shas before and after, writing both back to `audit.tsv`.
7. Clear the top of `out/` per the allowed-list clause and delete only with the evidence card; `manual/` keeps hand-edited snapshots only.
**Product contract:** `out/anchor.tsv` with five columns, `out/audit.tsv` with six (adding `entry_before` and `sha_same`), `out/module_map.tsv` with four, headers verbatim as above; a missing column or empty value fails.

**When to write:** each package's two rows the moment its tidy ends; the delivery note only after every package is done.

**Criteria and breach:** the three commands of `1.9-51`, `1.9-52` and `1.9-53` must all print 0; citing a `no-anchor` product as a conclusion is a breach.
