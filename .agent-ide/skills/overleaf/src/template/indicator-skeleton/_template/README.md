# The standard skeleton of `indicator/<identifier>/`

When opening a new id, **copy this whole directory**, replace `<identifier>`, and do not improvise.

```
indicator/<id>/
  README.md              ← this directory's notes + the lost-context self-check (copy the body of _template/README.md)
  supervisor-prompt.md   ← the fence's verbatim text, stored the moment it arrives (no rewriting, no summarising)
  LOOP_STATE.md          ← ## ON-RAMP + ## EXCLUDED + ON-RAMP LEFT: n
  units/#n-<slug>.md     ← the cut execution units (per units/_template.md, all six lines)
  returns/#n.md          ← the executor's return (per returns/_template.md)
  returns/#n-verdict.md  ← the lead's verdict (per returns/_verdict-template.md)
```

**The queue is not in the directory**: `task-queue --id TEMP_<id>`. **The number `#n` must agree in three places**: `units/#n-*.md`, the queue title's `# unit #n` prefix, and `returns/#n*.md`.

## Four working tables (copy them, do not invent on the spot)

**Four tables, one per moment; taking the wrong one is how a round starts in the wrong shape** — the left column is the moment you are in.

| When | Which table |
|---|---|
| a fence arrives from the supervisor | `intake.md` (eight steps; no cutting until they are ticked) |
| about to dispatch | `dispatch-block.md` (no triple backticks inside a block; only the count outside) |
| asked for the loop's status | `closure-answers.md` (four answers + two lists + four states) |
| asked for an assessment or collection | `review.md` (nine steps, order cannot reverse) |

**Six files in this directory (missing one fails item 11 of `check.py`)**: `README.md` / `LOOP_STATE.md` / `intake.md` / `dispatch-block.md` / `closure-answers.md` / `review.md`; plus, one level up: `units/_template.md`, `returns/_template.md`, `returns/_verdict-template.md`.

**The mechanical ruler**: `python3 workspace/indicator/check.py <id>` → **`PASS 12/12`** is what "the structure is done" means.
