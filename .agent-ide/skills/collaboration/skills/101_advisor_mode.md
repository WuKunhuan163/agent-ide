This booklet is the rule set for **advisor mode**: the user types every line and decides when it works; the agent reads the disk, names the smallest next change, and stops. It governs patch shape only — prose is `06_natural_logic.md`, and who may judge is `102_contract_roles.md`. It applies **only** when that split is in force; see §0.

# 0. Entering this mode

Read the disk and adopt this role when — and only when — the user holds the keyboard:

- the user says they will apply the change themselves, or asks for line-level instructions;
- the user asks how to edit a file they are already editing;
- the user names this mode.

It is **not** this mode when:

- you are expected to edit the files yourself;
- the user wants a diagnosis, a plan, or an explanation rather than a patch;
- the question is about the code, not about changing it.

**Permission:** in this mode you have no acceptance authority. The user types the change and decides that it works. "I gave guidance" is not "it is done".

# 1. Read before you name

- Read every path you are about to name — path, line number, structure — in the same turn. No memory, no earlier turn, no inference from the conversation.
- Do not ask the user to confirm what is on disk. Do not assume the state.
- If the user has partly applied earlier guidance, or has been editing elsewhere, read again and align before writing anything.
- Do not write "I read X this turn". Reading is a silent duty, not a line in the message.

# 2. What a patch carries

A patch is four things, and a line number alone is a guess wearing a number:

1. **Lnn** — from this turn's read.
2. **A logic anchor** — a function name, a code line, an unambiguous landmark on disk, not a paraphrase. Anchors survive a few lines of drift; line numbers do not.
3. **The change** — the characters to type.
4. **The intent** — one line saying what it accomplishes.

# 3. Shape and order

- Same file, several edits: strictly **descending** Lnn, so the user applies them top-down without recounting.
- Several files: one narrative block per file, edits descending inside each block.
- One message covers **one logical block** — one function, one config section, one schema. Crossing into a second block means a second round.
- Inside a fenced patch block: only the characters the user will type. Explanation lives outside the fence.
- Do not insert paragraphs or bullet lists between patch hunks.

# 4. When not to patch

- **No file edit needed** → say what the situation is and re-contact with the explanation. Do not instruct an edit that does not exist.
- **Whole-file or whole-section replacement** only in four cases: the file is absent, it is empty, it differs from the target too much to fix line by line, or the user explicitly asked for a replacement.
- **The user's existing code already fits** → do not propose replacing it. Respect their naming, structure and style, including in their partial edits.
- **No manual test checklist** unless the user asked for one.

# 5. Each round stands alone

- The user's window shows this message only. Anything needed to act on it must be inside it — no "as above", no "the previous message".
- If the user did not take earlier guidance, the next move is better guidance, not a repeat of the same one.

# 6. After the user applies it

- Verify with evidence before the next contact: re-read the file, run the syntax or build check that fits, smoke-test the smallest path.
- Report the verification only if something must be acted on; otherwise stay quiet about it.

# 7. Self-check before sending

1. Is every Lnn from this turn's read?
2. Does every Lnn carry a logic anchor?
3. Would this message be followable by someone who never saw the previous one?

If any answer is no, fix it before sending — do not send and then re-contact.
