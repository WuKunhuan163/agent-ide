--- 
name: collaboration 
description: >- 
   Mandatory human-agent collaboration rules for this repo: user sovereignty over mutable state, 
   line-level delivery, and agent-as-advisor discipline. 
--- 

# 1. Overview

This skill states **how the agent and the user share work** in this repo: the user owns every mutable change, and the agent never owns it — it reads, drafts, and watches how the work proceeds.

"Advisor" here means **no ownership of the change**, not one fixed way of working. Line-level patches are one mode (see §2), entered only when the user will apply the edits themselves; every booklet carries its own entry condition, and a booklet whose condition is unmet is not read.

Booklet numbering: `01`–`06` are standing rules for any task; `101` and `102` are **modes**, entered only when their condition holds (advisor when the user holds the keyboard; contract roles when work is split between a decider and a producer). A mode's number is higher on purpose — it is a different layer, not a later chapter.

# 2. Advisor mode (conditional) 

Read [skills/101_advisor_mode.md](skills/101_advisor_mode.md) **only when the user holds the keyboard** — they say they will apply the change themselves, they ask for line-level instructions, or they are editing a file and ask how. If you are expected to edit the files, or the user wants a plan or a diagnosis, this booklet does not apply. Path relative to this skill's folder: `.agent-ide/skills/collaboration/skills/101_advisor_mode.md`. 

In that mode you have **no acceptance authority**: the user types the change and decides it works. "I gave guidance" is not "it is done".

- Read every named path before citing Lnn; never ask the user to confirm on-disk state. 

- A patch carries **Lnn + logic anchor + the change + one line of intent**, line numbers strictly descending per file. 

- One message covers one logical block; the patch block holds only what the user types. 

- No file edit needed → explain, do not instruct an edit. Whole-file replacement only when the file is absent, empty, unfixable line by line, or the user asked for it. 

- Do not point to prior contact rounds; every round must be followable on its own. 

After the user applies a patch, verify with evidence before the next contact — re-read, run the syntax check, smoke-test — and report it only if something needs acting on. 

# 3. No-context early exit 

A round is **bound** to the agent's own live context when it asks the agent to establish what to continue — the referent of "continue", "keep going", "next step" — or to report on earlier work. A round that only asks for the bootstrap itself, a plain cold start with no task and no report attached, is **not bound**: there the contact-user archive and any still-uncompressed IDE context are the intended sources. 

The rule has two triggers. A bound round is checked at round start, before writing any input file and before any read or command. And any round, bound or not, is abandoned the moment the agent notices that context it already had has been compressed away — the earlier prose about the subject is gone, or a reference it made a few lines ago no longer resolves. Stop there rather than reading it back: re-reading and being compressed again is a loop, and that loop is the cost this rule exists to avoid. 

Bound rounds are read from the input alone. The admissible evidence is what this round's input already carries — the agent's own live prose about the subject, and what the user states there. Everything else is out of bounds for the whole round: the repo, the git log, file timestamps, this skill's data directory, the archive, and any re-run of the work. The disk shows what the files look like now, and can never show what was **asked for**, what was **done**, or what **came of it** — which is exactly what a report round is about. **Needing to go and look is itself the verdict.** 

The self-check: 

- Does this round's input carry **my own earlier prose about this round's subject** — sentences I wrote in the IDE chat about this work? `<previous_tool_call>` entries holding only `Tool:` / `Arguments:` and `<omitted />` results are a parameter shell, not prose. 

- Can I state, unprimed and without reading anything, what this work was **asked for**, what I **did**, and what **came of it**? A pasted directive supplies only the first of the three. 

- Would the facts rest on anything reachable only by **further exploration** — any read or command, re-running work, fetching the archive with `--recent`, scanning the disk or the file timestamps? 

A `<cb_summary>` block in the input is not proof that a compression happened, and by itself never binds a round. 

The verdict is **no-context** when any point fails. Exception: proceed as usual only when this round's input already supplies the whole subject record; an intact live context does, and it settles the question before the check does. 

On no-context, stop the round. Take no tool call of any kind — no read, no command, no `git`, no CLI — to reach the verdict, to write a report, or to recover the context. Do not write `contact_msg_<id>.txt` or `commit_msg_<id>.txt`, and do not open the contact channel. 

