# Executor · venue adaptation (cvpr) · the minimum

> This file carries **only what the venue can say**: what things are called, and what counts as failure here. **The layer's own clauses live in the shared `src/template/docs/strategy-roleplay/`**; read both.

one number on one benchmark: dataset · split · metric · setting (resolution, number of views, training time). A number without its setting is not comparable to the baseline it claims to beat.

So when the answer says "the results table will hold N rows", N is countable in these terms, and a row that lacks one of these fields is a hole with a name, not a row.

**A footing.**

the prior work whose **protocol** the number is comparable to — same benchmark, same split, same metric definition — not merely a paper that also reports a number on the task. Where no such protocol exists, the row is `not seen`.

A footing sentence that names a paper without naming the comparable setting is not a footing; it is a citation, and the exam should treat it as one.

**An increment.**

the delta this representation buys **on the same protocol**, with its cost (training time, model size, fidelity) measured in the same units. A gain under a cheaper protocol is a different claim, not an increment.

**Disclosure.**

which ablations and settings were chosen **before** the runs and which **after** — the CS form of the same honesty rule. An answer that cannot say which ablations were pre-registered has not described the stage.

**The four answers.**

- **Q1 (what a finished round leaves).** Rows in the terms above; a footing line per row; sections whose headers name the slot they build; signs for everything that cannot be produced yet. An answer that describes a generic paper's results chapter has not answered this question.
- **Q2 (telling the manuscript aloud).** It must name the stage in this field's own words and say what that stage buys the argument. For this instance the stage is describable as: what was reproduced, what was added, and what the added thing can and cannot claim.
- **Q3 (what each section owes its reader).** Judged against this venue's reading habits: the settings of a number visible where the number is, the protocol named in the same breath as the comparison, the difference sentence quoted from the neighbour rather than summarised.
- **Q4 (the next work).** On-ramp items are the ones that make a run possible in this field: the corpus read for design rather than for decoration, the data that supports the outcome, the table that has a column for every field the row needs, the draft that has a place for the number. In-loop items fill those.

**What fails here.**

An answer that reports a single number without variance or a seed policy fails Q1. An answer that names a baseline without its protocol fails Q3. An answer that commissions training runs while the benchmark split or the metric definition is unresolved fails Q4.


## This venue's delivery contract (three questions, answer only these)

**What is handed over.** One result row: dataset, split, metric and setting (resolution, view count, training time) — all four before it counts as a row; with it one footing line — why that number is comparable with some paper's protocol, naming **which setting** is the comparable one; then an increment: what this representation bought on the same protocol, with its cost (time, model size, fidelity) in the same units beside it; and finally a disclosure: which ablations were fixed before the run and which were added after.

**What counts as not handed over.** A number with no setting; a footing naming only the paper and not the comparable setting (that is a citation, not a footing); an increment across protocols; a disclosure that cannot tell before from after. One of the four missing and the round has no result in this venue's sense, even when the number itself is true.

**How the receiver judges it.** Pick that row up: can it go straight into the results table side by side — four columns aligned, blanks carrying a name (`not seen`) rather than an ellipsis. If yes, it was handed over; if the reader must go into the paper to find the setting, it was not.

**What it looks like done (what you see opening that directory).** Under `outputs/<run>/` a `metrics` file with keys and values, plus one rendered sample, with GT and ours at the same view and the same size side by side; the results row's four left cells filled and `not seen` written in the blanks on the right. Without that, the work is still in the "it ran" bracket and has no result.

## Training-type units: what "it ran right" means for this stretch

**A `loss` line, `rc=0` and a checkpoint only prove it ran.** The return adds three more, and missing one is `BLOCKED(result-not-established)`: the task's main metric in `metrics` (`psnr` / `ssim` / success rate, not an `rc`); at least one rendered or output sample, with one sentence saying what it looks like and what is wrong; and who this batch is compared with and whether it is the same source — if not, write `not comparable — <what differs>`.
