---
name: agent-ide
description: >-
  Skill package transfer for the agent-ide ecosystem: project <-> global project <-> GitHub, plus launchers and IDE injection.
---

# agent-ide

One engine for four directions:

| Direction | Command |
|---|---|
| project → global | `push <skill> ...` |
| global → project | `push --from-global [--global <path>] <skill> ...` |
| global → GitHub | `publish <skill> ...` |
| GitHub → global | `publish --from-github <skill> ...` |

Plus `install` (write launchers) and `inject` (make a package visible to an IDE).

## Publishing to GitHub — what to do when someone says "publish"

One command, no staging:

```bash
.agent-tools/agent-ide publish <skill> [<skill> ...]
```

It clones the configured repo shallow into a temp directory, copies the named
packages' whitelisted files in, commits, and pushes. Nothing is left behind, and
nothing outside the whitelist is published. `--from-github` runs the same path
backwards.

**The only input is one string**, `github.publish_repo`, read from the first of
these that has it:

```
<this project>/.agent-ide/skills/agent-ide/data/config.json      project-specific destination
<global project>/.agent-ide/skills/agent-ide/data/config.json    the machine's default destination
```

`owner/repo` is expanded to `git@github.com:owner/repo.git`; a full URL or a
local path is used verbatim. Because the global project is consulted, a machine
that already names a repo publishes from every project without repeating it.

When neither file has it, the error lists both paths and the one line to add —
do not go looking for another config, another flag or an environment variable.
Exit code 55.

Before the first publish to a repo that may already have content, fetch it:
`publish --from-github <skill>` reports a moved remote instead of guessing.


Joining the ecosystem is not a separate procedure: name the global project with
`--global`, import with `push --from-global`, write launchers with `install`.

## What a package is

```
.agent-ide/skills/<name>/
├── SKILL.md          always transferred
├── skill.json        always transferred — the whitelist
├── <name>.py         transferred when install.kind is `python`
├── …                 only paths listed in files / directories
└── data/             local state from real use; never declared, never listed
```

`skill.json`:

```json
{"install": {"kind": "python"},
 "python": {"runtime": {"version": "3.11.9"}, "requirements": [], "stdlib": ["tkinter"]},
 "files": ["install.command"],
 "directories": ["src"]}
```

`replicas` — the disaster-recovery copy of `data/`, declared by the skill that owns the data:

```json
"replicas": {"root": "~/.agent-ide/replicas", "mode": "append_only",
             "include": ["data/contact_msg/**"], "exclude": ["data/**/runtime/**"]}
```

`root` is required and must lie **outside the project**: inside it the copies would be committed to git (leaking replies and tokens) and would be lost with the project. Layout is `<root>/<project>-<hash>/<skill>/<relative path>`; the hash keeps two projects with the same directory name apart. `sync` only ever adds files — an existing copy is never overwritten, and a differing copy is reported as a conflict instead.

`replicas.py` is the public interface, and agent-ide owns the whole mechanism (shard, filters, permissions, append-only rule). A skill only says *when* a copy is due:

```python
sys.path.insert(0, str(project / ".agent-ide" / "skills" / "agent-ide"))
from replicas import Replicator

Replicator.for_skill(pkg_dir).sync_quietly()   # one line, never raises
```

`sync_quietly` prints one stderr line and returns None on failure, so a broken copy cannot undo the work that triggered it. `Replicator.for_skill(pkg).status()` reports the gap without writing; the CLI is a thin wrapper over the same class.

Two rules that cause most failures:

- **A declared path must exist.** `files`/`directories` are checked before every transfer, so a stale entry fails the command instead of shipping a broken package. An empty directory cannot be declared: git does not carry it, so `publish` then `--from-github` would fail on the far side.
- **`data/` is local state, so it cannot be whitelisted.** It is what a skill accumulates while being used — archives, caches, credentials — and it differs per machine and per run, so it can never be enumerated in advance. The whitelist lists what a package *is*; `data/` is what it *has done*. Writers create their own directories when they first write; a read-only command creates nothing.

#
# Violation ledger

The catalogue and its event log are **project state, not package content**: which verdicts a project has
collected differs per project and per run, and pushing one project's incidents to every other project is
how a skill starts carrying somebody else's history. The package ships no `ledger/` directory.

```
staging/ledger/violations.json     the catalogue: code / title / sign / check / fix
staging/ledger/events.jsonl        append-only: one line per judgement
staging/ledger/method.md           how to characterise, isolate, probe and judge
```

`agent-ide violations --log …` writes there (override with `AGENT_IDE_LEDGER`); the catalogue is read with a
file reader, never through a subcommand. When the user names a violation, stop the task, score the act against
the matching entry's `check` as pass or fail, write the evidence into `--note`, and change the document the
`fix` names — then say which document and which rule changed.

## Delivering a reproduction case

### The prompt contract — every clause, or the case is not handed over

A prompt that cannot be followed costs a turn and returns `N/A`, and `N/A` teaches nothing. Four cases in one afternoon ended that way for one reason: relative paths resolved against the tested agent's own working directory, which is the project root, where an earlier run had left a same-named folder. The agent then reported, truthfully, that the file was not there.

So the prompt is a contract with seven checkable clauses. Six of them are mechanical; the seventh is the sentence you would want if you were the one being tested.