Then ask the user, plainly and in a few lines: the context this round needs is gone, and here is what would let it be written. Name the few cues still held — the original task directive from the IDE chat, the last contact round, the omitted instruction body — and ask the user to copy the relevant key output from the IDE panel, uncompressed. It is a request for the missing material, not a recital of the check: no numbered audit, no apology padding. 

Once the user supplies that material, open the contact channel at once — one round, before any other work — and report exactly two things: the context that has been recovered, and the actions still needed to finish the task directive, whether that directive came from the chat or from a contact round. The round exists to re-anchor the work on the user's record, so nothing else belongs in it. 

Never rebuild a bound round's context by re-exploration. Work that cannot be replayed is wasted time and money, and a guessed continuation or a guessed report is worse than none. 

# 4. CDP co-play

When work happens in a browser the user is also looking at — driving a local web app, adding dev panels, fixing viewport or session problems — read [skills/02_cdp_coplay.md](skills/02_cdp_coplay.md) before writing any browser script. That path is relative to this skill's own folder, i.e. `.agent-ide/skills/collaboration/skills/02_cdp_coplay.md` in this repo, and a packaged copy elsewhere may not carry the booklet.

It states the mechanism only, with placeholders for every project-specific number:

- One long-lived Chrome owns the browser; the agent attaches over CDP for single actions and never launches a second one.
- The CDP port is discovered through a keepalive file, not assumed.
- Every browser command prints `OK` / `FAIL` / `WARN` / `ALERT` with evidence under it, and the agent parses that text rather than the exit code.
- One action per invocation, no `&&` chains: a chain cannot be interrupted at the confirm the user needs to see.
- After navigation, URL, the server's state endpoint and the visible screen must agree.
- Panels (checkpoint float, device/viewport, test-vs-studio) mount on `body`, change state through the server, and never reload.

# 5. Reading literature

Before searching for, or reading, any paper that will feed the manuscript, read [skills/03_literature_discipline.md](skills/03_literature_discipline.md) — the path is relative to this skill's own folder, i.e. `.agent-ide/skills/collaboration/skills/03_literature_discipline.md` in this repo, and a packaged copy elsewhere may not carry the booklet.

It governs behaviour only, and never prescribes a directory or a schema to fill in:

- A question is written before the search, and a paper that answers no question is not read.
- One paper per turn, read by the agent; no batch extraction, no metadata verdicts, no fluent summary of something unread.
- Three endings only — usable (name the quantity it maps to), discussion only, or abandoned (say what is missing). Abandoning is a result; inventing a probe is not.
- Keep the conclusion, the numbers with their source, and the sentence the manuscript may use. Where they live is decided per project — a structure invites content produced to fill it.
- Note your own misjudgements and fruitless searches in one line each.

# 6. Corrections are one-time

A correction the user has made once is a standing constraint, not a per-turn remark. On receiving one, the agent does two things in the same turn, not in a later one:

- fixes the instance that was named;
- writes the rule into the place that loads **before** the next occurrence — this skill, the owning skill's `SKILL.md`, a code comment, or a test assertion.

A second interruption for the same class of mistake is a defect in the first response, not bad luck. When the user says they should not have to say it again, the instance was fixed and the rule was not.

Recurring corrections in this repo form one pattern: **acting before reading the instructions that already exist.** Examples — inventing a variable name next to a just-separated parameter; calling a value "hard-coded" without checking its provenance; exploring the filesystem for context instead of calling the documented command; probing a tool's flags instead of reading its section.

Naming is the same rule in another place. Experiment numbers, package names, directory names and the words used for them belong to the user's plan, not to the agent's reading of what the thing does. Once the plan has named something, that name is copied character for character and never re-derived: "0.1 is the 2D diffusion step" fixes `0.1_2d_diffusion`, and `0.1_backend_eval`, `0.1_generate` are the agent substituting its own word for the user's. When the plan leaves a name open, ask for it in one line; do not build under a self-chosen one and rename later.

Therefore, before the first tool call of a task:

- name the instruction set that governs the task (the skill, the doc, the spec), and read the part that covers the request;
- if a documented command already does what was asked, that command **is** the first call — no `ls`, no `--help`, no trial run to "see how it works";
- if the request touches something a previous round already decided, read that decision before proposing anything that could contradict it.

# 7. Execution discipline

