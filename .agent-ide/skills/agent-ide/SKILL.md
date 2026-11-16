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

## A hand-off is a fence, not a file

**Any turn whose job is to hand work to another layer ends with exactly one `PROMPT` fence, and the reply is that fence.** Not "I wrote it into `give.md`", not "see the attached", not a `.md` block: **a file is a record of the hand-off; the fence is the hand-off.**

```PROMPT
id: <identifier>
<path to that layer's entry document>
```

- **Inside: exactly two lines** when an identifier exists (`id:` first, path second); **exactly one line (the path)** when the layer has no identifier. Nothing else — no brief, no checklist, no summary.
- **Outside: nothing.** A sentence before the fence ("the context is checked and fixed…") and a paragraph after it ("`room/give.md` is word-for-word identical to the fence above") are **both** the same failure: the receiver reads prose and treats the fence as an appendix.
- **Info string exactly `PROMPT`** — not empty, not `text`, not `code`. Never nest it inside another code block.
- **A turn may carry several fences — each is one complete delivery, and the count must be declared.** One fence is the default; a layer that dispatches independent units may ship 1–5 in one turn. Then: every fence opens with `# purpose` / `# what to do`, dependencies say `depends:#k` and may not be dispatched before that unit resolves, and the **last paragraph states the total** ("this round dispatches N items: …"). **The count is mechanical, not courteous: the user copies by number, and a missing one is a unit nobody runs.**
- **The two ``` are still required — “no ``` inside” does not license dropping them.** A `> PROMPT` blockquote is **not a fence**: `6e562175` shipped one with zero ``` and its own self-check said “exactly one PROMPT fence ✓”. **Criterion: exactly two ``` in the reply, one before the body and one after.**
- **No ``` inside the fence body — the opening and closing ones are the only two.** Need to show a snippet? Use an inline `` `x` `` or indent four spaces. **A third ``` splits the block**: the hand-off reads as two fences, a probe needle taken from it lands outside the fence, and a judge counts one delivery as two. **Criterion: the body contains zero ```.**


**Three ways this still goes wrong, all seen more than once:** ①the work gets written to a file and the reply reports on it (the file is not a delivery); ②the fence carries one line only (path without `id:` — the receiver cannot tell which wish it is); ③the fence is right but buried between a preamble and a follow-up (the reader stops at the prose).

**The rule is in this file, and it was in this file before the last three misses.** So the failure is not “I could not find it”: it is **I never looked at my own draft's last block before answering**. A rule you do not consult at the moment of acting is a rule you do not have — **the fix is a gate, not another copy of the rule.**

**Before answering, one question: is this turn a hand-off?** If yes, the last thing in the reply is the fence, and there is nothing after it. If the answer is a file path instead of a fence, the hand-off did not happen.

**Shipping a case is a hand-off too.** The reply that delivers a case carries one fence whose only content is the path to that case's `prompt.md` (add the `id:` line only when an identifier exists); the case text stays in the file. **Pasting the case text into chat is a second copy of the same object** — and the person forwarding it has to re-select it, which is exactly how lines get lost.

**The launcher is a path, not a command on `PATH`.** Every example below is written `agent-ide …`; in a project the thing to run is `./.agent-tools/agent-ide`, and a bare `command -v agent-ide` returning nothing is the normal case, not the tool being absent. Resolve the launcher once — the project root's `.agent-tools/` first, then `<global>/.agent-tools/` — and use the resolved path for the rest of the turn. Concluding "the tool is missing" from an empty `command -v` is a finding about the shell, not about the skill.

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

**A package is a directory with a declared whitelist, and nothing outside that list travels**: the block below is the shape a reader will see after a push.

```
.agent-ide/skills/<name>/
├── SKILL.md          always transferred
├── skill.json        always transferred — the whitelist
├── <name>.py         transferred when install.kind is `python`
├── …                 only paths listed in files / directories, minus `exclude`
└── data/             local state from real use; never declared, never listed
```

`skill.json`:

```json
{"install": {"kind": "python"},
 "python": {"runtime": {"version": "3.11.9"}, "requirements": [], "stdlib": ["tkinter"]},
 "files": ["install.command"],
 "directories": ["src"],
 "exclude": ["src/<tree holding per-project work>/*",
             "!src/<tree holding per-project work>/_template"]}
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

Three rules that cause most failures:

- **A declared path must exist.** `files`/`directories` are checked before every transfer, so a stale entry fails the command instead of shipping a broken package. An empty directory cannot be declared: git does not carry it, so `publish` then `--from-github` would fail on the far side.
- **`data/` is local state, so it cannot be whitelisted.** It is what a skill accumulates while being used — archives, caches, credentials — and it differs per machine and per run, so it can never be enumerated in advance. The whitelist lists what a package *is*; `data/` is what it *has done*. Writers create their own directories when they first write; a read-only command creates nothing.
- **A `directories` entry carries every file under it, so per-project material living inside the package is kept home by `exclude`, not by the directory entry.** A real identifier beside a template, one project's drafts, one project's run output — a whole-directory entry ships all of it to every project that pulls the package, and no later command can tell it from content. Patterns are matched against the path and each parent directory, in list order, last match winning, `!` putting a path back: the shape is "drop the tree, then name the templates inside it". Three things are enforced rather than promised — `validate` refuses a manifest whose `exclude` swallows something it also declares, the copy leaves excluded paths out of the destination even when an older push put them there, and the read-back digests the same set on both ends, so a correct push is not reported as `missing`.

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

**The judging criterion reads the export panel, never the product file.** Shape items (how many fences, how many lines inside the fence, whether prose sits outside it, whether the delivery is in the reply or in a file) and behaviour items (is there a `execute_command` / `write_to_file` line) **can only come from the export, and each must carry `L<line>`**; the file only verifies whether the content is true (does the number agree with `ls`, does the citation exist). **A criterion with no line number is recorded `unjudged`, and `unjudged` is not a pass** — a verdict containing `unjudged` means the round was not judged to the end. **Judging is valid as long as the four steps are walked and every verdict carries `L<line>`** — there is no judge qualification, and who the judge is does not matter. This file is the complete clause; **the skill borrows no content from machine-local rules**.

**The prompt states only identity, material, what is being judged, and which file to land in; method and format are never written.** Putting things like "hand over `coverage.md` / below 90% read counts as fail / list `seen-not-judged` separately" into the prompt turns the test into copying a list — what it measures is "can it read a list", not "can it find the spec itself". **Criterion: give the prompt to someone who has never read the skill, and they can start but cannot get it right.**