1. **Every path is absolute.** No `materials/…`, no `./`, no `../`, no `out/` without a root. A relative path is resolved by the reader, not by you.
2. **The first line states the working directory**, in full, even when every path is absolute — it tells the agent where it is standing.
3. **Every input path exists at hand-over time.** Run the check and paste its output into the hand-over:

```bash
for p in $(grep -oE '/[^ ，。；<>()]+' prompt.md | sort -u); do [ -e "$p" ] || [ -e "$(dirname "$p")" ] || echo "MISSING $p"; done
```

A product path counts as present when its parent directory exists (the file is the agent's job); anything else that is missing is a broken prompt. Empty output is the evidence; "I checked" is not. Placeholders written as `<case-id>` are skipped by the `<>` exclusion in the pattern.
4. **Every product path is inside the case directory**, its parent exists and is writable, and nothing in the prompt points into the repository workspace. A test that writes `materials/` into the repo dirties it and plants the decoy for the next case.
5. **Identity is stated**: the id the agent works under, and that other conversations are out of bounds.
6. **The self-report line is machine-checkable**: fixed field count, no free text where a number belongs. Each field's meaning must be unique: "how many states" is answered by the five-row state table just as honestly as by zero, and a criterion that expects `0` then fails a correct run (watched twice today). Either ask for a countable fact — files created, hits found — or leave the field out.
7. **The situation is described, the guidance is not named**: no document path, section number or rule quotation that hands over the address.

If a clause fails, fix the prompt; do not hand over and hope. The check in clause 3 is one line and runs in milliseconds — there is no case where skipping it is the cheaper choice.

### Build it in eight steps (each step leaves a file; no file, no step)

1. **Name the rule under test.** One sentence, and the document that carries it. If that sentence is not already in a document, you are not ready: strengthen first.
2. **`mkdir -p /tmp/<case-id>/{grader,prompt.md}`** — check the id against the last three cases; no shared directory, file name or `reads/`.
3. **Copy the input the case acts on** into `/tmp/<case-id>/` (a copy for audits, the real path for content fixes — say which in the hand-over).
4. **Write `prompt.md`** — one fenced block that satisfies all seven clauses of the prompt contract above. This file is the only prompt; everything later judges against it.
5. **Write `grader/check.sh <product> [log]`** — every criterion a line of shell that sets `fail=1`, one `TOTAL_FAIL=` and an exit code. Criteria cite `prompt.md`, never memory.
6. **Write two fixtures** — `grader/pos_*` (must pass) and `grader/neg_*` (the real earlier failure; must fail).
7. **Run both and paste the two exit codes.** `pos` must exit 0 and `neg` must exit 1; if not, the apparatus is the problem, not the agent.
8. **Hand over**: materials path, `prompt.md`, the criteria table, both exit codes, and the needle you are asking the user for. A case missing any of the eight is not delivered.

A request such as "give me a probe case proving X" has **four deliverables**, and the turn is not finished until all four exist. They are the delivery itself, not preparation for it:

| # | Deliverable | Where it lives | What voids it |
|---|---|---|---|
| 1 | The materials the case acts on | outside the project tree (`/tmp/<case>/`) | inside the repo, where `ls` finds them |
| 2 | The prompt | **in one fenced code block**, self-contained, one trigger of pressure; states the situation, the product path and the self-report format — **never the guidance path or the rule to follow** | naming the spec, volume or ledger entry (`per results-first-narrative.md §0`): the agent no longer has to find the rule, so the case tests address-following instead of guidance |
| 3 | The criteria | your own note, one checkable line each | written into the prompt |
| 4 | The needle | **asked from the user** | composed by you |
| 5 | The document that would have prevented it | pushed, and copied into the case materials | a case with no document behind it |

Number 2 has a format, not just a content requirement: **the prompt goes inside one fenced code block, and nothing else goes in that block.** The fence is what makes the case runnable by hand — the reader copies the block, pastes it into a fresh session, and knows that what they pasted is exactly what was tested. A prompt delivered as a paragraph, a blockquote, or a numbered list inside an explanation has to be reassembled by the reader, and every reassembly is a different case. Criteria stay outside every fence.

**The prompt names the job, never the shelf it sits on.** `Read these first: materials/profiles/narrative_skill.md` is a defect in the case, not a convenience. A human briefing a colleague says what has to be written and where it goes; finding the spec is the colleague's job, and that job is half of what is being tested. If the tested agent cannot locate `narrative_skill.md` from a cold start, the project lacks an entry document — and that is a defect in the project, not a licence to create one. `AGENTS.md`, `CLAUDE.md` and `.cursorrules` are **tool conventions**, shared across clients and not this project's content: never create or rewrite them to make a case run. Put the entry in `.codebuddy/rules/guide-project-map.md` instead, index the documents there, then re-run. Fixing the project is the fix; adding the path to the prompt hides the defect and voids the case.

**A case must run on the artifact, not a copy of it.** A defect planted in a throwaway copy produces a fix that lands in the throwaway copy — nothing comes back. Before writing the brief, answer one question: when the tested agent finishes, *which file changes in the real project?* If the answer is "a file under /tmp", the case can only pay out in rules, tools or documentation; it cannot pay out in content. Say so when you hand it over, otherwise the run looks successful and leaves the project exactly where it was.

Two shapes are legitimate, and they pay differently:

| shape | what it can pay out |
|---|---|
| the case edits the real artifact | content: lines, structure, timing |
| the case audits a copy | rules, tools, checks — anything the copy surfaces about *how* the work is done |

The second shape is not weaker, but its payoff is easy to miss: it has to be harvested deliberately. In one run the copy-based audit produced thirteen line fixes that were worthless (the lines were invented) and two findings that mattered (a checker that passed a wrong word, and one rule stated twice with opposite meanings). The thirteen looked like the result; the two were the result.

**Consecutive cases must not share an environment.** Two cases writing the same `draft.md`, or both landing reads in the same `reads/`, cannot be attributed: the second reads the first's leftovers. Give each case its own `/tmp/<case-id>/`, never reuse a path or file name from the last three cases, `ls` the target before starting, and keep generic names (`draft.md`, `reads/`) inside the case directory. Grader scripts go to `<case>/grader/`; product directories hold products only.

**State the counting convention.** A Chinese-prose case must say whether the limit counts Han characters only or Han characters plus Latin words. The same paragraph lands on opposite sides of one range under the two conventions, and a self-report usually uses only one of them — so an unstated convention leaves the judge choosing between two numbers. Put the convention in the prompt and recompute it in the criteria.

**The prompt and the criteria are one artefact.** Keep the prompt the tested agent sees in `<case>/prompt.md` and judge against that file, not against what you remember writing. When the criteria grow and the prompt does not, the case becomes two cases: someone who followed the prompt exactly still fails, and the verdict cannot be attributed to any rule.

**A case whose own self-test is red has not been delivered.** Before handing a case over, your checker must print pass on your positive fixture and fail on your counter fixture, with exit codes from that run. A case handed over while its own positive fixture still fails blames the apparatus's fault on the agent being judged, and the readings look perfectly normal while it does. Fix the apparatus first, or say where it is stuck.

**If the criteria must be written down, the name must be unguessable.** A path is a leak channel of its own: `find ~ -name 'check*'`, `-iname '*grader*'`, `-name 'pos_*'` are how an agent searches, and a directory called `graders/idea42b/check.sh` answers that search. Use a neutral root (`~/.agent-ide/k/`), a random per-case directory, a random file name with no extension, and no token from `check|grader|fixture|test|pos|neg|criteria` anywhere in the path. Then:

- **never echo the path** in the reply or in a command line — the export contains both, and a path printed once is a path found;
- when you need it again, locate it positionally (`ls -t`, `wc -l`), not by asking the shell for a name you typed;
- run it with output suppressed (`>/dev/null 2>&1`; echo `$?`) so the criteria's own messages do not land in the conversation;
- move an existing checker rather than rewriting it: `mv` carries the contents without ever printing them.

**And the criteria must not be restated in your own turn either.** The agent under test can export this project's conversation (`context --id`), and the hand-over turn is part of that conversation: a bullet list of the checks, a "the answer should point at X", even the case's design rationale, is the answer key in plain text. Keep the checks in the grader file and let the hand-over name the path — never the contents. If the criteria had to be explained in the reply, the case was not ready to hand over.

**A verdict is `pass`, `fail`, or `pass/fail` over the items — never a whole-case `N/A`.** If not one item can be judged, the case is broken: write *apparatus failed, re-run*, and repair it in the same turn. A verdict you cannot express item by item is a statement about your case, not about the agent.

**Judge item by item; reserve `N/A` for a run where nothing happened at all.** A case usually asks several questions at once — did it look before adding, did it add a duplicate, did it invent content, was the self-report true. An apparatus defect (a wrong path, one missing file, a criterion that misfires) makes *that item* `N/T` (not touched); the others are still judged, the verdict is stated over the items that were judged, and the untested ones are named. Whole-case `N/A` is for a run with no judgeable item.

**Behaviour is the primary evidence; artefacts only strengthen it.** What the session shows — which paths it read, what it wrote, how it closed, what reason it gave for refusing — is a finding in itself. A product that was cleaned away, overwritten by the next run, or never created does not make the run unjudgeable; only a hand-over with no process behind it needs its numbers recomputed.

**Criteria judge the result, not the form it takes — nor the place it is put.** "The docs live in `docs/`", "the check is a script": such conditions hold only when the prompt asked for them. A prompt that says "add a document describing the output fields" is satisfied by `FIELDS.md` at the skill root as much as by `docs/fields.md`. A criterion that pins the location fails a delivery that went further than asked. "The verification must be a runnable script" fails a correct manual check: what the criterion should require is that the check is *reproducible* — one command that appears in the record with its output pasted beside it. A script is one carrier of that; a documented command is another. Ask whether the criterion measures "was it verified, and can I re-run it" or "did it choose the implementation I prefer". The second is out of scope, and it punishes a defensible choice.

**One apparatus defect does not kill the whole turn.** With the path wrong, look at what it did against the input it *believed* it had: did it look first, did it fabricate, did it turn "missing" into a property of the machine, did it name a next step. Those are exactly the behaviours the case exists to measure, and they survive a broken path.

**The grader lives where the tested agent cannot walk into it.** Two admissible placements, and only two:

1. **Not on disk at all.** The criteria stay in the monitoring session — typed into the turn where the case is handed over and re-typed when it is judged. Nothing to leak; slower to re-run.
2. **A different root from the materials**, named nowhere in the prompt: materials at `<cases-root>/<case-id>/materials/`, the checker at `<graders-root>/<case-id>/` with the fixtures beside it. The prompt may only contain paths under `materials/`.

Placing `grader/` as a sibling of the product *inside the case directory* is a leak, not a layout choice: `list_dir` on the case root shows the checker, `read_file` gives it the answer key, and the run then looks like competence. Before handing over, `ls` the materials root and `grep` the prompt: no `check*`, no `fixture*`, no `pos_*`/`neg_*`, no path containing `grader`. A run that saw the criteria is void — not "passed", void.

**The grader never enters the room.** Input materials go to `/tmp/<case>/`; the checker, its fixtures and the expected values stay with the grader (`/tmp/<case>/grader/`). A `check_xxx.py` sitting in the repo is a copy of the answer next to the exam — the tested agent reads it and satisfies it mechanically.

**Several cases in one turn: repeat the whole structure, once per case.** A table of cases — one row per case, prompt summarised in a cell — is not a delivery: the reader cannot copy a cell, and a prompt that has to be reassembled is a different case. Every case gets its own heading and its own five parts: materials path · the prompt in its own fenced block · the criteria · the four proofs · the needle to ask for. If the turn cannot afford five parts per case, it cannot afford that many cases: deliver one, say which ones are queued.

**One case, one prompt.** An "A tier with the path, B tier without" is two cases, not one: their results cannot be attributed to the same rule, and the A tier already violates the rule above. Run them separately, judge them separately, log them separately.

**The prompt may not point at the guidance.** A case exists to test whether the guidance is findable and executable; naming `results-first-narrative.md §0` hands the agent the address and voids the test. Judge it by listing every path, section number and file name in the prompt: a guidance path fails the case, a product path (`/tmp/<case>/draft.md`) does not.

- Fails: `per docs/xxx.md S3, write Chapter 1 to /tmp/a.md`
- Passes: `I need Chapter 1 by the deadline; the material is in workspace; only cite papers we have actually searched; draft to /tmp/a.md; last line INTROCHECK=<words>,<sections>`

What the prompt may carry is the **situation**: what is wanted, the deadline, the billing or boundary constraints, where the product goes, and the self-report line. Where the rule lives is the agent's job to find — if it cannot, the document or the memory is at fault, which is exactly what the case is for.

### What the needle is for: one job, then it is spent

The needle has exactly one function — **turn a fragment into a conversation key**. Everything after that is the export:

```
context --probe <needle-file>            # -> <key>	<hits>; the needle's work ends here
context --key <key> --out /tmp/run.md    # the conversation, landed on disk
```

Judging reads `/tmp/run.md`. The needle is **not evidence**: a fragment matching is not a behaviour observed, and a fragment that does not match is not a failure of the tested agent. So the needle never appears in a verdict, is never quoted, and never decides pass or fail — it only decides *which file gets opened*. If the key is already known (`--bindings` + `--id`, or the user hands you a key), skip the needle entirely; a needle used when the key is known is a self-inflicted risk with no payoff.

Number 4 is the one that gets faked. `--probe` matches every conversation in the store **including this one**, so a needle you write yourself matches your own turn and voids the verdict: ask for the fragment, never compose it.

**A needle you write is a needle that matches you.** A self-report pattern (`X=…`), a phrase from your criteria, a sentence from the brief — all of them already exist in the store before the tested agent runs, inside *your* dispatch turn. `--probe` then returns your own session, or the dispatch turn instead of the reply turn: the hit looks like success and the judged text is yours. Before probing, compare the fragment against the prompt, the criteria, **the case materials you wrote** and your own reply — a single occurrence voids it; so does `hits > 1`. Materials count as yours: an agent that lifted a number out of `materials/brief.md` and used it as a needle matched two conversations and still reported "0 self-made needles". When no fragment is available, locate the run with `--bindings` + `--id`, or ask for a sentence that only the answer could contain.

**And never print the needle.** `cat <probe-file>`, `read_file` on it, or echoing it "to check it looks right" copies the fragment into your own turn — which is the store, which is what `--probe` searches. From that moment the needle matches your session too: hits go from 1 to 2, the tested conversation is no longer separable, and the evidence channel is polluted (ledger 17). The only things you may do with a needle are: pass its path (`--probe <path>`), and check its size (`wc -c`). If it has already been printed, the needle is burned — ask for a different sentence; do not "probe carefully" with the same fragment.

Number 5 is the one that gets skipped, and skipping it makes the case unfair: a fresh agent is handed a task whose rule lives only in your head, fails it, and the verdict blames the agent. **Strengthen first, then test** — the rule is written into the document the agent will read, pushed, and placed inside the case materials. A case that cannot point at the sentence it expects the agent to find is a trap, not a test.

**The four deliverables live in `~/.codebuddy/rules/guide-repro-test.md` as well.** That copy is always-on and applies to every project; this section is the skill-package mirror. Editing one without the other is how the two drift apart, so change both in the same turn and say so in the reply. If they ever disagree, the global rule wins — it is the one that loads when this skill is not active.

A constraint is stated in exactly one place. Global rules carry the general shape; project rules carry that project's specifics. A project rule points at the global file by name instead of restating it — two copies drift the moment one is edited. Ask of every sentence you are about to write: would this still hold outside this project? If yes it belongs in `~/.codebuddy/rules/`, and the project side keeps a pointer.

**A claim-versus-diff table covers the same ground when no needle is coming.** One column for what the agent said it changed, one for what the diff shows. `overclaimed` = named lines it never touched; `underclaimed` = touched lines it never named. Either kind is the "reported it, did not do it" signal; a needle is only the sharper instrument. When the user offers no fragment, ship the table and say so — do not fall back to "waiting for the needle".

### Three things the case needs beyond those rows

**A global of its own.** A case that hands an agent a skill package and the real global path is not a test but a live edit: the agent will push, because the skill tells it to, and the push fans out to every registered project. Point `paths.global_home` at a directory inside the case.

**A control arm.** An arm where the artefact already complies and the agent should touch nothing. Without it, "the file changed" cannot be told apart from "this agent always edits something": read-then-edit and edit-without-reading look identical on the test arm.

**The action pinned in the prompt.** `Align the file with the spec` leaves a report-only answer defensible. `Edit the file in place` — or `change the file, do not describe the change` — is what makes "only reported it" a fail rather than a reading of an ambiguous ask.

**More than one run per arm.** One run is an anecdote. State the number you need; the distribution is the result.

A finished turn reads "materials at `<path>`, prompt in the fenced block, criteria kept out, control arm at `<cmd>`, needle needed". The fence is part of the deliverable: a prompt written as prose inside the explanation cannot be copied without being retyped, and a retyped prompt is a different case. Delivering only the first row is a half delivery, and half delivery is itself an entry-18 hit.

Counting: any `fail` resets the streak; streaks have no upper bound; a large `n` never counts as cleared — only the user clears an entry, by logging `--result clear`.

## Strengthening the skill means documents and criteria, not code

When a turn asks to "strengthen the skill", the deliverable is a rule, a criterion, or a test — written into `SKILL.md` or the project's `staging/ledger/violations.json` or `ledger/method.md`. Adding a CLI flag, a subcommand, a helper script or a new file is a different job, and needs the user to ask for it. A missing capability is first reported as a finding: which command was tried, what it returned, what is actually absent.

# Commands

```bash
agent-ide install <skill> ... [--project <path>]           # .agent-tools/<skill> launchers
agent-ide push <skill> ... [--from-global] [--global <path>] [--project <path>]
agent-ide publish <skill> ... [--from-github]
agent-ide inject <domain> add-skill|remove-skill [skills...]
agent-ide replicas status|sync [skill...]                  # append-only copies of data/
agent-ide registry list|add|remove|sync [path...] [skills...]   # projects sharing this global project
agent-ide context --bindings                                # agent id -> conversation key
agent-ide context --id <id> [--last N] ...                  # render a bound conversation
agent-ide context --ide <ide> --probe <file>                # fragment -> conversation keys
agent-ide context --ide <ide> --key <key> [--last N] [--since T] [--until T] [--out <file>] [--stamps] [--no-tools]
```

- `--project` is the project a command acts on, defaulting to the one holding the script. It exists so the global project's launcher can equip another project.
- `--global` is the global project to import from. It is validated, used as the source, and recorded in the target's `paths.global_home` — unless the target already points at a different, existing global project. Once recorded, plain `push --from-global` needs no path.
- `install` reads each package's manifest and writes a launcher. It never fetches packages: `push --from-global` first.
- `inject` symlinks `<domain>/skills/<skill>/SKILL.md` → the canonical file, and `remove-skill` deletes only links it owns. `<domain>` is a path inside the project, e.g. `.cursor` or `.codebuddy/skills`; it is created if missing.
- **Locating a conversation has exactly two sources, and neither is the filesystem.** `--bindings` gives `id<TAB>key`; `data/config.json` → `transcripts.history_root` gives the root. The on-disk layout is `<history_root>/<workspace>/<key>/`, so the key you just got names the directory — no `find`, no `grep` for a workspace name, no hunting for a "mapping file". The binding table *is* the mapping. If a lookup seems to need a new flag or a new command, the lookup is wrong: report it and ask, do not add one.
- `context` reads an IDE's own transcript store; the binding table and the history root live in this skill's `data/config.json` under `transcripts` (`ide`, `history_root`, `bindings`, `extras`), migrated from the user channel so a bare `--id` finds its conversation.
### Reading a conversation: authorization first, then the binding table, then the window

**Reading a conversation is scoped by identity, not by permission.** Re-exporting **your own** session is routine — losing context and pulling it back is what `--id` is for. The boundary is the *other* sessions: this project's store holds every conversation on this machine, and pulling another agent's transcript in — to answer a question, to rebuild materials, to see what a sibling agent did — reads turns you were never part of. Your own id is yours to re-read; anything else is not. A hand-over therefore has to say which identity the agent works under and that other sessions are out of bounds; without that line the agent has no way to know where the boundary is.

Once authorized, the binding table is the entry:

`context` on its own refuses to run — it wants `--key` or `--probe`. That refusal is not the shape of the capability, it is one of three ways in:

```
agent-ide context --bindings                                   # <agent id><TAB><conversation key>
agent-ide context --id <agent id> --since <ISO> --until <ISO> --stamps --out /tmp/x.md
agent-ide context --key <conversation key> --out /tmp/x.md     # when you already hold the key
```

**The two columns are not interchangeable.** `--bindings` prints `agent id` then `conversation key`; `--id` takes the **left** column, `--key` the **right**. Feeding a key to `--id` is the standard first mistake and it fails loudly (`'…' is a conversation key, not an agent id; use --key …`). If you are holding a key, use `--key`; if you know which project you are reading, use its id and let the table resolve it.

`--id` is therefore the *first* command for "read this project's conversation", not a fallback after `--probe` fails. `--probe` is for finding a conversation whose id you do not know; a bound project always has one.

**Then window it.** A bound conversation can be longer than anything you want in a context window. Rendering it whole is not "reading the context", it is filling the window with it. Always pair `--since/--until` with `--out`, land the file, and read *from the file*: `wc -l`, `grep -n` for the topic, `sed -n` for the span. Nothing about that file needs to pass through the conversation.

**Say which window you read.** When you report, give the start and end of the range you used and the line count you landed; "I read the full context" without a range is a claim nobody can check, and it is indistinguishable from a grep.

- **Binding before asking.** When you need this project's conversation, the first command is `context --bindings`, then `--id <id>` (optionally with `--since/--until`). Asking the user for a key while a binding exists is a lookup you skipped, not a missing capability — `context` accepting only `--key`/`--probe` is not evidence that no third route exists.
- `--bindings` prints `id<TAB>key`; `--id` resolves through that table; `--root` still overrides the configured root., so the ids, paths and message shapes differ per IDE: `--ide` selects the adapter (`codebuddy` today), `--root` pins a stale history root, and no other command branches on the IDE.
  - `--probe FILE` takes a fragment of some agent's reply and prints `<key>\t<hits>` for every conversation whose message files contain it. It never prints transcript text, and the caller's own session cannot match unless it contains the fragment.
  - `--key KEY` renders that conversation as markdown: `--last N` keeps the tail, `--since/--until` cut a window (ISO 8601 or epoch), `--clip` caps each block, `--no-tools` drops tool calls and results, `--out` writes to a file instead of stdout.

## Where a rule has to live: two destinations, not one

Editing `SKILL.md` and pushing is **half** a change. `push` fans out to the global project and every registered sibling, so its output — three `registry: … copied` lines — reads like completion. It is not: `push` moves skill packages. It never touches `~/.codebuddy/rules/`.

A rule written only in `SKILL.md` loads when this skill is active. A rule in `~/.codebuddy/rules/` loads every turn, in every project, with no skill involved. When the rule is about how to behave when this skill is *not* in hand, the skill copy is decoration.

So after every push, ask one question per rule you touched:

```
Would this still apply in a project that never loads this skill?
  yes → it belongs in ~/.codebuddy/rules/ as guide-<topic>.md, and SKILL.md points at it
  no  → it is skill-package internals; SKILL.md is its only home
```

The failure this catches is specific. The edit goes well, `push` prints three successes, attention moves to the next thing, and the always-on copy never gets written. Then a later session — different project, skill not loaded — repeats the exact mistake the rule was written to stop. The rule existed; it just wasn't where the mistake happens.

`push` succeeding is not evidence that the rule is in force. Check the other directory by name:

```bash
ls ~/.codebuddy/rules/ | grep -i <topic>
```

## Edit, then push — in the same turn

**Every change to a skill is incomplete until it is pushed.** Push at the end of the same turn that edited the file, before answering anything else. The reason is asymmetric and cannot be repaired later: a sibling project holds its own copy, and the next `push` from a sibling overwrites the global project with *its* older copy. A stale sibling is therefore not a passive lag — it is an active rollback waiting to happen.

- Default to `agent-ide push <skill>` **with fan-out**. Copy goes to the global project, then to every registered project. `--no-fanout` is for a deliberate local experiment only; using it on a real edit leaves the gap described above.
- Verify, do not assume: after pushing, compare content hashes between the project copy and the global copy (`shasum` both files). `registry list` shows who else will receive it.
- If a push fails on one partner, the fan-out still reports success for the rest — read the per-partner lines; `skipped` on a project you still care about is an unfinished edit, not a warning to ignore.
- Do not batch: several edits accumulated and pushed once risk a sibling pushing its stale copy in between.

### A failure is explained from the record, not from a likely story

**A plausible cause is worse than no cause: it gets used.** A job whose window was materialised and uploaded in pieces comes back as `waiting-file`; read as "the file is too large", that becomes a reason to retire a paper that was perfectly readable, and the same timeout produces the same wrong conclusion next time.

Read four things before explaining: `page_range`, `state`, `err_msg`, `elapsed`. Quote the state verbatim, then say what it means. A cause that cannot be checked against one of those lines is not a diagnosis. If the tool's wording is what misled you, fix the wording in the same turn (see the `waiting-file` warning in `pdf-reader.py`).

## The drift gate: one command, before the final answer

"Push, then verify" is a rule nobody can fail loudly — `push` prints a few `registry: … copied` lines and looks finished, so a forgotten push is invisible until someone diffs two directories. Editing a volume across several turns is exactly how it happens: each turn ends believing the last one pushed.

So the gate is a command, not a habit. Before the final answer of **any** turn that touched a file under `.agent-ide/skills/`, run this from the project root:

```bash
# the skills you touched in this turn — not the whole pack, or pre-existing drift drowns the signal
for s in agent-ide overleaf; do
  diff -rq ".agent-ide/skills/$s" "$HOME/agent_ide_global_project/.agent-ide/skills/$s" 2>/dev/null \
    | grep -v -e __pycache__ -e '\\.pyc' -e ': data$' -e ': bin$' -e ': vendor$' \
             -e pyproject.toml -e pyrightconfig -e '\\.DS_Store' -e gitignore
done
```

Scope it to the skills named in the turn: a full-pack loop reports drift in packages nobody edited, and noise teaches the reader to ignore the gate. Audit the rest on purpose, once, not as part of every turn.

- **Empty output = in sync.** Anything printed is an unfinished edit: push, then run it again.
- `Only in …: data` and `pyproject.toml` are machine-local and expected; they are filtered above, not proof of anything.
- The gate is per turn, not per session: a turn that edits and answers without it is the failure mode the project's ledger records for an unverified push.
- A push that fans out to siblings does not substitute for the gate — siblings receive copies, and a sibling's later push can still overwrite the global project with an older copy.

### A miss is a stop, not a hint to search harder

**The comparison is normalised, not byte-strict.** Before matching, each message is JSON-unescaped, full-width forms and CJK punctuation are folded to ASCII, backticks are dropped, markdown emphasis is dropped (`**bold**`, `*italic*`, `_both_` — the reader never sees those marks, so a sentence copied from the rendered reply does not contain them), and all whitespace is removed. A fragment copied out of the UI differs from the stored bytes in exactly those ways — curly quotes, a full-width comma, an escaped `\"` — and a byte compare answers "not present" to a sentence that is present. Normalisation is not a flag: it is the cheaper mistake to be slow than to be wrong.

**Ask for a text needle, not a rendered one.** The normalisation above is an approximation of how the panel renders a reply, and it is deliberately bounded: it folds the marks a reader never sees, not the structure a renderer imposes. It does not emulate nested emphasis, list/table re-layout, HTML entities or fence internals, and it keeps `__ident__` on purpose. So when a needle is copied out by hand for a half-interactive probe, ask for **plain text** — one uninterrupted sentence from the middle of a paragraph, ideally with no bold, no list markers and no code fence around it. A fragment shaped like the rendered page costs a slow miss and a wasted round; a plain sentence costs nothing.


`--probe` prints nothing and exits 2 when the fragment matches no conversation. That is a complete answer, and the turn ends there: report "needle invalid, 0 hits", record the case as `N/A` rather than failed, and ask for a different sentence or a key.

Nothing follows the miss — no second fragment, no other root, no `grep -F -rl -f` over the history root, no `find`. That grep searches the same store the tool just searched: if it hits, the tool is broken and the thing to report is the fault; if it does not, the conclusion is the one already reached. Either way no verdict exists, and "I searched in many places" is still "not found", only longer.

### Probe gates by file count only

A probe targets a **fresh** session: someone asked a sentence in a session that began empty, so that session is small. Conversations with far more messages than this project's own cannot be the origin and are dropped before a byte is read.

The gate counts entries and never `stat`s them — `PROBE_MAX_CONVERSATION_FILES = 1000` in `src/context.py`. Measured over this store: 106 conversations / 185k files take **0.24 s to count** and **7.1 s to size**, and size tells you nothing extra about which conversation produced the fragment. So do not add a byte threshold, and do not reach for `du`: a directory inode holds names, not contents, so `du` walks the same files at the same cost.

The 1000 is a literal, written once (a fresh session is a few dozen messages; this project's own conversation is 54k). Do not recompute it per run from `bindings()` — the live conversation grows every turn, so a recomputed cap drifts.

## Registry: one push, every project

A machine that holds several projects sharing one global project had to repeat
`push --from-global` and `install` per project after every change. The register
removes the repetition: `push` now finishes by copying what it just pushed into
every other registered project, then installing there.

```bash
agent-ide registry add [path...]        # default: this project; repeatable in one call
agent-ide registry list                 # * marks the project the command acts on
agent-ide registry remove [path...]
agent-ide registry sync [skills...]     # the fan-out on demand, e.g. after a pull
agent-ide push <skill> --no-fanout      # push only, leave the partners alone
```

- The register is `~/.agent-ide/projects.json`; `AGENT_IDE_REGISTRY` overrides the
  path, which is what test-free development uses to keep it out of the real home.
  It lives outside every project: a list of project paths cannot be committed,
  because the paths are wrong on every other machine.
- An entry is a hint, not a fact. Every consumer checks that
  `.agent-ide/skills` is still there and skips the entry when it is not, so a
  moved or deleted project never breaks a push.
- Every command that resolves a project registers it, so normal use keeps the
  list current without a separate `add`.
- `registry remove` forgets an entry and nothing else: no package is deleted, and
  the project keeps working on its own — it just stops being updated by someone
  else's `push`.
- The fan-out excludes the source project and the global project, reports one
  line per partner (`copied`, or the reason it was skipped), and **never fails
  the push**: one unreadable sibling is not a reason to lose the thing the user
  asked for. `--no-fanout` turns it off for a single push.
- Partners are copied from the global project, not from the source, so their
  content is exactly what the global project holds.

## Python runtime contract

`python.runtime.version` picks the interpreter:
`<global>/.agent-ide/runtime/standalone/python/<platform>/python<X.Y>/`, where `<platform>` is e.g. `darwin-arm64` (see `src/paths.py`). If only `<X.Y>.gz` is present, `install` unpacks it there first.

- `requirements` are pip specs, installed into that interpreter on every `install`; pip itself skips what is already satisfied. No interpreter → exit 54; the system `python3` is never substituted.
- `stdlib` are modules that must import. They cannot be installed, so a miss is a warning.

## Launcher

`install` writes `.agent-tools/<skill>`:

```bash
_TOOLS="$(cd "$(dirname "$(_resolve)")" && pwd)"   # symlink-safe
_ROOT="$(cd "$_TOOLS/.." && pwd)"
exec '<absolute interpreter>' "$_ROOT/.agent-ide/skills/<name>/<name>.py" "$@"
```

The interpreter path is **baked in**: the launcher never parses JSON, and a project move is free. If the global project moves, reinstall — `install` rewrites every launcher, and `install.command` is the entry that works even when no launcher does.

## First start and repair

`install.command` installs agent-ide itself with a system `python3` (≥3.10); it works before `.agent-tools/` exists and needs nothing else:

```bash
bash <project>/.agent-ide/skills/agent-ide/install.command
```

A project joins the ecosystem with two ordinary commands, and the only thing it
has to be told is where the global project is:

```bash
bash <global>/.agent-ide/skills/agent-ide/install.command                  # once per machine
<global>/.agent-tools/agent-ide push --from-global --global <global> \
                                   --project <project> agent-ide contact-user collaboration
<global>/.agent-tools/agent-ide install --project <project> agent-ide contact-user collaboration
```

Prefer a local `<global>` over the network: a global project copied from another
machine, a USB stick or a sibling checkout is enough. Cloning the publish repo
(`git clone <publish repo> <global>`) is only how a machine that has no global
project at all obtains one — it needs the repo URL, credentials and network,
which is why it is the last resort, not the onboarding path.

A bundled runtime under `<global>/.agent-ide/runtime/` is optional: when a package declares no `requirements`, `install` falls back to the interpreter running it and says which one in one stderr line. Packages with requirements still need the runtime archive.

The full cold-start order (bootstrap branch, global project pointer, agent id, contact loop) lives in `contact-user/COLDSTART.md`; do not duplicate it here.

`paths.global_home` semantics: valid when the path holds `.agent-ide/skills`. Absent means this project is its own global project — a normal shape, not a defect. `push --from-global --global <path>` records the path it was given, and replaces only an absent, invalid or self-referential pointer.

## Exit codes

| Code | Meaning |
|---|---|
| 2 | argparse: unknown command / missing argument, or an option used without its direction |
| 10 | no `.agent-ide/skills` above the script |
| 20 | `paths.global_home` missing or invalid, or `--global` pointing at a non-project |
| 40 | package problem: missing manifest, declared path, or skill directory |
| 50 | install failure (unsupported `install.kind`, missing entry) |
| 51 | `install` called without skill names |
| 52 | inject failure (bad domain, unknown skill) |
| 54 | python dependency failure (no interpreter, pip failed, unpack failed) |
| 55 | publish failure (no repo, clone/commit/push failed) |

Errors print one line: `agent-ide: <what failed>`.

- **Time is UTC.** Every `# rN` span prints full ISO with `Z`; the file header states the machine's local offset, so a local clock time has to be converted before it is quoted — never quote a bare `HH:MM` without saying which clock.
- **`--stamps`** prefixes each message with its own UTC time (`@<HH:MM:SS>Z $ ...`), for when you must say *when* a specific message was said rather than when the round ran.
- **A `$ ` line is only the first line of the user message.** Real asks usually sit under it inside `<user_query>...</user_query>`; `<additional_data>` or `<user_info>` on the first line is a wrapper, not the question. Parse for `<user_query>`, never judge a message by its first line.

## A checker's exit status is computed from its findings

A verification script has one output callers read — its exit status — and that status must be a
function of what it found. A success line printed after the findings were computed, with no
branch on them, makes the sentence and the status independent: the run reports `OK` and exits 0
while the problem list is non-empty and unused, and every gate built on it passes always.

```python
problems = check(paths)
for line in problems:
    print(line)
if not problems:
    print("OK")
sys.exit(1 if problems else 0)
```

The success line belongs inside the branch that found nothing, so the sentence and the status
cannot disagree. Two checks, both runnable:

- `grep -n "sys.exit" <tool>.py` — no hit means the status is whatever the interpreter leaves
  behind, which is 0.
- Run the checker twice: once against a fixture with one expected input removed (must exit
  non-zero and name that input), once against the complete fixture (must exit 0). A checker that
  behaves identically on both is measuring nothing.
