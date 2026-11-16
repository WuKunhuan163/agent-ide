# The case library (`_eval/`) — it belongs to no layer

**This directory holds "what happened" and filled-in samples, and exists for two kinds of reader only: whoever edits the layer documents, and whoever issues a reproduction test.** The layer under examination reading it voids that exam.

## The contract (four items, the same set as every other layer)

**Four items, read as borders rather than etiquette**: who may open the directory, who may write in it, how a change is recorded, and what voids a case — a library without them is a drawer, not evidence.

| Item | Content |
|---|---|
| who may read | **only those two kinds**: whoever edits `00`–`03` / `skill.md`, and whoever writes the criteria in `k/<prefix>/`. **A session of any layer is not among them**, the owner included when he "just wants to check" |
| who may write | the same two kinds; **the writer may not be the layer under examination** (writing "I did it right" into the case library = editing the answer key) |
| one line per change | every addition or deletion appends one row to `## changes` at the end: date / which item / why / which reading or verdict it rests on |
| the failure criterion | a `read_file` under `_eval/` appearing in any layer's export → that round is `fail(process)` as a window breach; a new case with no row in `## changes` → the case is void and is not evidence |

**A case records only what happened; it does not prescribe practice.** Anything written as "this is how it should be done" moves into the layer documents' criteria; what stays here must be "what that time looked like, and what the reading was".

---

## Examples and counter-examples (here only)

**The layer documents (`00-owner.md` / `01-supervisor.md` / `02-lead.md` / `03-executor.md`) carry rules and criteria, never answers, never filled-in samples.** The reason is not fussiness: those four are exactly what each layer reads as its prompt, and **putting an example in them hands the answer to the person being examined** — copy it and pass, with no judgement of that layer measured. So:

- **rules, criteria, how a gap is judged** → the layer documents;
- **what a filled-in version looks like, counter-examples, readings, why a rule exists** → this section;
- **a reproduction test's criteria and predictions** → `k/<prefix>/` (`00-owner.md` §Producing a reproduction test), **not this section**.

Every entry below actually happened; paths and readings are transcribed as they were.

### 1 The owner's one action, and its product: geography + prerequisite-experiment list + assessment direction

**These three sections are three blocks of one action, and missing one makes the three layers below each invent their own.** Every path below is on disk; the values are this project's measured ones (from an `ls` on 2026-11-16):