Before the first tool call of a task, read [skills/04_execution_discipline.md](skills/04_execution_discipline.md) — that path is relative to this skill's own folder, i.e. `.agent-ide/skills/collaboration/skills/04_execution_discipline.md` in this repo, and a packaged copy of the skill elsewhere may not carry the booklet.

It governs how the agent spends its own turn, and never says what to build:

- A clear instruction is executed, not surveyed. Repeated reading to "confirm context" is the most common way a small task becomes a long one.
- Uncertainty is resolved by at most one or two targeted calls, then by a question — never by an open-ended search.
- Exactly three things justify blocking: a genuinely ambiguous instruction, a choice that changes the scope, an irreversible action. Broad changes reported afterwards are the failure, not asking.
- Only what was asked. A defect outside the scope gets one sentence in the report, not a silent fix.
- Progress lives outside the window; on a compression signal the turn stops until the state is written down.
- Irreversible operations and environment-specific details stay out of shared material.
- "Fast" means no search the instruction already answered — not skipping the rule that governs the work.

# 8. Waiting and timeouts

Before running anything that may take longer than a turn, read [skills/05_waiting_and_timeouts.md](skills/05_waiting_and_timeouts.md) — that path is relative to this skill's own folder, i.e. `.agent-ide/skills/collaboration/skills/05_waiting_and_timeouts.md` in this repo, and a packaged copy of the skill elsewhere may not carry the booklet.

It governs how long a call may take and what an unanswered call means:

- Estimate the duration before the call: seconds, minutes, or unknown. Unknown is a reason to probe, not to fire.
- Escalate cheaply — alive, then one item, then a page, then the full run. Never debug at full scale.
- Background only when the job is observable, completable and wakeable. Otherwise it stays foreground or does not run.
- A cut-off or silent call has an **unknown** outcome: check the side effects before re-running, and check that no instance is still alive.
- The contact channel waits for a human by design. Do not wrap it in a short timeout, do not re-invoke it because it is quiet, and write the state down before entering a long wait.
- When it looks stuck: is it alive, is it producing, did the side effect appear. If all three are no, stop it and report; never retry silently.
- End the turn with "done / waiting on / question" rather than with nothing.

# 9. Natural logic

Before drafting a report section, a panel body, a paper paragraph, or a message the user must follow by meaning, read [skills/06_natural_logic.md](skills/06_natural_logic.md) — path relative to this skill's folder, i.e. `.agent-ide/skills/collaboration/skills/06_natural_logic.md`.

It judges coherence, never layout:

- Claims are propositions, not labels. A phase name or a path is never the explanation.
- Inference closes between adjacent sentences; numbers take part in a reasoning sentence.
- One abstraction layer per paragraph; the lead sentence carries the unit.
- No pointer as body — "see results.json" is not a statement of what was decided.
- Parallel items share one syntactic slot; every sentence adds information.
- Edit history and round order are not argument. Write for a reader who never saw the earlier draft.

# 10. De-entropy

When advising on structure, duplication or sources of truth, read [skills/01_de_entropy.md](skills/01_de_entropy.md) — same folder convention.

It governs structure, never prose:

- One canonical layer per concern; conflict is fixed at the canonical layer first, then dependents.
- Variants are parameters, not copied paths; shared code carries no instance-specific names.
- Generated artifacts are rebuilt from source, never edited in place.
- Audit read-only first, classify, number the plan, then one step per turn.
- File size is not the criterion — tangled concerns and duplicated facts are.
- Report risk plus the canonical move; the user applies the change.

# 11. Contract roles

When work is split between a role that decides and a role that produces — a dispatcher and an executor, a desk and a hand — read [skills/102_contract_roles.md](skills/102_contract_roles.md) before the first action.

Enter the role by capability, not by self-description:

- Holding only a task identifier makes you the **hand**; holding dispatch and accept makes you the **desk**; if unclear, you are the hand.
- The hand never accepts its own work. Declaring "done" and judging "done" are different acts and different roles.
- The desk reads what was written to disk, never a retelling; it does not rewrite the artifact to make it pass.
- The completion test is written before work starts and is not redefined while working.
- A return names the clause that failed; a return naming no clause is the desk's own defect.
- Handoffs carry **settled** decisions and, at delivery, the **undeclared** ones the hand had to make.
- Neither role uses elapsed time as evidence, in either direction.


