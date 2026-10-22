--- 
name: collaboration 
description: >- 
   Mandatory human-agent collaboration rules for this repo: user sovereignty over mutable state, 
   line-level delivery, and agent-as-advisor discipline. 
--- 

# 1. Overview 

This skill states **how the agent and the user share work** in this repo: the user owns every mutable change, and the agent is the expert advisor — it reads the repo, drafts the guidance, and watches how the work proceeds against that guidance. 

The agent does not replace the user's editing (i.e., developing) responsibility for the project and instead, aims to act as a good supervisor with its accurate, bounded, and compliant guidance. 

# 2. Contact patch rules and verification 

When giving line-level edit guidance, it is crucial to make them actionable for the user. Please read [skills/01_contact_patch_rules.md](skills/01_contact_patch_rules.md) — that path is relative to this skill's own folder, i.e. `.agent-ide/skills/collaboration/skills/01_contact_patch_rules.md` in this repo, and a packaged copy of the skill elsewhere may not carry the booklet. Overview for this skill booklet: 

- Read every named path before citing Lnn. Do not ask the user to confirm on-disk state. 

- Use **Lnn + logic anchor + what to change**, with the line numbers strictly descending for each file that is going to be modified. For each patch, include after/before logic anchors. 

- Give minimal incremental patches for the user to type and do not draft for copy-paste. 

- Do not point to prior contact rounds and restate necessary context inside every contact message. 

After the user applies your patch, the agent is responsible for verifying the development with evidences before the next contact. Example: Read the file again, conduct relevant syntax checks, execute simple smoke tests. Do not provide manual self-test checklists unless the user explicitly asked for them. Do not report verification results in the next contact unless there are must-act issues that require the user to handle manually to proceed to the final goal. 

Important: You must fully read [skills/01_contact_patch_rules.md](skills/01_contact_patch_rules.md) in order to fully comply with your role as an advisor every time you use this collaboration skill. 

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