**Before you hand a case over: run this on the block you are about to print.** The rules above are already written five times in this file (§the three lines, §no case directory, §the real tree, §the owner runs it, ledger #22/#23) — writing them a sixth time changes nothing. What changes behaviour is a check that fails:

```bash
# paste the exact block you are about to hand over into /tmp/case.txt
wc -l < /tmp/case.txt                                   # must be 3 (+ the two fences)
grep -nE 'probe|--key|needle|criteria|acceptance|line number|which file|criterion|acceptance line|line number|落哪个文件' /tmp/case.txt   # must be empty
grep -c '^PROMPT$' /tmp/case.txt                        # must be 1
```

**Any hit is a leak, and the leak is always the same one: I answer the question I am asking.** A case prompt that names the method measures obedience, not the document. If the three checks pass, hand it over; if they fail, delete the line — do not "reword it".

**And then there is no case directory at all**: the prompt is three lines inside the fence (`id:` / the layer's entry doc / “you are this layer”), because a real hand-off has nothing else. `/tmp/<case>-xxxx/prompt.md` is **a sandbox wearing a different name** — it tells the agent there is a case, and it gives the judge somewhere to stash a copy. Answer keys live in `~/.agent-ide/k/<prefix>/`, which is a key, not a sandbox.

**When there is no time to isolate, the real project is the sandbox.** From this point on, a case runs **on the live tree**: the agent plays the role and does the role's real work, artefacts land where they really belong, `identifier` is the real `data/<id>/`, and **nothing is copied or seeded**. The write scope still follows the role documents — **a test grants no extra write permission** — and judging still reads the panel and `L<line>` only. **The price is that a wrong product really does land on disk**, which makes the write-scope discipline harder, not looser.

## Four invariants that outrank every format rule

**Before the shape checks, these four decide whether the case is worth running.** They are the same in every project; only the objects change.

1. **It is real work, not a rehearsal.** Unless the owner says "sandbox", the tested agent changes real files and its product is judged by the same bar as a delivery. **A copy cannot reproduce stale readings, window temptation, or a parallel session editing the same file** — so there is no case directory.
2. **The author does not pre-solve it.** Not just "does not run it": for a diagnostic case, **do not grep its config, read its source, or run the command to find the cause first**. If I already know the answer, the criteria quietly become "did it guess my answer", and a better explanation scores as a fail. **My hypothesis goes into `a_pred.md`, never into `criteria.md`.**
3. **Sensory criteria are the body; shape criteria are the fallback.** Write one sentence first — *what must the owner see happen* — and build the criteria around it (was the dispatched work the priority, did the report wait for the run). Checklists, counts, `path:line`, command output are **fallback only**, and never fail a case on their own unless the case is explicitly about procedure compliance.
4. **A case is registered before it runs.** `tmp/reproduce-test/<id>.json`: `id` verbatim, `purpose` (`do_work` / `judge_behavior`), `intent`, `write_domain`, `session_key` empty. **The key found by probing is written back in the same breath** — the next probe reuses it instead of sweeping again.

**Two cases whose `write_domain` overlap may not run in parallel.** They will overwrite each other and neither verdict can be attributed.

## A case without a prediction is not a case

**Every case carries five files, and the fifth is the one that makes me better:**

| file | what it is |
|---|---|
| the `PROMPT` block | three lines, nothing else |
| `cl.md` | the criteria |
| `a_pos.md` / `a_neg.md` | one pass, one fail |
| **`a_pred.md`** | **my prediction, written before the run** |

**A verdict tells me what it did. A prediction tells me whether I knew.** Write three to five falsifiable lines — "it will not open `01-supervisor.md`", "it will `ls -lt` the export directory instead of probing", "it will miss the self-report line at the end of the fence". Then run, then mark each hit or missed.

**The misses are the only material that changes me.** A case where I predicted nothing teaches nothing: it produces "it violated rule N" → another rule → I violate that too. **That loop is why a year of cases has left me unable to predict a single layer's behaviour.**

**Rule:** no `a_pred.md`, no hand-over; and it is written **before** the block is handed over — a prediction written afterwards is a summary.

## A reproduction case is run by the owner, in a new session — never by me

**The cycle is fixed, and no step may be reordered.** I write the case (a copyable `PROMPT`, its criteria, a positive and a negative sample); **the owner copies that prompt into a new session and runs it**; when the owner says it has come back, I take that session's export (`--probe` / `--key`) and judge it.

**I must never ask to take the run.** "Let me be the executor", "I'll run it once to check", "want me to open a session and try" — each of these silently **replaces the agent under test with myself**: a case I run is a case I wrote it to pass, and the only thing it measures is whether I can follow my own instructions. **A delivered case has not been run**; offering to run it is a defect, not diligence.

**I don't nag either.** After the case is delivered, stop and wait for the owner.

## Delivering a reproduction case

**Three things the case must carry before anything else is written:**

1. **A root that the entry path alone determines.** The subject resolves “which tree am I in” from the path it was handed; if the case lives in `/tmp/x/m` while the session sits in the real project, **it will do the right work on the wrong tree** — the output looks fine and answers a different question. Put cases inside the working directory, or make the root explicit and add a criterion for it. **Check the root before judging: if the root is not the case's tree, the whole case is void.**
2. **`id:` as the first line of the hand-over.** Every layer's hand-off starts with `id: <identifier>` and only then the path; the case must ship `data/<id>/{WISH.md, BOSS_CONTEXT.md}`. A hand-over with a path and no `id` makes the receiver guess which wish it is.
3. **Criteria that can be read off the panel.** Before writing one, ask: *which line of the export would support it?* If none, the criterion is unjudgeable and must be deleted. **Every shape criterion carries a count and a position** (how many fences, how many lines inside the fence, inside or outside the fence) — never "whether it understood" or "whether it read carefully".

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
2. **`mkdir -p <cases-root>/<case-id>/`** — check the id against the last three cases; no shared directory, file name or `reads/`.
3. **Copy the input the case acts on** into `/tmp/<case-id>/` (a copy for audits, the real path for content fixes — say which in the hand-over).
4. **Write `prompt.md`** — one fenced block that satisfies all seven clauses of the prompt contract above. This file is the only prompt; everything later judges against it.
5. **Write the criteria as a checklist you read against** — one line each: what must be present, what must not, and the evidence in the answer that settles it. Scripts may help you count paragraphs or pointers; **the verdict is your reading, not an exit code**. Criteria cite `prompt.md`, never memory.
6. **Write two answers by hand** — `pos_*` (what a competent researcher would say) and `neg_*` (the real earlier failure: recites the manual, invents numbers, states a gap as done).
7. **Read both against the checklist and write the two counts.** If the checklist cannot separate them, the checklist is the problem, not the agent.
8. **Hand over**: materials path, `prompt.md` in a fence, the criteria table, the two counts from step 7, and the needle you are asking the user for. A case missing any of the eight is not delivered.

A request such as "give me a probe case proving X" has **four deliverables**, and the turn is not finished until all four exist. They are the delivery itself, not preparation for it:

| # | Deliverable | Where it lives | What voids it |
|---|---|---|---|
| 1 | The materials the case acts on | outside the project tree (`/tmp/<case>/`) | inside the repo, where `ls` finds them |
| 2 | The prompt | **in one fenced code block**, self-contained, one trigger of pressure; states the situation, the product path and the self-report format — **never the guidance path or the rule to follow** | naming the spec, volume or ledger entry (`per execution-loop.md §0`): the agent no longer has to find the rule, so the case tests address-following instead of guidance |
| 3 | The criteria | your own note, one checkable line each | written into the prompt |
| 4 | The needle | **asked from the user** | composed by you |
| 5 | The document that would have prevented it | pushed, and copied into the case materials | a case with no document behind it |

Number 2 has a format, not just a content requirement: **the prompt goes inside one fenced code block, and nothing else goes in that block.** The fence is what makes the case runnable by hand — the reader copies the block, pastes it into a fresh session, and knows that what they pasted is exactly what was tested. A prompt delivered as a paragraph, a blockquote, or a numbered list inside an explanation has to be reassembled by the reader, and every reassembly is a different case. Criteria stay outside every fence.

**The prompt names the job, never the shelf it sits on.** `Read these first: materials/profiles/narrative_skill.md` is a defect in the case, not a convenience. A human briefing a colleague says what has to be written and where it goes; finding the spec is the colleague's job, and that job is half of what is being tested. If the tested agent cannot locate `narrative_skill.md` from a cold start, the project lacks an entry document — and that is a defect in the project, not a licence to create one. `AGENTS.md`, `CLAUDE.md` and `.cursorrules` are **tool conventions**, shared across clients and not this project's content: never create or rewrite them to make a case run. Put a **project map** in the project's own rules file instead (one entry per document, with what each is for), then re-run — That map is **the project's own** and does not go into the skill's global directory. Fixing the project is the fix; adding the path to the prompt hides the defect and voids the case.

**A case must run on the artifact, not a copy of it.** A defect planted in a throwaway copy produces a fix that lands in the throwaway copy — nothing comes back. Before writing the brief, answer one question: when the tested agent finishes, *which file changes in the real project?* If the answer is "a file under /tmp", the case can only pay out in rules, tools or documentation; it cannot pay out in content. Say so when you hand it over, otherwise the run looks successful and leaves the project exactly where it was.

Two shapes are legitimate, and they pay differently:

| shape | what it can pay out |
|---|---|
| the case edits the real artifact | content: lines, structure, timing |
| the case audits a copy | rules, tools, checks — anything the copy surfaces about *how* the work is done |

The second shape is not weaker, but its payoff is easy to miss: it has to be harvested deliberately. In one run the copy-based audit produced thirteen line fixes that were worthless (the lines were invented) and two findings that mattered (a checker that passed a wrong word, and one rule stated twice with opposite meanings). The thirteen looked like the result; the two were the result.

**Feed before you re-issue.** A case measures whatever survived the last round of feeding, so re-issuing before feeding is re-measuring the same weakness — the second run tells you nothing the first did not. Before building the next case: enumerate what the failure could be fed into (the document under test, the rule that governs the behaviour, the methodology, a memory entry), feed all of it, and read the changed document back to yourself to check that the failure is now addressable from inside it. Only then build the case.

**Feed the shared document first; a project-local note is the last resort.** A skill document travels: `push` copies it to the global project and to every registered project, so one edit is one rule everywhere. A memory file does not travel — it belongs to one project's conversation, it is invisible to the next project, and it goes stale the moment the code moves. So when a probe reveals a defect, the first destination is the document under test; the second is the rule or method file of the skill; the third is a violations entry; a memory entry is what you write when the finding is *about this machine* (where a file sits, which needle must be used) and cannot be true elsewhere.

**A document has a size budget, and the budget is spent by refactoring, not by appending.** Every round of feeding adds a paragraph, and a document that only grows ends up as a wall the answering agent skims — the tenth rule is read with the same attention as the first, which is to say none. Before appending, check whether the new rule belongs to an existing block: if a rule and its consequence can be folded into the block that already states the obligation, fold them and delete nothing that is still cited. When a document passes roughly a thousand lines, the next feed is a refactor: move the rationale into the block it explains, merge blocks that say the same thing twice, and drop the sections that no reader path reaches. A rule added to a document nobody finishes reading is a rule that will not be obeyed.

**Feed on the probe's return, in the same turn — and route it by kind.** A finding is one of three things, and each has exactly one home: **a procedure** (how to build, locate, export, judge) goes into the skill document that owns that procedure, then `push`; **a conduct** (how the owner, the evidence or a promise was treated — a paraphrase, a claimed read, a cost billed back) goes into the existing `violations.json` entry, the `rules/*.md` file that states it, and the matching section of the always-on conduct rules **on this machine**; **a machine fact** (path, needle, key) goes into `memory/TEMP_*.md` with an index line. **The two must not cover for each other**: a conduct failure written only into a procedure document becomes a workflow, and a procedure gap written only into the violation list becomes a moral judgement. Say the routing in the reply — `feed: <procedure → path> / <conduct → #code, rules/…, AGENTS §n>` — and if no existing entry matches, strengthen one before adding another.

**Feed on the probe's return, in the same turn.** The moment a probe hands you a transcript and a judged answer, the findings are still cheap to act on: the failing sentences are in front of you and the document that should have prevented them is open. A turn that reads the transcript and stops — deferring the feeding to "before the next case" — has begun the decay: by the next case the finding has become a summary, and summaries do not tell you which paragraph to change. So the sequence inside one turn is: probe → read → judge → **feed** → say what was fed. Building the next case is a separate turn.

**When a question is unanswerable, the correct behaviour is to refuse and state the gap — and the criterion must record that as pass.** Before writing a case, ask of each item: **can this be answered from the material alone?** If not, there are two fixes: supply the material, or write "refuse and say what is missing" into the list. **A list that forces a value to be invented measures obedience at inventing**, and inventing is exactly what these cases exist to prevent. Such an item is recorded `N/T` (not answerable), never `fail`. **A judging case ships two things**: ① **the artefact under check** (the file the answer cites must exist in the material, or only form can be judged); ② **the definition of the acceptance line** (`spec.md` saying "how to write a judgement" is not enough; it must say what counts as passing). Missing either, the reading can only be `N/T` and may not be recorded as the subject's fail. **A placeholder file is not material**: a file holding one `todo:` line has no prose to generalise from and no table to edit — use it as the task and you measure only "can it invent". Before writing a case, **write out what each product file should contain** (table, paragraphs, numbers), and only then let the prompt change it.
**When one criterion keeps failing while every other passes, suspect the question before the answer.** A criterion can be perfectly written and still out of the question's reach: ask "what would this look like told to a person", and no answer will describe how a table's caption is written, because the question was about telling, not writing. Three rounds of the same failure is not evidence about the agent — it is evidence that the prompt never asked. The repair is to widen the prompt's nouns (one more question, phrased in the user's terms), never to write the missing answer into the document a fourth time.

**A criterion only the document can supply — and that is settled before the case ships, not after it runs.** Prove it three ways, all at authoring time: the materials carry no method (a header that says "read by timestamp" has taught the behaviour, so the case is void); the criterion names the line it rests on, `rule: <path>:<line>`; and the product must contain a sentence only a reader of that line would write. A criterion that cannot name its line is measuring common sense. Before crediting the treatment arm with a behaviour, check the control: if the control shows it too, the behaviour is baseline and the criterion attached to it must be dropped or re-scoped — otherwise the next case re-measures a property that was never the document's.

**The prompt travels in a fence labelled `PROMPT` — and that fence is never nested inside another code block.** One extra ```` layer turns the fence into text inside a quoted block: the layer reading it looks for `PROMPT` and finds no commission, so the test is malformed before it starts. To show it to the user, paste the fence itself.

**The prompt travels in a fence labelled `PROMPT`.** One fence per arm, info string `PROMPT` (control: `PROMPT-CONTROL`), the agent-visible text and nothing else inside it; one line outside naming the arm. An unlabelled fence reads as an ordinary quote and is not findable later; the label is what makes the block scannable and copyable in one action. Nothing of yours — no reading of it, no criterion, no note — goes inside the fence, or what gets copied is no longer the case.

**Two probe questions, two needles — never one rule for both.** The needle's legitimacy depends on *whose session you are trying to land on*, not on the tool:

| question | legitimate needle | why |
|---|---|---|
| **read my own context** ("what did I do in this session") | a **nonce you write in this session**, placed at the fixed path `./probe` at the project root, then `--probe ./probe` | only your own conversation contains that string; nothing from the owner is needed |
| **judge a case result** ("what did the tested agent do") | text **the agent under test wrote** — by default the fragment it left in `./probe`; or a fragment the owner hands you | the tested session contains only what it wrote or was given |

**A fragment from your own prompt is not a needle for the second question.** The prompt exists in your own transcript *and* in every arm you ever launched, so a hit does not identify the session — and it is the one fragment guaranteed to be shared. Symmetrically: a nonce you invented does not exist in the tested session at all, so it can never land on it.

**The prohibition, stated per question.** Reading your own context: do not probe a file whose content you neither wrote nor were given. Judging a case: do not probe your own prompt, your own criteria, or a template — and if the tested agent left nothing in `./probe`, ask the owner for the fragment instead of inventing one.

**Fallback for both:** `--bindings` → `--id`, when no needle qualifies.



**And say what was fed, and what was not.** The hand-over carries one line: `fed: <document §, rule file, memory entry>` / `not fed: <what, and why not>`. A turn that builds a case without that line has either skipped the feeding or done it silently, and silent feeding cannot be reviewed while the case is being judged.

**One arm. The agent under test is the treatment arm.** A control arm has to be run too, and the moment it scores the same — or the treatment is judged void — that second run is wasted: two runs bought one reading. Keep the case single-armed, and put the effort into the authoring checks above instead. A case still gets its own room: one working directory holding only this case's materials and that arm's output directory. Sharing one room contaminates the control — the control agent finds the treatment's materials (so "no document given" stops being true) and reads the treatment's answer file (so the control is measuring the treatment). A control that has read the treatment is not a control, and a case whose control was contaminated must be reported as contaminated rather than compared.

**Consecutive cases must not share an environment.** Two cases writing the same `draft.md`, or both landing reads in the same `reads/`, cannot be attributed: the second reads the first's leftovers. Give each case its own `/tmp/<case-id>/`, never reuse a path or file name from the last three cases, `ls` the target before starting, and keep generic names (`draft.md`, `reads/`) inside the case directory. Grader scripts go to `<case>/grader/`; product directories hold products only.

**State the counting convention.** A Chinese-prose case must say whether the limit counts Han characters only or Han characters plus Latin words. The same paragraph lands on opposite sides of one range under the two conventions, and a self-report usually uses only one of them — so an unstated convention leaves the judge choosing between two numbers. Put the convention in the prompt and recompute it in the criteria.

**The prompt and the criteria are one artefact.** Keep the prompt the tested agent sees in `<case>/prompt.md` and judge against that file, not against what you remember writing. When the criteria grow and the prompt does not, the case becomes two cases: someone who followed the prompt exactly still fails, and the verdict cannot be attributed to any rule.

**A case whose two hand-written answers cannot be separated has not been delivered.** Before handing over, read `pos_*` and `neg_*` against the checklist; the counts must differ, and the difference must be on the behaviour the case claims to test. A script's green light is not that proof: a checker that prints passss on your positive fixture and fail on your counter fixture, with exit codes from that run. A case handed over while its own positive fixture still fails blames the apparatus's fault on the agent being judged, and the readings look perfectly normal while it does. Fix the apparatus first, or say where it is stuck.

**If the criteria must be written down, the name must be unguessable.** A path is a leak channel of its own: `find ~ -name 'check*'`, `-iname '*grader*'`, `-name 'pos_*'` are how an agent searches, and a directory called `graders/idea42b/check.sh` answers that search. Use a neutral root (`~/.agent-ide/k/`), a random per-case directory, a random file name with no extension, and no token from `check|grader|fixture|test|pos|neg|criteria` anywhere in the path. Then:

- **never echo the path** in the reply or in a command line — the export contains both, and a path printed once is a path found;
- when you need it again, locate it positionally (`ls -t`, `wc -l`), not by asking the shell for a name you typed;
- run it with output suppressed (`>/dev/null 2>&1`; echo `$?`) so the criteria's own messages do not land in the conversation;
- move an existing checker rather than rewriting it: `mv` carries the contents without ever printing them.

**And the criteria must not be restated in your own turn either.** The agent under test can export this project's conversation (`context --id`), and the hand-over turn is part of that conversation: a bullet list of the checks, a "the answer should point at X", even the case's design rationale, is the answer key in plain text. Keep the checks in the grader file and let the hand-over name the path — never the contents. If the criteria had to be explained in the reply, the case was not ready to hand over.

**A list, not a criterion engine.** The criterion is **a list you read item by item**; the verdict is **your reading**, not a script's exit code (§5 already says: "scripts may help you count paragraphs or pointers; the verdict is your reading"). **You may not write one script to judge a case, and certainly not one script to judge several**: that replaces "reading the answer" with "running a program", crushes four different behaviours into one regular expression, and passes `PASS` off as a judgement. The only permitted use of a script is **assisting a count** (how many items, how many lines, how many pointers), and it **outputs no conclusion**. **One list file per case, one line per item: what to check, what counts as passing, and which sentence of the answer settles it.**
**A verdict is `pass`, `fail`, or `pass/fail` over the items — never a whole-case `N/A`.** If not one item can be judged, the case is broken: write *apparatus failed, re-run*, and repair it in the same turn. A verdict you cannot express item by item is a statement about your case, not about the agent.

**Judge item by item; reserve `N/A` for a run where nothing happened at all.** A case usually asks several questions at once — did it look before adding, did it add a duplicate, did it invent content, was the self-report true. An apparatus defect (a wrong path, one missing file, a criterion that misfires) makes *that item* `N/T` (not touched); the others are still judged, the verdict is stated over the items that were judged, and the untested ones are named. Whole-case `N/A` is for a run with no judgeable item.

**Behaviour is the primary evidence; artefacts only strengthen it.** What the session shows — which paths it read, what it wrote, how it closed, what reason it gave for refusing — is a finding in itself. A product that was cleaned away, overwritten by the next run, or never created does not make the run unjudgeable; only a hand-over with no process behind it needs its numbers recomputed.

**Authoring content is a violation; only three sources may be quoted.** The user's own words, the project's existing files (thesis, ledger, .tex, notes, sample meta), and the literature itself. When none of the three says it, write `PENDING(...)` or say "there is no basis for this here" — do not assemble a plausible-looking list, rubric or spec of your own. A self-authored checklist gets executed by the next session as if it were a rule, which is worse than a missing one. Self-check: every claim in the answer must point to a quoted line, a path, or a section number; the ones that cannot are deleted, not rephrased.

**Criteria judge the result, not the form it takes — nor the place it is put.** "The docs live in `docs/`", "the check is a script": such conditions hold only when the prompt asked for them. A prompt that says "add a document describing the output fields" is satisfied by `FIELDS.md` at the skill root as much as by `docs/fields.md`. A criterion that pins the location fails a delivery that went further than asked. "The verification must be a runnable script" fails a correct manual check: what the criterion should require is that the check is *reproducible* — one command that appears in the record with its output pasted beside it. A script is one carrier of that; a documented command is another. Ask whether the criterion measures "was it verified, and can I re-run it" or "did it choose the implementation I prefer". The second is out of scope, and it punishes a defensible choice.

**One apparatus defect does not kill the whole turn.** With the path wrong, look at what it did against the input it *believed* it had: did it look first, did it fabricate, did it turn "missing" into a property of the machine, did it name a next step. Those are exactly the behaviours the case exists to measure, and they survive a broken path.

**The criteria live where the tested agent cannot walk into them.** Two admissible placements, and only two:

1. **Not on disk at all.** The criteria stay in the monitoring session — typed into the turn where the case is handed over and re-typed when it is judged. Nothing to leak; slower to re-run.
2. **A different root from the materials**, named nowhere in the prompt: materials at `<cases-root>/<case-id>/materials/`, the checker at `<graders-root>/<case-id>/` with the fixtures beside it. The prompt may only contain paths under `materials/`.

Placing the checklist as a sibling of the product *inside the case directory* is a leak, not a layout choice: `list_dir` on the case root shows the checker, `read_file` gives it the answer key, and the run then looks like competence. Before handing over, `ls` the materials root and `grep` the prompt: no `check*`, no `fixture*`, no `pos_*`/`neg_*`, no path containing `grader`. A run that saw the criteria is void — not "passed", void.

**The criteria never enter the room.** Input materials go to the case's `room/`; the checklist, its two answers and the expected values stay with the grader (`/tmp/<case>/grader/`). A `check_xxx.py` sitting in the repo is a copy of the answer next to the exam — the tested agent reads it and satisfies it mechanically.

**Several cases in one turn: repeat the whole structure, once per case.** A table of cases — one row per case, prompt summarised in a cell — is not a delivery: the reader cannot copy a cell, and a prompt that has to be reassembled is a different case. Every case gets its own heading and its own five parts: materials path · the prompt in its own fenced block · the criteria · the four proofs · the needle to ask for. If the turn cannot afford five parts per case, it cannot afford that many cases: deliver one, say which ones are queued.

**One case, one prompt.** An "A tier with the path, B tier without" is two cases, not one: their results cannot be attributed to the same rule, and the A tier already violates the rule above. Run them separately, judge them separately, log them separately.

**The prompt may not point at the guidance.** A case exists to test whether the guidance is findable and executable; naming `execution-loop.md §0` hands the agent the address and voids the test. Judge it by listing every path, section number and file name in the prompt: a guidance path fails the case, a product path (`/tmp/<case>/draft.md`) does not.

- Fails: `per docs/xxx.md S3, write Chapter 1 to /tmp/a.md`
- Passes: `I need Chapter 1 by the deadline; the material is in workspace; only cite papers we have actually searched; draft to /tmp/a.md; last line INTROCHECK=<words>,<sections>`

What the prompt may carry is the **situation**: what is wanted, the deadline, the billing or boundary constraints, where the product goes, and the self-report line. Where the rule lives is the agent's job to find — if it cannot, the document or the memory is at fault, which is exactly what the case is for.

### What the needle is for: one job, then it is spent

The needle has exactly one function — **turn a fragment into a conversation key**. Everything after that is the export:

```
context --probe <needle-file>            # -> <key>	<hits>\t<msgs>\t<bytes>; the needle's work ends here
context --key <key> --last 200 --stamps  # no --out: lands at data/context/<key>.md
```

Judging reads `/tmp/run.md`. The needle is **not evidence**: a fragment matching is not a behaviour observed, and a fragment that does not match is not a failure of the tested agent. So the needle never appears in a verdict, is never quoted, and never decides pass or fail — it only decides *which file gets opened*. If the key is already known (`--bindings` + `--id`, or the user hands you a key), skip the needle entirely; a needle used when the key is known is a self-inflicted risk with no payoff.

Number 4 is the one that gets faked. `--probe` matches every conversation in the store **including this one**, so a needle you write yourself matches your own turn and voids the verdict: ask for the fragment, never compose it.

**A needle you write is a needle that matches you.** A self-report pattern (`X=…`), a phrase from your criteria, a sentence from the brief — all of them already exist in the store before the tested agent runs, inside *your* dispatch turn. `--probe` then returns your own session, or the dispatch turn instead of the reply turn: the hit looks like success and the judged text is yours. Before probing, compare the fragment against the prompt, the criteria, **the case materials you wrote** and your own reply — a single occurrence voids it; so does `hits > 1`. Materials count as yours: an agent that lifted a number out of `materials/brief.md` and used it as a needle matched two conversations and still reported "0 self-made needles". When no fragment is available, locate the run with `--bindings` + `--id`, or ask for a sentence that only the answer could contain.

**And never print the needle.** `cat <probe-file>`, `read_file` on it, or echoing it "to check it looks right" copies the fragment into your own turn — which is the store, which is what `--probe` searches. From that moment the needle matches your session too: hits go from 1 to 2, the tested conversation is no longer separable, and the evidence channel is polluted (ledger 17). The only things you may do with a needle are: pass its path (`--probe <path>`), and check its size (`wc -c`). If it has already been printed, the needle is burned — ask for a different sentence; do not "probe carefully" with the same fragment.

Number 5 is the one that gets skipped, and skipping it makes the case unfair: a fresh agent is handed a task whose rule lives only in your head, fails it, and the verdict blames the agent. **Strengthen first, then test** — the rule is written into the document the agent will read, pushed, and placed inside the case materials. A case that cannot point at the sentence it expects the agent to find is a trap, not a test.

**This section is the copy that must stand alone.** The skill travels to other machines; a global rules directory does not. **A skill document that points at the operator's rules directory for its content is broken on every machine but this one** — so every rule this skill relies on is written here, in full.

A constraint may appear in two places, and each copy must read correctly **on its own**: the skill states it in full (this file travels), and the always-on rules state it in full (that file loads without the skill). **Neither copy points at the other** — a pointer is a dependency, and the machine you hand the skill to does not have your rules directory.

**A claim-versus-diff table covers the same ground when no needle is coming.** One column for what the agent said it changed, one for what the diff shows. `overclaimed` = named lines it never touched; `underclaimed` = touched lines it never named. Either kind is the "reported it, did not do it" signal; a needle is only the sharper instrument. When the user offers no fragment, ship the table and say so — do not fall back to "waiting for the needle".

### The case stack: work it LIFO, author it in parallel where it is free

Cases open against a stack of unclosed findings — the ones in `ledger/violations.json` that no case has ever landed on, plus the ones this session produced. **Reading order is newest-first; closing order is LIFO**: the top item is closed or explicitly deferred with a reason before new work starts.

**Authoring is the exception, and it is a real one: cases that do not depend on each other may be produced in one turn.** Independence has one test — *does this case's criteria rest on a contract another case is currently refining?* If two cases judge different behaviours against documents that are already settled, they are independent and their rooms share nothing, so hand them over together: three cases, three prompts, three needles, one round of yours instead of three.

**Dependency beats the request, including an explicit "give me them in parallel".** When the owner asks for parallel output, the same test decides what is excluded: a case whose criteria quote a contract that another open case is still rewriting must wait (it would be judged against a spec that is about to change, and both readings would be void — exactly the failure that made two arms useless). Name the excluded ones and the reason in one line, ship the rest.

**A case that passes pops; a finding that is not closed does not.** The stack is a work queue, not a history: when a case has been run and the behaviour held, the item **leaves** the stack in that same turn — otherwise the next item, which was waiting on it, never becomes visible, and the owner reads a stack of finished work as an unfinished project. Three rules:

- **Feed first, then prove the feed worked — closing on the feed alone is the exception, not the routine.** Writing the rule down is step one of every finding; the item stays on the stack until a reproduction test shows the rule changes behaviour. Two things make that the default rather than a formality: **an attitude failure and a core skill gap can almost always be simulated** (give the agent the same situation and see whether the same wrong move comes back), so "I fed it" is normally a hypothesis, not a closure. **Close on the feed alone only when the case genuinely cannot be re-staged** — the environment or the context is gone and no stand-in reproduces it — and then write the reason in the same line: `closed: feed <path>:<line>, not testable because <why>`. A bare `closed: feed` with no reason is a hit.
- **A finding that needs only wording still gets its test — the wording is not the evidence.** The usual shape: the behaviour already has a verdict (a case showed it right), and what is missing is the rule that keeps it right. Then the item closes on **both** halves and the line says so: `closed: #10 by case96 c3 (behaviour) + feed guide-answer-the-asked-thing.md:28 (wording)`. A rule written after a pass is a regression guard, and a regression guard without a test is a hope.
- **A reproduction test that proves it fixed is the strongest evidence there is — pop on it immediately.** That is the whole point of authoring one: the item was kept open *because* nothing proved it, so a recorded verdict ends it. Do not ask for a second run, a second opinion, or a "documented" confirmation; a pass is not a hypothesis to be re-checked, and treating it as one is how a closed item sits at the top of the stack and blocks the next one.
- **Pop if and only if the case passed — running it and judging it is not the same thing as it passing.** "I evaluated it" resolves nothing: the verdict has to be *pass*, recorded with the criterion that carried it. A judged **fail** keeps the item where it is and sends you back one step: **feed again** (the document did not do its job, or the case measured the wrong thing), re-author if the criteria were the problem, and re-run. Only the new pass pops; a fail that is followed by more feeding is the normal, healthy loop — a fail followed by a pop is a lie about the state of the work.
- **Build the table before you touch the queue, and let the count fall out of it.** Four columns, one row per item: `item / criterion that judged it / the run's verdict / operation`. Then `closed` is only what the table says, and `old N → new M` is arithmetic, not narration. A speed-up is welcome — one case covering six items is fine — **the accounting after it is not**: a pop list that is off by two is a claim about work that was never done, and it reads as competence right up until someone checks.
- **One criterion pops one item, and the mapping is written down.** `closed: #41 by case92c c3` — one code, one criterion, one line. A criterion that judges "does the reply lead with the quotation" closes the lead-with-quotation item and nothing else; it says nothing about whether the same agent searches before writing rules, even though both are "how it answers". **Grouping items by theme and popping the group is the same lie in bulk**: three judged behaviours cannot settle six, and the reconciliation table will read as if each had a criterion of its own. When in doubt the item stays.
- **Else, pop only on a verdict**: a case run with a recorded result (pass, or pass-with-one-new-defect) pops the item it was authored for; the new defect, if any, is **pushed as its own item**, with the failed criterion quoted.
- **No pass, no pop**: an unrun case, a case judged void, or a behaviour still failing keeps its item at the top. "I fed the document" is not evidence; only a verdict is.
- **New items push, they do not reorder.** A fresh finding goes on top of the stack (newest first); the items below keep their order, so a dependency chain still resolves top-down.

**Migrating the stack is a reconciliation, not a re-write.** Any rebuild — moving from a scratch file into `task-queue`, renaming an instance, collapsing duplicates — must print the old count and the new count and account for every missing item: `closed: <verdict>` or `moved: <where, why>`. An item that is merely absent reads as finished to everyone downstream, including the next you, and it is the quiet version of claiming work that was never done.

**Stop testing when it has served its purpose, then reclaim the instance.** The stack exists to serve the *working* agent: a behaviour is worth a case when a real run would otherwise go wrong. Three consequences, and they pull against the habit of endless verification:

- **A pass is an ending, not a milestone.** Pop it, and when the queue is empty **delete the instance** — a `TEMP_` queue kept "just in case" is the same hoarding as a stack that never shrinks.
- **Do not stack cases the real work will never hit.** Elaborating a case for a situation that does not recur is displacement activity; it reads as diligence and buys nothing.
- **Enough is a number you can state.** Per behaviour, one clean pass plus one independent rerun settles it. A third run answers a question nobody asked, and each extra run costs the owner a session.

**Name a temporary instance `TEMP_…`.** The stack is scaffolding: when the findings are closed it gets deleted, and a forgotten queue should look like one. `TEMP_repro-stack`, not `repro-stack` — the name is the only thing standing between a tidy-up and an orphan nobody dares delete.

**Keep the stack in the task-queue tool, not in a markdown file.** If `task-queue` is installed (`agent-ide install task-queue`, then `./.agent-tools/task-queue`), the stack is one temporary instance of it — `push` per item, `next` for the head, `resolve pass|fail` to close with a verdict, `list` to show the owner what is left. The order then lives in `data/<id>/queue.json` rather than in a reminder to yourself, and the next session can read it without this conversation. **A scratch file under `/tmp` is the fallback, used only when the tool is absent**, and it must carry the same fields (item, verdict, what closes it) so it can be migrated in one move.

## When a run comes back

**A verdict is read off the export, one round at a time.** ① **Frame the round first** (`# rN` or a timestamp interval) — reading across rounds lets the next round's "push and commit" scroll the previous round's hand-over off the screen, so what gets judged is a different thing; ② shape criteria (**how many fences, how many lines inside the fence, whether prose sits outside it, whether the delivery is in the reply or in a file**) come only from that reply body; ③ `* execute_command` / `* write_to_file` / `* read_file` are **behaviour** — **no such line means it was not done**, and the product may not be used to infer it; ④ the file only judges **whether the content is true** (does the number agree with `ls`, does the citation exist).

**Every criterion is written `<criterion> — pass|fail — L<line>`; with no line number it is `unjudged`, and `unjudged` is not a pass.** **The judging must walk that round step by step**: hand over `coverage.md` (one line per `* ` call in the panel, the line ranges read, the ranges unread with reasons); **under 90% read with no reason = the judgement itself fails**. **A line number found by `grep` is an index, not behaviour** — with the arguments and the result out of view, you have not judged what it changed. **"Seen but not judged" (`seen-not-judged`) counts worse than not reading.** **Print the line before citing it**: pointing at a blank line or an unrelated paragraph = no evidence given. **Shape criteria come in pairs** — having counted "how many lines inside the fence", you must also count "how many lines remain before and after it" (when the rule says "the reply is the fence", both sides must be 0); judging only inside the fence exempts all the prose outside it. Three lazy judgements are forbidden: using the delivery file (`give.md`) in place of "is there a fence in the reply", using the self-report (`context-diff.md`) in place of "which files it wrote", using a `grep` result in place of "it ran that command". **Their common move is treating a product as behaviour, so they always judge clean.**

**The criterion reads the export panel, never the product file.** Shape and behaviour items both come from the export and carry `L<line>`; the file only verifies whether the content is true. This file is the complete clause; **the skill borrows no content from machine-local rules**.

Decoding the probe and reporting the score is the first step, not the whole job. A result is **handled** when every finding it produced has a line: `fixed: <where>` / `fed: <path>` / `false positive: <because of my material, not its error>` / `open: <why not>`. **A finding with no line is unhandled**, and proposing the next round before the list is complete is the hurry this step exists to prevent — it is also how a run that contained twelve findings gets reported as one score.

Two habits make the difference: **separate the score from the behaviour** (what commands it ran, what it read first, whether it stayed in scope, whether it verified its own claims), and **let the next round's criteria grow out of this round's blind spots** rather than out of your own interests.

## Simulating a hand-off chain before you test it

A white-box review is not reading documents and saying they look fine. It is **running the chain in your head, one artefact at a time**, and writing down what each stage would actually produce.

**State the chain in its own nouns first, then apply the method — the method has no domain.** A chain is any sequence where one stage's output is the next stage's input: a build (source → object → link → binary), a data pipeline (ingest → clean → aggregate → report), a multi-agent hand-off (request → dispatch → work → review), a document tree (spec → plan → ticket → change). Nothing below depends on which one you are reviewing; if your write-up contains the vocabulary of one particular chain, you have described an example, not extracted the method.

1. **Read every document the chain defines, end to end, in chain order.** Not excerpts: the defect you are looking for usually sits in the section you would have skipped.
2. **Fix one concrete input and carry it through.** A real request, a real input file, a real capability list. Vague inputs produce vague simulations, and vague simulations find nothing.
3. **At each hop, produce the artefact itself, not a summary of it** — the actual record, message, schema or diff that stage would emit, in the shape the documents prescribe (fields, tables, status lines). **If you cannot write it, that hop has no interface**, and that is finding number one: an interface you cannot instantiate is an interface the next stage will invent.
4. **Ask the three questions at every hop**: *who produces this, how does it break, who notices?* The third pays: a break nobody notices is how a system passes its checks while being quietly wrong.
5. **Simulate the choices each participant actually makes, not the ones it is permitted to make.** Rules state what is allowed; a system fails on what a reasonable participant does with those rules in hand — which input it opens first, which branch it takes when two rules both apply, what it writes when a field is absent, whether it invents a value to keep moving. **The gap between "permitted" and "what a participant would actually do" is where most defects live, and no amount of reading surfaces it.**
6. **Simulate the outside re-entering.** Every real chain is interrupted from outside — a new constraint, a narrowed scope, a fragment of context, a changed requirement, a failing dependency, a person overriding a decision. Model that event and ask what the chain does with it: does it become a narrowed check, a replaced item, an added item, a re-planned stage — or is it absorbed into a document nobody re-reads, or silently widening the work? **Chains fail at their boundaries far more often than in their middle.**
7. **Walk the second cycle.** First-cycle output is second-cycle input, and that is where the expensive defects appear: a pointer that moved, a check that passed once and then quietly stopped being true, a record that no longer says which cycle produced it, a stage re-doing work because the state never absorbed it.
8. **Keep four receipts while you work, and publish them with the findings.**
   - **What you read**: one line per document — path and line count — so the reader can tell a review from a skim.
   - **What you resolved**: your findings cite `path:line`; before handing over, re-open every citation and state `resolved: <n>/<m>`. A citation you did not re-open is a guess that happens to be right.
   - **Cross-checks by command**: at least one place where two documents are compared **mechanically** (`grep -n '<the rule>' <a>.md <b>.md`), because a rule stated differently in two files is invisible to careful reading and obvious to a grep.
   - **Where your material ends**: separate "this is a defect in the document" from "this is a gap in what I was given". **A reviewer that reports its own missing inputs as document defects is reviewing its arm, not the system** — and every such confusion costs a real finding its credibility.
9. **Only then design the test**, each broken hop becoming one criterion with a `rule:` line, each finding naming the document and line it contradicts.

**Why the patience is the point:** a test run costs the user a session and can only confirm what the simulation already guessed. Every break found by walking the chain is a run not wasted. **The simulation is cheap, slow and boring; the test is expensive, fast and conclusive — spend the cheap one first, and spend it thoroughly.**

**A worked instance, to show the shape rather than to define the method:** the closed-loop roleplay kept in this repo has four documents (method → commission → plan → execution) and a wish as its input; walking it that way produced twenty-odd breaks across the steps above, none of which needed a real run to see. That is one chain, not the method.

**Say that they are parallel.** The hand-over carries it plainly — "these N cases are parallel: independent because <no shared document / no shared room / different behaviours>; excluded: <case, because it depends on …>". A batch handed over silently reads as a sequence, and the owner runs them one at a time for no reason.

### Three things the case needs beyond those rows

**A global of its own.** A case that hands an agent a skill package and the real global path is not a test but a live edit: the agent will push, because the skill tells it to, and the push fans out to every registered project. Point `paths.global_home` at a directory inside the case.

**No control arm.** One arm, and the material must be shaped so that an agent which has not read the rule cannot produce the required sentence. That is a stronger guard than a second run, and it costs one run instead of two. (An early version of this file asked for a control arm; the pair was dropped after a control scored full marks and made the treatment run worthless.) edits something": read-then-edit and edit-without-reading look identical on the test arm.

**The action pinned in the prompt.** `Align the file with the spec` leaves a report-only answer defensible. `Edit the file in place` — or `change the file, do not describe the change` — is what makes "only reported it" a fail rather than a reading of an ambiguous ask.

**More than one run per arm.** One run is an anecdote. State the number you need; the distribution is the result.

A finished turn reads "materials at `<path>`, prompt in the fenced block, criteria kept out with `rule:` lines, needle needed". **The fence is part of the deliverable**: a prompt described in prose, summarised, or written only into `prompt.md` without being fenced in the turn has not been handed over — the user cannot copy it, and the only copy is one the agent under test may read.

**A delivered case has not been run, and this tool cannot run it.** There is no `run` subcommand; `agent-ide` installs, pushes, publishes, replicates, resolves bindings, renders a transcript, logs a judgement, injects a skill. Delivering a case means: the files exist, the self-test is green, the prompt is fenced, the control arm is named, the needle is asked for. **Executing it is the user's act, in a fresh session, one run per arm per the count you stated.** Language that treats delivery as execution — "I will run it", "let me run this case", "let me start it", "once it finishes I will judge" — is a claim about an action nobody in this turn can take.

**What the turn may then do is judge an export.** After the user has run an arm, the transcript exists; reading it is `context --bindings` → `--id`, and judging is the checker over that transcript. Judging is not running.

**More than one run per arm.** One run is an anecdote: state the number of arms and the runs per arm you need, and say that the distribution, not a single pass, is the result. A case handed over with "run it once" has not been handed over either. a prompt written as prose inside the explanation cannot be copied without being retyped, and a retyped prompt is a different case. Delivering only the first row is a half delivery, and half delivery is itself an entry-18 hit.

Counting: any `fail` resets the streak; streaks have no upper bound; a large `n` never counts as cleared — only the user clears an entry, by logging `--result clear`.

**A result is judged against the threshold that was written before the run, not against a general sense of health.** The threshold lives in the plan the experiment started from — a file, or the turn that launched it — not in memory and not in the field's usual numbers. Three things are not an acceptance:

- **a borrowed metric** — loss shape, gradient magnitude, rendering look. Those belong to another question; a precise reading against the wrong threshold is still the wrong answer.
- **a designed behaviour reported as a defect** — a quantity frozen by the configuration staying frozen is the design, not an anomaly.
- **a verdict-free sentence** — "it ran", "the direction looks right", "the surface did not appear". None of them let the next person decide between stopping and re-running, which is the only thing an acceptance is for.

The step before opening the results: state what the run was meant to establish, the threshold, and where it is written. If that cannot be stated, find it first — reading the numbers before the threshold is how a run gets judged by how good it looks.

**Before a turn that changes anything, five invariants decide whether it may start.** They are cheap to check and expensive to skip, because each one has already cost a turn:

1. **Quote the user's last sentence, then state the result they want, in one line.** If the line cannot be written, the only permitted action is one question.
2. **A sentence about "what it is now" reads the source first** — a path with a line number, or a command's output. Without one, the sentence says "not read", not a guess.
3. **Change only what was named.** A second edit in the same turn is announced before it happens, not explained afterwards.
4. **No new term, no new criterion, no new file** unless the user's words or a project file contain it; a criterion is quoted from a line and cited.
5. **A turn ends with checkable things**: what changed (paths), the number or line that shows it, and what is still uncertain. "Done", "verified", "aligned" are not evidence.

**Reading a sibling project is normal; writing into one is not.** The registry lists the projects that share this global; their trees are readable precisely so a case can be built from them. That is not permission to move, copy in, or "tidy" anything there: a sibling's artefact that looks like a leftover is still that project's state. Quote it, clone it into the case's own root if the case needs it, and keep every write inside the project the session works in.

**A rule document carries rules, and the greps below decide whether it also carries state.** Dates go stale, incident narratives turn a rule into an anecdote, and a count that a command could print is a future inconsistency. Before pushing any method or skill document:

```
grep -nE '\b(19|20)[0-9]{2}(-[0-9]{2}-[0-9]{2})?' <doc>   # a date or year
grep -nE '发生|事故|上次|那天|previously|last time'      <doc>   # an incident narrative
grep -nE '\b[0-9]{2,}\b' <doc> | grep -viE 'exit|code|line|http'  # a number a command could produce
```

Any hit is rewritten: the rule stays, the evidence moves to the ledger row or the case file that produced it.

**A case runs on the real tree, and a pass is adoptable as a patch.** A sandbox copy teaches the shape and proves nothing about the project: the judged answer has to land where the project's own next round would read it. When the case is a fix, the artefact it edits is the working tree, and a pass means that diff could be committed as it stands.

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
agent-ide context --ide <ide> --key <key> [--last N] [--since T] [--until T] [--stamps] [--no-tools]
```

- `--project` is the project a command acts on, defaulting to the one holding the script. It exists so the global project's launcher can equip another project.
- `--global` is the global project to import from. It is validated, used as the source, and recorded in the target's `paths.global_home` — unless the target already points at a different, existing global project. Once recorded, plain `push --from-global` needs no path.
- `install` reads each package's manifest and writes a launcher. It never fetches packages: `push --from-global` first.
- `inject` symlinks `<domain>/skills/<skill>/SKILL.md` → the canonical file, and `remove-skill` deletes only links it owns. `<domain>` is a path inside the project, e.g. `.cursor` or `.codebuddy/skills`; it is created if missing.
- **Step 0, before any case step: transcribe the requirement.** Take the owner's own sentences that state what the case must prove, quote them with `path:line`, and turn each into one acceptance line the product can fail. **The procedure's later steps (prompt, criteria, arms, counts) are shapes; the requirement decides the target, and a shape applied without the target produces a case that looks finished and measures a different question.** If the requirement contains a condition ("without any explicit guidance"), that condition is the first criterion, not a decoration of the prompt.
- **When asked "what did I require", the answer starts with the quote.** Locating comes before explaining: quote the sentences with `path:line`, then, if it helps, one line of mechanism. A mechanism offered before the quote is a story that replaces the answer.
- **Before writing a case, write one line of motive — and keep it out of the prompt.** `discriminates: <behaviour> · pass=<what passing looks like> · fail=<what failing looks like> · ctrl=<the check the control arm must fail>`. This line is yours; the prompt states the situation and the product path and nothing else. **A case whose prompt contains the criteria, the template or the expected report lines measures copying, not behaviour** — and the tell is that a control arm with none of the documents passes too.
- **Before writing a rule, run the three greps and print one `placement:` line.** Grep the project's `memory/MEMORY.md` (does this trigger already have a note), grep `ledger/violations.json` (is there already an entry with this meaning), grep the **owning document** for this layer. Then say which move you made: `placement: index→<file|none> · ledger→#<code|none> · owner→<path>:<anchor> · move=strengthen|add|delete`. A rule added without that line is #27; a second paragraph where one existed is #28; a rule kept in a TEMP_ note when a skill document owns it is #27 again.
- **Ownership, so the grep has a target.** Behaviour toward the owner and the evidence → the always-on conduct rules (machine-local) + `ledger/violations.json`. Tool procedure (context, probe, needles, receipts) → this file. Loop method (position, two kinds of work, rounds, receipts) → `overleaf/.../template/docs/strategy-results-first/execution-loop.md`. Per-layer expectation → `.../strategy-results-first/skill.md`. Layer interface → `01-supervisor.md` / `02-lead.md`. Venue nouns → `03-executor.md`. Machine facts (paths, needles, keys) → `memory/TEMP_*.md`, never a skill document.
- **The conduct list is not in this file and not in your memory: it is `ledger/violations.json`.** The norms live in the operator's always-on conduct rules (machine-local; the skill does not cite them); the entries with `sign / check / fix` live in that JSON; the project's `memory/MEMORY.md` indexes the triggers. **Before writing a rule, grep all three** — an entry that already exists is strengthened (`sign`, `check`), never duplicated, because two entries for one behaviour means neither gets enforced.
- **Locating your own conversation: say something only you could have said, then probe it.** In an IDE (codebuddy included), the cheapest key is a **nonce**: print one distinctive string in your reply — `needle-K7Q2-2f9c` — write that exact string to a file, and run `--probe <that file>`. The nonce matches only the conversation that contains your sentence, so the answer is your own key with no guessing. **Never probe a file whose contents you did not write** (`./probe`, someone else's fragment, a template): you cannot know which conversation it lands on, and a probe whose needle you did not author is a shot in the dark that reads like a measurement.
- **The owner's sentence carries an access strategy; obey it before choosing a window.** "before I lost my temper", "since the last cleanup", "from yesterday until now", "just the last thirty minutes" — these are **bounds on the read**, not colour. Turn one into an anchor: find the boundary event in the export by timestamp, then read the side the owner asked for. Reading across the boundary is how a question about "before the explosion" gets answered with the explosion.

**Before reporting a state "at time T", prove the segment covers T.** Line ranges are not time: a block at `:2298262` can be ten minutes before or ten after the blow-up, and the answer changes. Print the boundary — `# rN 2026-11-14T17:0…` — and the span you actually read, then say whether T falls inside it. A quotation without its timestamp is not evidence about *when*.

**Read a window backwards.** The bottom of the export is the present; the top of the window is already history. Read **newest → oldest** and stop as soon as the question is answered — the first hit going forward is usually the statement that a later message corrected. A window read forwards answers the project as it was three complaints ago.
- **The default window is the recent one, not the whole file.** `--key` writes the export to its one idempotent path and prints `path · lines · bytes`; it never prints the text. Reading starts from the **tail** (`--last 40`, or `tail -n` on the file) unless the owner named a time or a keyword — then `--since/--until` or a `grep -n` on the file, and the grep's line numbers are the window. A conversation of 2.3 M lines cannot be "read whole"; what can be read is the window that answers the question, and **the question is almost always about what just happened**.
- **Resolution order for "where in the conversation is this":** (1) **the tail** — what the owner said in the last few turns is the referent, by default and without being asked; (2) a **time window**, only if they named a time; (3) a **keyword**, only if they said the keyword. **A keyword I chose myself is not a search, it is a substitution**: it returns a topically similar passage from an old round, the answer then addresses that passage, and the drift is invisible because the material was real.
- **`--out` no longer exists (it was removed).** The path is fixed per key, and every render rewrites it, so a second export is never a second file: if a copy is genuinely needed, `cp` the one file. Two exports of one key is how a stale dump outlives the conversation it describes.
- **`--bindings` → `--id` is the fallback, not the first move.** When the nonce route is unavailable — a non-IDE host, probes disabled, or a store that drops large conversations — take `--bindings` (prints `agent id<TAB>conversation key`) and render by id. Both routes end the same way: the render lands at `data/context/<key>.md` on its own, then a receipt naming the path, the line range and the count.
- **"Probe this" is a verb with a procedure, not a metaphor.** When the owner says *probe* — "probe that run", "probe-check what the executor did" — they are naming this tool. Four steps, in order: take the needle the owner gave (a path, never its contents), run `--probe <needle>` once and read `key / hits / msgs / bytes`, export that conversation with `--key`, then read the **artefacts** it wrote and judge from them. "Probe" never means *look around and see what happened*, and it never means *guess from the latest files on disk*: without a needle there is no probe — ask for one. When a turn says "probe" and you have no needle, the correct first move is the question, not a search.
- **One question, one command, and never a search.** "Which conversation does this fragment belong to" is answered by `--probe <needle>` alone: it prints `key`, `hits`, `msgs`, `bytes`, and all four columns are read before anything is concluded. `--bindings` answers a different question — which conversation *this project's* agent id is bound to — and it is not a list of conversations. `history_root` exists only so that a stale detection can be overridden with `--root`; it is not a directory to enumerate, and `ls`/`find`/a module import against it is not a locating step.
- **When the probe's answer is not the one you expected, run the same command again.** A needle that changed returns a different key; that is the designed behaviour, not a broken tool. Three failed attempts at locating is the signal to ask for a needle, not to open a fourth door — a person with no context does not know which door exists, and a document that leaves four open lets them try all four.

- **Locating a conversation has exactly two sources, and neither is the filesystem.** `--bindings` gives `id<TAB>key`; `data/config.json` → `transcripts.history_root` gives the root. The on-disk layout is `<history_root>/<workspace>/<key>/`, so the key you just got names the directory — no `find`, no `grep` for a workspace name, no hunting for a "mapping file". The binding table *is* the mapping. If a lookup seems to need a new flag or a new command, the lookup is wrong: report it and ask, do not add one.
- `context` reads an IDE's own transcript store; the binding table and the history root live in this skill's `data/config.json` under `transcripts` (`ide`, `history_root`, `bindings`, `extras`), migrated from the user channel so a bare `--id` finds its conversation.
### Reading a conversation: authorization first, then the binding table, then the window

**Reading a conversation is scoped by identity, not by permission.** Re-exporting **your own** session is routine — losing context and pulling it back is what `--id` is for. The boundary is the *other* sessions: this project's store holds every conversation on this machine, and pulling another agent's transcript in — to answer a question, to rebuild materials, to see what a sibling agent did — reads turns you were never part of. Your own id is yours to re-read; anything else is not. A hand-over therefore has to say which identity the agent works under and that other sessions are out of bounds; without that line the agent has no way to know where the boundary is.

Once authorized, the binding table is the entry:

`context` on its own refuses to run — it wants `--key` or `--probe`. That refusal is not the shape of the capability, it is one of three ways in:

```
agent-ide context --bindings                                   # <agent id><TAB><conversation key>
agent-ide context --id <agent id> --since <ISO> --until <ISO> --stamps
agent-ide context --key <conversation key> --last 200 --stamps   # when you already hold the key
```

**The two columns are not interchangeable.** `--bindings` prints `agent id` then `conversation key`; `--id` takes the **left** column, `--key` the **right**. Feeding a key to `--id` is the standard first mistake and it fails loudly (`'…' is a conversation key, not an agent id; use --key …`). If you are holding a key, use `--key`; if you know which project you are reading, use its id and let the table resolve it.

`--id` is therefore the *first* command for "read this project's conversation", not a fallback after `--probe` fails. `--probe` is for finding a conversation whose id you do not know; a bound project always has one.

**Then window it.** A bound conversation can be longer than anything you want in a context window. Rendering it whole is not "reading the context", it is filling the window with it. Always pair `--since/--until` with `--stamps`, land the file, and read *from the file*: `wc -l`, `grep -n` for the topic, `sed -n` for the span. Nothing about that file needs to pass through the conversation.

**Say which window you read.** When you report, give the start and end of the range you used and the line count you landed; "I read the full context" without a range is a claim nobody can check, and it is indistinguishable from a grep.

- **Binding before asking.** When you need this project's conversation, the first command is `context --bindings`, then `--id <id>` (optionally with `--since/--until`). Asking the user for a key while a binding exists is a lookup you skipped, not a missing capability — `context` accepting only `--key`/`--probe` is not evidence that no third route exists.
- `--bindings` prints `id<TAB>key`; `--id` resolves through that table; `--root` still overrides the configured root., so the ids, paths and message shapes differ per IDE: `--ide` selects the adapter (`codebuddy` today), `--root` pins a stale history root, and no other command branches on the IDE.
  - `--probe FILE` takes a fragment of some agent's reply and prints `<key>\t<hits>\t<msgs>\t<bytes>` for every conversation whose message files contain it: how often it matched, then how big that conversation is. The size is part of the answer -- 2 hits in 12 messages is a fragment quoted somewhere, 2 hits in 414 messages is the session itself. It never prints transcript text, and the caller's own session cannot match unless it contains the fragment.
  - **`--last N` and `--since/--until` only parse the files that can contribute.** mtime decides the candidate window; the message's own `at` still decides inclusion. Measured on a 110k-file conversation: a full read parses 28 s worth of JSON, `--last 2` parses a few hundred files and finishes in 1.5 s warm (4.9 s cold — 3.5 s of that is `stat` on 110k files). A bare `--key` with no window still reads everything, so bound it.
  - **The size decides whether the key is still findable.** A conversation above `PROBE_MAX_CONVERSATION_FILES` (2000 message files) is dropped before it is read, so nothing in it can ever be probed. `--probe` warns on stderr once a hit sits at 70% of that cap; a key past it does not warn, it simply stops matching. If a fragment provably exists and no key comes back, read the drop count on the `probe:` line before concluding the fragment is absent.
  - **One key, one export file.** There is no `--out`: the path is `<global project>/.agent-ide/skills/agent-ide/data/context/<key>.md`, created on demand. There is no flag to name another path, and the refusal names the path to use. `--last`, `--since` and a newer conversation all rewrite that same file, so there is one copy to read and one to delete — never a second copy in `/tmp` that still looks authoritative a week later.
  - `--key KEY` renders that conversation as markdown: `--last N` keeps the tail, `--since/--until` cut a window (ISO 8601 or epoch), `--clip` caps each block, `--no-tools` drops tool calls and results, and the write target is fixed (no flag) instead of stdout.

## Where a rule has to live: two destinations, not one

Editing `SKILL.md` and pushing is **half** a change. `push` fans out to the global project and every registered sibling, so its output — three `registry: … copied` lines — reads like completion. It is not: `push` moves skill packages. It never touches the always-on rules directory on this machine.

A rule written only in `SKILL.md` loads when this skill is active. A rule in the always-on rules directory loads every turn, in every project, with no skill involved. When the rule is about how to behave when *this skill is not loaded*, the skill file is the wrong home — but **the skill must still state the rule in full for its own readers**, because the two files travel separately.

So after every push, ask one question per rule you touched:

```
Would this still apply in a project that never loads this skill?
  yes → it also goes into the always-on rules **on this machine**, as a full mirror copy; SKILL.md still states it in full — never as a pointer
  no  → it is skill-package internals; SKILL.md is its only home
```

The failure this catches is specific. The edit goes well, `push` prints three successes, attention moves to the next thing, and the always-on copy never gets written. Then a later session — different project, skill not loaded — repeats the exact mistake the rule was written to stop. The rule existed; it just wasn't where the mistake happens.

`push` succeeding is not evidence that the rule is in force. Check the other directory by name:

```bash
ls <your rules directory>/ | grep -i <topic>
```

(This check runs only **on the machine that writes the mirror** and **does not enter the skill's body**: the skill's reader has no such directory.)

## Edit, then push — in the same turn

**Every change to a skill is incomplete until it is pushed.** Push at the end of the same turn that edited the file, before answering anything else. The reason is asymmetric and cannot be repaired later: a sibling project holds its own copy, and the next `push` from a sibling overwrites the global project with *its* older copy. A stale sibling is therefore not a passive lag — it is an active rollback waiting to happen.

- Default to `agent-ide push <skill>` **with fan-out**. Copy goes to the global project, then to every registered project. `--no-fanout` is for a deliberate local experiment only; using it on a real edit leaves the gap described above.
- Verify, do not assume: after pushing, compare content hashes between the project copy and the global copy (`shasum` both files). `registry list` shows who else will receive it.
- If a push fails on one partner, the fan-out still reports success for the rest — read the per-partner lines; `skipped` on a project you still care about is an unfinished edit, not a warning to ignore.
- Do not batch: several edits accumulated and pushed once risk a sibling pushing its stale copy in between.

### Before the edit: read the block, then say which of three operations it is

**No edit starts with the write.** Three steps, in this order, and the record must show them:

1. **Grep the target document** for three or four synonyms and quote the existing same-meaning passages **with line numbers**. If one exists, the new rule is not a new section.
2. **Name the site**: `path:line-line`, the two blocks the insertion falls between. Both must still be whole afterwards — **a heading that loses its table is a structural loss even when every line survives** (entry 53).
3. **Declare the operation**: correct (fix a wrong sentence) / strengthen (add a clause inside the block that already says it) / append (only when nothing covers it) / **refactor** (change no claim, only the arrangement: merge duplicate blocks, gather scattered same-meaning clauses into one, split a block carrying two subjects, delete what is superseded). Say why not the other three. **Refactor is the only one of the four that may net-delete lines** — and the easiest to reach for when what you actually need is strengthening: if the sentence you want to add is already said, strengthen that block, do not restructure around it.

**Two readings after the edit**: `grep -c` of the synonymous keyword is **1, not 2**; and each block adjacent to the insertion point still has its heading and its body.

**Why**: 2026-11-15 I appended a whole section on the owner's delivery format to `strategy-results-first/skill.md` while `skill.md:86-94` already said it with an example — the new section duplicated it and landed under `## How the work is judged`. Entry 64.

### A failing command is reported by its exit code and its error line

The first sentence of the report carries the exit code and the command's error line, verbatim, before anything else is said. Not "done", not "the rest looks fine": those are conclusions drawn from a run that failed, and the error line they skip is the only part the next reader cannot reconstruct. What follows is what was attempted; the assessment comes only from a re-run that succeeded. This block is also the operative home of the conduct entry that names the same failure, so the rule outlives the session it was learned in.

### A failure is explained from the record, not from a likely story

**A plausible cause is worse than no cause: it gets used.** A job whose window was materialised and uploaded in pieces comes back as `waiting-file`; read as "the file is too large", that becomes a reason to retire a paper that was perfectly readable, and the same timeout produces the same wrong conclusion next time.

Read four things before explaining: `page_range`, `state`, `err_msg`, `elapsed`. Quote the state verbatim, then say what it means. A cause that cannot be checked against one of those lines is not a diagnosis. If the tool's wording is what misled you, fix the wording in the same turn (see the `waiting-file` warning in `pdf-reader.py`).

## A miss is reported as an omission, never as a situation

**When something was missed, the first sentence is what I did not do — in the first person, checkable, with the line that proves it.** Not what the documents did, not what the prompt said, not what the schedule allowed.

| Not this | This |
|---|---|
| "the rule is not where I would read it" | "I did not look at the last block of the draft before answering (`SKILL.md` §A sits in the same file)" |
| "the prompt told me to write to a file" | "my prompt said 'write into `give.md`' and turned a hand-over case into a writing case; the prompt was mine" |
| "there was no time" | "I skipped the `grep -c` recheck when closing, so the silent replacement failure went unnoticed" |

**Why the situation-form is worse than the miss**: it converts a missing check into a missing condition, so **nothing gets added where the failure happened** — the next run has the same hole and the same explanation. **An explanation whose subject is not me is a refusal to fix.**

**Three checkable forbidden sentences** (any occurrence is a breach; see `#65` in `ledger/violations.json`): ① "the rule is not here / not where I can read it" ② "the prompt or document did not require it, so …" ③ "time or the environment did not allow it". **The replacement format is fixed at three sentences**: ① what I missed ② which line proves it (`path:line` or command output) ③ which gate catches it now.

**If the rule genuinely was absent, prove it** — give the all-zero `grep` output or the file's `path:line`, **and still say first what you missed**. "It does not exist" is **evidence**, not an **opening line**.

## The fence gate: look at your own draft's last block, before the final answer

**Same shape as the drift gate: a mechanical check, not a resolve to remember.**

```
Is this turn a delivery? (handing work to a layer / shipping a case / passing a decision on)
  yes → is the LAST block of my draft a `PROMPT` fence?
          no  → stop. Put the fence there, move everything else into the file, delete prose after it.
          yes → is anything non-empty after the fence? → delete it.
  no  → this gate does not apply.
```

**Read the draft, not the intent.** The failure mode is not “I forgot the rule” — it is “I never looked at the end of what I was about to send”. **Three deliveries in a row went out without a fence while this rule sat in the same file, in bold.** A rule that is only recalled is a rule that is skipped; **this is why the check is on the artefact and not on memory.**

**One line is enough**: `fence gate: applies → last block is PROMPT (id, path) → nothing after it.` If that line cannot be written truthfully, the delivery is not ready.

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

The gate counts entries and never `stat`s them — `PROBE_MAX_CONVERSATION_FILES = 2000` in `src/context.py`. Counting is cheap relative to the substring scan it guards, which is the whole reason the cap can be this high.

The 2000 is a literal, written once. A fresh session is a few dozen messages; a long-running one can exceed the cap and is then dropped before the scan. Do not reco

## Working trees: the project's state is not a scratch pad

**Production directories hold products, and nothing else.** A directory the project's own tools read — compiled output, generated sources, the engine — holds only what those tools produce. Ledgers, check scripts, trial PDFs, `__pycache__`, `.state/`, half-edited copies: all of it lives under `staging/`. The rule is not tidiness; a stray file in a generated directory is indistinguishable from a product on the next run.

**Nothing is moved, archived or deleted before a person has looked at it.** "Tidying up" after a mistake is how evidence disappears: a directory moved to make an error look smaller is a directory the user can no longer check. Rename nothing, delete nothing, archive nothing on your own initiative — the report of a mistake never requires moving the file that shows it.

**A README states what the thing is, never where it stands.** Numbers and status labels change every day; written into a README they require the whole document to be re-synced each time, and the first missed sync makes it contradict itself. Status belongs in the ledger, where it is dated and attributable.

**`push` carries the package, and nothing else.** Three things stay where they are and must be checked by name:

| Not carried | Where it lives | How to check it |
|---|---|---|
| the behaviour rules | the operator's always-on rules directory (machine-local; the skill body does not cite it) | read the file you edited there — it is in no registry |
| the project's memory | the per-project memory directory on this machine | per project, never shared, invisible to the next project |
| the project's data | `<skill>/data/` | local state; the diff gate is expected to show it and must not be "fixed" |

So `push` printing three registries `copied` is not a sync claim. A sync claim names the registries **and** says which files outside them were edited and where they were verified. A rule file edited and never re-read is a rule that may not exist under the name the next session will look for.

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

**Exit codes are the only branch a script may take**: the printed text is for humans and may change.

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

## Finding yourself: probe with no cap, and read bindings first

**A long conversation is not unprobeable — it needs `--max-files 0`.**

```bash
# 1) who am I, if this session is bound
./.agent-tools/agent-ide context --ide codebuddy --bindings
# -> <agent id>	<key> (config: transcripts.bindings)

# 2) otherwise probe a sentence you actually wrote, with the cap off
printf '%s' '<a sentence from the reply you are looking for>' > /tmp/needle.txt
./.agent-tools/agent-ide context --ide codebuddy --probe /tmp/needle.txt --max-files 0
# -> key	hits	msgs	bytes (best hit = most hits, then most msgs)
```

**Why the cap exists and why it must be lifted here.** The default `PROBE_MAX_CONVERSATION_FILES = 2000` drops whole conversations before reading them, on the assumption that a needle names a *fresh* session. A main session breaks that assumption by growing: measured on this machine, **73,836 message files** (1.09 GB) — silently dropped, so every fragment taken from it returned `0 hits`.

**Cost.** With the cap off the store is ~201k files; the scan runs in a process pool (more than 20k files) and takes **~38–40 s**. That is the price of finding yourself; pay it, do not report a miss you did not actually test.

**Progress prints at seven marks only** — first file, 1%, 2%, 5%, 10%, 20%, 50%, 100% — because a 200k-file scan at 500-file ticks erases itself. Before the result line a one-line separator (`# below is the result: key<TAB>hits<TAB>msgs<TAB>bytes`) says what follows; stdout itself stays the clean table.

### Named id vs this conversation — two different lookups

**When the owner names an id (an identifier, "that project's full context", "look at that person"), the binding is authoritative: `--bindings` → that id's key → `--key`. No probing, no best-hit guessing.** The binding is the owner telling you *which* conversation they mean.

**When the owner means the conversation you are in ("this session", "what you wrote above", "this stretch"), bindings are useless and can be actively wrong**: the bound key may be a *different* session.

**The tell.** A binding hit whose matches are `PROMPT` fences or quoted material is the case-authoring session, not the one you are in. Check what the hits *are*, not only how many.

### `--max-files 0` is for *your own* session, not for someone else's

The cap exists because a **main** session grows past 2000 files. A **case** session is 20–40 messages: the default cap finds it in seconds, and lifting the cap turns a 7-second lookup into a 40-second scan of 200k files for no gain.

- **needle from a case / another agent → default probe.** No `--max-files`. If it misses, the needle is wrong, not the cap.
- **needle from the session you are sitting in, or the bound main session → `--max-files 0`.** That is the only reason to lift it.
- **Decide before you run**: whose sentence is this, and how big can that conversation be? **Reaching for `0` out of habit is a 6× slowdown on every lookup that did not need it — and it hides a wrong needle behind a long scan.**

**The result table has five columns: `key`, `hits`, `msgs`, `bytes`, `last`.** `last` is the newest stored message's UTC time. **Rows sort by `hits`, then by `last`** — so when one needle hits several conversations, the newest one is the first tie you can break, and you can tell "the run I just finished" from "an older session that quotes the same words" without opening either.

**Pick by key, not by needle.** A needle drifts: the same sentence gets quoted into later sessions, and a needle that hit one conversation yesterday can hit another today. **The key is the identity; the needle is only how you found it.** After the first probe, keep the key — re-read that conversation with `--key <key> --stamps`, and never re-probe a needle to answer "look at it again".

**If you have no key, say so.** No key means that conversation was never probed: write it down as missing context and ask the owner which one they mean (which unit, which round, roughly when). **Guessing a key costs more than asking for one.**

**Reading the result.** `probe: 160/163 conversations kept (> 2000 files dropped: 3)` means three sessions are invisible. **Check that line before saying "the needle is invalid".** A hit on the session you are in is the only proof that you located yourself; quote `key`, `msgs`, `bytes` as the receipt.

## What the reading must decide: guidance, not luck

**A criterion is not "did the answer come out right" — it is "did the expected guidance produce the action".** An agent that guesses the right format has passed nothing: the same agent meets the next project with a different convention and guesses wrong. So every criterion names **the document, memory entry or rule line that should have caused this action**, and the reading asks two questions:

1. **Locating** — did the reply show it *found* that source? A path with a line (`01-supervisor.md:19`), the command that opened it, a quote from it. "I followed the convention" with no path is indistinguishable from having invented one.
2. **Following** — does the action match what that line says, including its exceptions?

**The three failure shapes, and how each looks in a reading:**

| shape | what the transcript shows | what it is called |
|---|---|---|
| **wild search** | `find` / `grep -r` across the whole tree, several guesses, no source named | native search that happened to end somewhere |
| **wild fit** | the answer follows *one* of two files without saying which or why; or follows both | convention chosen by convenience |
| **wild guess** | a plausible format with no source at all — and, worse, an admission like "I added that scope myself" | fabrication wearing the project's name |

### Walk the trace, or the reading is about the product

**A quoted line proves the document was *read at some point*; it does not prove it *steered the action*. Quotes can be pasted after guessing.** So the reading starts with the **action trace** — the tool calls in order, from `context`'s `* name {...}` lines — and every step is classified:

| class | looks like | what it means |
|---|---|---|
| **locate** | `read_file` on the document that should govern this move, **before** the write | guidance did the work |
| **wander** | `ls` / `find` / `grep -r` across the tree with no named target, repeated | native search, hoping to stumble |
| **guess-write** | `write_to_file` first, sources cited afterwards | fabrication with a citation bolted on |
| **verify** | re-reading its own artefact, `cat -A`, `wc -l` after writing | discipline, not evidence of guidance |

**The decisive question is ordering: did the `locate` step happen before the `guess-write` step?** A trace of `list_dir → read <entry doc> → read <context> → write` is guidance. A trace of `find … | grep … → write → read <doc> → quote it` is guessing that found the answer, and it is a `fail` however good the product looks.

**Report the trace, not just the verdict**: `action 1 list_dir m/ (orient) → action 2 read 01-supervisor.md (locate, before write) → action 3 write give.txt → action 4 cat -A (verify)`. No trace in the reading = the criterion was never evaluated.
**Write the expectation first, then the criterion.** Each item reads: `expected: <path>:<line> says <rule>` → `action: <what the agent must do>` → `fail shape: <which of the three>` . If an item has no `expected:` line, it is measuring taste, not guidance — delete it.

**A pass must be *reproducible by the document*.** Ask: if this agent were dropped into another project with the same docs and a different convention, would it still pass? If the answer is no, the case measured luck.
