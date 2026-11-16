# The new-instance skeleton (`_skeleton`)

**Why `template.json.tmpl` and not `template.json`**: `list_instances()` only recognises a directory that contains a `template.json`. **Keeping the `.tmpl` suffix** stops this skeleton from being mistaken for a compilable instance.

## Five steps to build an instance (`<id>` a real id, e.g. `healthclaim`)

1. `cp -r instances/_skeleton instances/<id>`;
2. `mv instances/<id>/template.json.tmpl instances/<id>/template.json`, replacing the `<id>` / `<class>` placeholders with real values;
3. put the venue assets in place: `assets/` (`.sty` / `.cls` / `.bst` / fonts) and `preamble.py` (importing absolutely, `from src.template.core...`);
4. write `docs/blocks.md` and `docs/strategy-roleplay/executor-notes.md` — **these two are the equivalence criteria**; missing one and the instance can compile but cannot work;
5. verify: `<id>` appears in `python3 overleaf.py list-templates`, and `init --conf <id>` builds a project.

## The equivalence checklist (aligned item by item with `cvpr` / `fri`)

**Five pieces, aligned item by item with the two working instances**: the right column is existence, and a missing row is what keeps an instance from working.

| Piece | Existence |
|---|---|
| `template.json` | required (what `list-templates` reads) |
| `docs/blocks.md` | required (the block contract, plus what this venue does not need) |
| `docs/strategy-roleplay/executor-notes.md` | **required** (nouns / failure forms / the four questions in this discipline's words) |
| `assets/` | required when the venue has its own style |
| `preamble.py` | required when `template.json.python` is set |

**One criterion: if `ls instances/<id>/docs/strategy-roleplay/executor-notes.md` finds nothing, do not let the supervisor write `instance: <id>`** — it falls back to default ML reading habits and gets all of Q1–Q4 wrong.