```markdown
## Geography

**This is the filled-in form, kept whole so it can be copied rather than reinvented**: every path is on disk, and the right-hand column is what a layer below acts on.

| Directory / package | What it is (one plain sentence) | Entry |
|---|---|---|
| workspace/00_3dgs_garment | stage 0: two 2D priors + planar SDS | 0.3_planar_sds/v1_patched/build.py |
| workspace/01_main_pipeline | main line 1.1–1.7, seven experiment packages | 1.1_sim_3dgs/run.py |
| workspace/02_baselines | official and reference baselines | 2.1_triposr/ |
| workspace/03_approaches | evaluator and scene generation — input made by make_scene.py **may enter the control experiment only** | 3.0_evaluator/ |
| workspace/04_optimizations | optimisation items | 4.0_baseline_official/ |
| workspace/05_proposed_work | our method: 5.1 mesh anchoring | 5.1_mesh_anchored/run.py |
| workspace/literature | papers and neighbour rows | reads/index.tsv |

## Prerequisite experiments (the arms this stretch runs, each written down)

**Each arm is written down to the level where a reader can run it without asking**: input, product, what is visible when it works, and what it buys in the paper.

| Arm / experiment | Input | Product | What you see when it runs | What it buys |
|---|---|---|---|---|
| 0.3 the two arms `gsA_twice` / `gsB_once` | two yamls under `0.3_planar_sds/v1_patched/configs/` + the same data | `gsA` / `gsB` / `table.md` under `outputs/gs_twice_ab_2329/` (101 lines each) | neither loss explodes in the first 100 steps, and the difference table holds one item | the attribution sentence of main-table row R2 |
| 1.1 `r1_1000` | a scene from `1.1_sim_3dgs/data/` | `runs/r1_1000/`: `metrics.json`, `renders/`, `manifest.json` | what is rendered is the same object, not a template outline | main-table row R1 + the "re-render" column |
| 1.2 `boundary_aware` | only `README.md` so far, `tools/` is empty | `run.sh` + `spec.md`, to be produced | the skeleton runs to the unimplemented point and prints `PENDING` | one page of specification for main line 1.2 |

## Assessment direction

- criterion type: this stretch is judged on **experimental validity** — there is a reading and the form is right; **not** on documents being complete.
- the command that checks it: `cat <arm>/outputs/*/table.md`; `python3 -c "import json;print(json.load(open('<run>/metrics.json')).keys())"`.
- who measures: the lead runs these read-only commands; the owner does not.
```

**Fill these three sections and one thing is settled**: asked "what is each prerequisite experiment, its input and output, what is visible when it runs, what does it buy", the lead's four answers all sit in these three sections — and the "buys" column was written by the owner. **Leave them unfilled** and the same question becomes the twenty-three actions of 2026-11-16: `ls workspace/` first, then three READMEs, then `cat` one table, then zero sentences of answer — and one of those leaves (E5) went off and built a checkerboard scene with `make_scene.py` to fill the gap.

### 2 An observation sentence written as a conclusion

The observation sentence read 「with the residual off, is the contour still there (**there = position is not given by the residual**)」. The half in brackets is a conclusion, not a reading. The executor dutifully handed over 「the cell's position did not move by one cell, therefore the pattern's position is decided by the atlas」, while the same unit's `pattern_phase` readings **0.7765 / 0.7569 / 0.7670 / 0.7785** (line 0.8) judged fail — **one product supporting both "passes" and "fails", because the observation sentence judged a conclusion, not a figure**. The same block also crushed two separately passable things (the figure's form, the IoU number) into one unit: the form passed, the number did not, and the executor could only speak plain speech about half and paste a fail for the other half — leaving the collector unable to tell whether it succeeded.

**The correct cut, two rules**: ① the observation describes the figure's composition only ("each view: GT left / base middle / nodc right, three columns, same view, same size, same background"), and **the whole "what this shows" sentence is deleted or moved behind the numeric criterion**; ② when two things can separately pass and separately fail, **either cut two leaves, or write into the acceptance line "either failing fails the whole dispatch, and the other one's form may not be used to claim a pass"**.

### 3 Percentages reported while the ruler was never opened

**This already happened once, in full form**: `units/12-e5-garment-visible.md:12` wrote its `paves:` as 「the wish clause "finish the experiments on the prerequisite work" **'s end-to-end product**」 — while the owner had long since written that clause as the two arms `gsA_twice` / `gsB_once` (`supervisor-prompt.md:93`, `:210`, criteria `non_finite=0`, `grad_shs` and the first and last loss values present, the two arms juxtaposed, the difference table listing that one item) — and the leaf's input was a synthetic checkerboard made by `make_scene.py` (`units/20-e5-redo.md:14`). **The arm names never appeared once, and the input was chosen by the leaf itself** — "two arms" became "a scene I could think of".

### 4 One place with the old convention, one with the new

**Why it jammed here**: the twenty-leaf version of 2026-11-16 had `weight` sitting at **3–18** (`ratio` = 6.0, `anchors` empty), neither anti-compression check passed, and the same reply reported `44.55%` — **a percentage reported with the ruler never opened is fake to the last decimal, and the next round will schedule on it**.

### 5 A clause mistaken for an experiment (input invented)

**This happened in this project once**: `units/20` split ④ into ⓐ phase / ⓑ residual-off ΔE and turned ② into an absolute difference, while `returns/#12-verdict.md` still recorded `fail(result)` against the old ④ (ΔE 22.72) — two papers each self-consistent, and the reader has to pick which to believe.

### 6 Two denominators

This project's own measurement had two: one place read `55.5/108`, another `69.5/156`, and the true value at that moment could only come from the command above.

### 7 Three measurement changes between two arms

That is what happened on 2026-11-16: three measurements changed between the passes (foreground restriction, separate colour centres, a new `mean_alpha_fg`), and IoU went from `0.7718/0.7550/0.7710/0.7787` to `0.7765/0.7569/0.7670/0.7785` (v2 got worse in the reverse direction), while the return wrote "the second pass after the convention change is the valid product".

### 8 One physical exam that failed

**Measured, one failure**: the head block of `data/prelim-report/BOSS_CONTEXT.md` carried `CARDS: target=10 effective=0 pending=11`, while `compshare pool status` ended at `pending=10 broken=1` at that moment — **the first command would have caught it**. Item 7 of the same exam also failed: nowhere in the context was there a line saying "this stretch is judged on experimental validity or on documents being complete".

### 9 The owner was asked for a list, and wrote an entry that does not exist

**What that looked like**: whoever maintains the documents (me) required three things of the owner in `00-owner.md` — a project geography table (with a `path:line` entry), a prerequisite-experiment list (input / product / what you see when it runs / what it buys), and three lines of assessment direction (with the checking command and the measurer).

**Reading**: one row read `workspace/00_3dgs_garment | <…>/run.py:1`, and `ls` returned `No such file or directory` on the spot; the other two items (input, acceptance line, measurer) require reading disk and running commands, which the owner's layer cannot do.

**Consequence**: one guessed cell in the list gets forwarded by the supervisor as established fact and finally lands on the lead's ledger; the lead's "cannot find the prerequisite experiment" at that time was downstream of exactly this.

**What it became**: the owner writes only the big state and the two columns of `## markers` (left = what he saw on disk, right = the sentence the next layer must check for him); checking and elaborating belong to the supervisor; the exam's "three assessment lines" shrank to one sentence naming the pass type.

## Changes

**A case library that never says what changed turns into folklore**: one row per change, with the reading or verdict it rests on.

| Date | Change | Why | Basis |
|---|---|---|---|
| 2026-11-16 | library created, items 1–9 collected | layer documents keep criteria only; "the filled-in version / counter-examples / readings" move out | `path:line` and command readings, checked item by item |
| 2026-11-16 | four contract items added (who reads / who writes / one line per change / the failure criterion) | a directory without read-write boundaries has no door | as above |
| 2026-11-16 | item 9 changed from "preaching at the owner" to "recording what happened" | the case library describes events, it does not prescribe practice | this round's review |
