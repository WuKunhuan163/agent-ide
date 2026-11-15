# Violation ledger

Entries live in `violations.json`. **Read that file directly.** This document only says how to use it and never restates an entry.

```
violations.json     entry definitions: code / title / sign / check / fix
events.jsonl        judgements: one line each, append-only
```

The catalogue is data, not a command's output. **Do not write a parser for it, and do not add a subcommand that prints it.** A catalogue that needs a parser carries a second copy of itself inside the parser, and the two drift. `agent-ide violations` keeps `--log` only, to append one line to `events.jsonl`.

## Counting rules (not negotiable)

1. **Two states only**: `0` (reproduced; streak reset) or `n >= 1` (consecutive runs without reproducing).
2. **Any reproduction resets to zero**, including a streak that had reached 12.
3. **No upper bound on a streak**, and a large `n` never means "cleared" — `n` is just `n`.
4. **Only the user clears an entry**, by logging `--result clear`. Without that event the entry stays however large `n` grows.
5. Every judgement leaves four things: `code`, `result` (pass / fail / clear), `test` (case id), `note` (one checkable piece of evidence), plus a UTC timestamp.

```bash
agent-ide violations --log 18 --result fail --test DILAT-18A --note "spec posted, scene.json untouched, reply said aligned"
```

## The fixed procedure when the user reports a violation

1. **Stop.** Do not continue the task; do not touch any file.
2. Read `violations.json` and compare item by item against the entry's `check` line. Read the tail of `events.jsonl` for that entry's current streak.
3. Give `pass` or `fail`, and put the evidence in `--note` (one checkable sentence).
4. On `fail`, do two things in the same turn: write the `--note`, and change the document the `fix` field names.
5. Before returning to the task, say which document and which rule changed.

## Boundaries between entries (so one act is not counted twice)

- **16 is revoked**: "self-made evidence input" is folded into 2 — fabricating a file and fabricating a conclusion are one act. The historical events logged under code 16 stay in `events.jsonl`; state is counted under 2.
- **1 vs 9**: 1 is answering without looking; 9 is looking but losing control and taking "the closest" as the target.
- **1 vs 4**: 1 asks whether anything was read; 4 asks whether the denominator covered the whole set.
- **6 vs 7**: 6 is a location error (aimed at A, took B, or a section swallowed); its check is structural counts. 7 is a scope error (right location, collateral edits); its check is the diff ratio. The two tests are not interchangeable.
- **11 vs 12**: 11 treats an old note as primary; 12 reads a wrapper line and concludes the original is absent. The first never looks; the second looks only at the surface.

## Adding an entry

Entries are open. When a violation appears that no entry covers, add one to `entries` in `violations.json` and continue the numbering. Two hard requirements: sign, check and fix together; and the check must be findable in the record.

## Appendix A — Entry 2, tightened

1. **Locate to the line**: every judgement gives a line number (`path:line`, or a range). A section number alone (4.2, §2.3) is half-satisfied and counts as a hit.
2. **No compressed metaphor**: renaming two existing quantities (grouping "face count F" and "UV atlas" as "the two tables") is inventing a term, even when the meaning is unchanged.
3. **Say which read it rests on**: when reusing material from an earlier turn instead of reading again, write "from the lines X–Y read in turn N". Omitting it leaves the reader to verify.
4. The criteria sentence precedes the material list; any term in it that cannot be found in a file reproduces the violation.

## Appendix B — Entry 3, fix (from published rule sets)

**The rule (three sentences, promoted to global rule 5)**

1. No files by default: rules, checklists, tables, explanations and records go into the conversation first; to write one, ask "should this be written, and where".
2. Any new file in the project tree is unauthorised unless the turn names its path; a sibling file of the same kind is not authorisation.
3. Intermediate artefacts go to `/tmp` and are declared "temporary, not kept in the project".

**Sources**: `ZarK/ai-quality`'s AGENTS.md forbids decision records, status files, progress reports and implementation plans unless the current issue explicitly calls for stable documentation; `@oh-my-pi/pi-coding-agent`'s write tool states "You NEVER create documentation files (*.md, README) unless explicitly requested"; public CLAUDE/AGENT rule sets carry this as Rule 5 with the addition "Instructions go in chat only".
