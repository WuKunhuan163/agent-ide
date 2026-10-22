This booklet is the rule set for whether a paragraph coheres. It governs **meaning, not patch shape and not structure**: how a file or a tree is laid out belongs elsewhere. It applies to anything a reader or a decision-maker has to follow without external scaffolding — a report section, a panel, a paper body, and the prose of a message written for the user to act on.

**One line:** claims are propositions, not labels; inference closes between adjacent sentences; the lead sentence carries the load; one abstraction layer per paragraph; parallel items share a slot; every sentence adds information.

# 1. Label versus proposition

- Names, phase titles and file paths **denote objects**; they are never the explanation. A slug, hash or account name must not stand where a claim belongs.
- "What is at stake" needs conditions and a decidable outcome: who, under what premise, satisfies or violates what.
- A hook line — subtitle, opening, caption — must not be only a status token (`passed`, bare `p=…`). Numbers may appear **inside** a claim or a contrast.
- Self-check: ask the lead sentence "so what? what is still undecided?" If there is no answer, it is a label.

# 2. Inference closes

- A judgment must find its support in the same or the adjacent paragraph. No conclusions from nowhere.
- Match wording to evidential strength: settled results are not described as ongoing work, and the reverse.
- Mark inference explicitly — therefore, hence, shows, indicates — or by temporal order: observe first, infer second.
- Numbers and command outcomes take part in a reasoning sentence; they are not a ledger line on their own.
- Self-check: delete the conclusion paragraph — what remains should not read as complete. Keep only the conclusion — the text should not cohere.

# 3. One abstraction layer per paragraph

- Do not mix a whole-task verdict with a single command or a single number in one paragraph. Higher-level prose first; operations and numbers after.
- A paragraph break permits a change of depth; inside a paragraph, stay at one level.
- If a paragraph contains paths or numbers, its first sentence must already justify that granularity.

# 4. Local self-containment

- A paragraph, or one semantic block including one message paragraph, must be intelligible without "see above" or "below we will".
- **No pointer as body**: a reader-facing block cannot consist only of `see results.json`, a workspace path, or `verdict: pending`. Pointers may follow an interpretive sentence; they never replace it.
- Self-check: strip the pointers and file names; the block should still state what is decided or what the reader should understand.

# 5. The lead sentence carries the unit

- The first sentence of a paragraph or subsection states what the unit answers or decides. Later sentences may elaborate, qualify, exemplify or rebut — never paraphrase the lead.
- Label lines with no reasoning ("question:", "boundary:", a lone "conclusion:") are empty scaffolding, not logic.
- Self-check: read only the first sentence of each paragraph; they should sketch the whole argument. Replace a label line with nothing; if nothing worth saying is lost, delete it.

# 6. Parallel items share a slot

- Siblings under one parent use one word class and one syntactic slot — all noun phrases, all verb–object, all "whether …" questions — so they compare like with like.
- Detail differences start from the second sentence, not in the labels.
- Self-check: read only the titles of parallel items; they should look like columns of one list.

# 7. Process time versus content time

- Edit history, ticket state, round order and "as mentioned above" are not argument. They belong in a changelog, not in an argument.
- A content timeline — prior work, experimental order, causal history of the subject — is allowed when it carries evidence.
- Self-check: delete the sentence. Losing only meta about drafting means the cut was right; losing evidence means it was content.

# 8. Every sentence adds information

- Delete or merge anything that adds no information against its neighbours: synonym restatement, slogans, pure status words, rhetorical questions, emotional closings, "remember this" hooks.
- Repetition is allowed only when the later sentence restates a judgment **with new evidence**.
- A short summary must not be a path catalogue: give the gist in prose, not a list of files.

# 9. Reader-facing versus operator-facing

- For a block written as a section of a report for third parties, prefer impersonal mechanism statements over second-person instructions or CLI-tutorial voice. Describing the execution path is right; telling the reader to run something is not.
- Uncertainty and limitations are stated as causal prose, not as project-management enums (`open`, `pending`) used as exposition.
- Headings, tables and lists structure a report; inside an argument paragraph, advance by sentences and causal order. Lists enumerate, they do not reason.
- Write as if the reader has never seen an earlier draft: do not carry "the previous version said …" into the body.

# 10. Non-goals

Tree UI limits, panel byte caps, experiment layout, message API details, how much signposting a particular document should carry, and IMRaD or thesis-writing tutorials. Those are the owner's choices, not laws of prose.
