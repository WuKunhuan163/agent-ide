# `data/<identifier>/` — one directory per id

**This holds one concrete project's commission**, not part of the method: `data/<identifier>/` sits beside the documents that produce it and contains `WISH.md` (the wish verbatim) and `BOSS_CONTEXT.md` (the context).

## Two disciplines

1. **Read only your own project's id.** The skill package gets copied into other projects together with one project's `data/` — **an id that is not yours (for example `prelim-report` in this package belongs to another project) is never read, never edited, never cited**. Its wish and context are none of your business; reading the wrong one makes someone else's objective yours.
2. **A new project creates its own directory; never reuse another's id.** With no `data/<identifier>/WISH.md`, `skill.md` requires the main agent **to stop and ask the owner for the identifier and the wish**, and **never to invent a近似 id** to fill the slot.

**Criterion**: for every directory in `ls data/` other than your own id, the write count must be 0 (check with `git status` or mtimes).

## On receiving this package, delete the other ids first

**`agent-ide push` copies the whole `data/` across** — so every project receiving this skill sees `data/prelim-report/` (that is the thesis project's wish). **First act after landing in a new project**:

```bash
rm -rf <project>/.agent-ide/skills/overleaf/src/template/docs/strategy-results-first/data/<not-your-id>
```

Keeping it costs more than disk space: analysing the wish, the main agent **reads someone else's wish list**, and because that looks "very complete" it stops asking you for an identifier. **Exactly one id may remain: this project's own.**
