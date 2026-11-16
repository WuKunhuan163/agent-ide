# Adding a template instance

**Read `instances/_skeleton/README.md` first**: five steps plus an equivalence checklist, the single complete procedure. This file adds only the three things that are not there.

## 1 When a new instance is needed, and when it is not

- **Needed**: changing venue or journal means changing the layout, changing what "one row" is, changing reader habits. Any one of the three differing needs a new instance.
- **Not needed**: a different paper title, different data, different results — that is a **project** (`data/<identifier>/`), not an instance.

**Criterion**: if you only want to change words inside a paragraph, that is block content (the `build` JSON), not an instance.

## 2 What an instance cannot decide for you

An instance answers only "the fields of this row", "what counts as failure", "how the four questions are phrased in this discipline" (`docs/strategy-roleplay/executor-notes.md`). **It does not answer "what this round does"** — that belongs to `data/<identifier>/WISH.md` and `results-first-narrative.md`. **Writing the research plan into an instance is a second plan**, and next round it fights the wish.

## 3 Who writes `executor-notes.md`

**Not the main agent from impression**: it must come from observing how published work in this discipline is laid out and how it reports numbers (`report/samples/` or published PDFs from the same venue), and **every line must point at one verbatim sentence or one table**. An instance whose prescription cannot be written is better not created: hold with `cvpr` and mark it `instance: cvpr (provisional)` — **but that goes into BOSS_CONTEXT, never by default**.

## 4 Criteria (checkable)

**Four criteria, each with the command that answers it**: an instance that passes all four can work; one that passes fewer can only compile.

| Criterion | Command |
|---|---|
| the instance is recognised | `python3 overleaf.py list-templates` lists that id |
| the three equivalence pieces exist | `ls instances/<id>/{template.json,docs/blocks.md,docs/strategy-roleplay/executor-notes.md}` |
| a project can be built | `init --conf <id>` succeeds and `validate` reports no error |
| it is not an empty shell | in `executor-notes.md`, each of Q1–Q4 has a specific sentence for this discipline (not "same as cvpr") |
