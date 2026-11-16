# Prose

Rules for the text that goes into blocks. They are formatting rules, not style
preferences: each one prevents an inconsistency that is expensive to find later.

## Technical terms are set in typewriter

Library, framework, method and model names, file names and CLI flags are marked
as code — `\texttt{...}` in TeX, the matching inline-code form in Markdown.
Consistency matters more than the choice: half the document marking a name and
the other half not reads as though two people wrote it.

## Numbers carry their own provenance

A number in the prose must be traceable to where it came from — a table, a
figure, a run. If the same quantity appears twice, both occurrences use the same
digits and the same unit; a rounded restatement in the abstract is still the same
number and must not drift.

Provenance is not enough on its own: **a number also carries four conditions** —
object, resolution, view count, device. One that cannot show all four in the same
line is removed rather than footnoted. "Runs faster" is not a claim; "2.1 s per
frame at 512² with 64 views on one A100" is.

## Refer to blocks, not to positions

Write `Figure~\ref{fig:...}` / `Section~\ref{sec:...}`; never "the figure above"
or "as shown earlier". Positions change when a section moves.

## One claim per paragraph, evidence adjacent

A claim and the evidence for it belong in the same paragraph. A citation at the
end of a paragraph that makes three claims is ambiguous about which one it
supports, and the reader cannot tell whether the others are yours.

## Do not restate the caption in the body

The figure caption says what the figure shows; the body says what it means for
the argument. Duplication makes the two drift the first time either is edited.

## One sentence per line, and the line stays a sentence

A sentence occupies one line; sentences are separated by a single newline and
paragraphs by a blank line. Never wrap a clause onto the next line and never put
two sentences on one line: the diff you read later is a diff of sentences, and a
wrapped paragraph hides which sentence changed.

`\cite{...}` opens the line and is followed by the work it names — `\cite{guédon2024} SuGaR binds Gaussians to mesh faces.` — not parked at the end. A citation at
the end of a long sentence supports whichever clause the reader guesses.

A sentence does one thing. Past roughly twenty-five words, split it: no semicolon
carrying two assertions, no dash standing in for a full stop. A paragraph holds at
most five sentences, and a blank line marks a change of subject rather than a
change of mood.

## A term is measured, not coined

Before a new term enters the text, run it through the corpus: translate the
candidate into the standard English term and count how many sample papers use it.
Zero means it is ours, not the field's — rewrite, do not define it into existence.
Four signals that a term was invented: it does not translate into one standard
English phrase; it is a metaphor (a floor, a ledger, a dial); it names a property
of our method rather than something a reader could observe; or it only exists in
this document. Two signals are enough to reject it.

The audit is a file, not a memory: one row per candidate — term, English
equivalent, papers hit, disposition — and every zero-hit row must end in "rewritten"
with the term's count in the body at zero. A term with a standard translation, a
term the authors define once and use only for their own mechanism, and pure
notation (`F`, `k`, `N = F·k²`) are not inventions.

## A rule states the derivation, never the answer

A document that says "the answer must contain these six things" has handed the
reader an answer key, and the reader will fill it in without understanding
anything. Write the derivation instead: from the purpose, through what each
reader needs, to the property and the failure it prevents. Keep the checkable part
— reader, failure shape, pointer form — and leave the enumeration out.

Counting claims are reconciled before they are stated: the same number often
lives in three places (the ledger, the index, the bibliography), and when they
disagree the job is to report the disagreement, not to pick the convenient one.

## A title names the object and the action

A section title says what was done to what — "Splitting the count from the
appearance" — not which file it lives in and not which round produced it. A title
that names a file is a title that will be wrong the first time the file moves.

## Write from the conclusion backwards, and read it yourself after a real edit

Draft the section by fixing its final sentence first, then the evidence that earns
it, then the opening that sets it up; writing forwards produces an opening that
promises what the evidence will not pay. After any substantive insertion or
deletion — not a typo, a paragraph — read the passage whole: an edit that removes a
premise leaves the sentences that consumed it grammatically fine and logically
empty, and only reading catches that.

## An emphasis sentence is not a reason

"I want to stress that the method is lightweight" states the wish; the reader needs
the number and the comparison that make it true. When a paragraph reads as
unconvincing despite being correct, the usual cause is not too little emphasis but
an assertion standing where evidence was owed.

## The body carries no methodology narration

`lifecycle`, `gate`, `phase`, `the order of work`, `we now move to` — words about how
the writing was organised are not part of the argument and read as scaffolding left
in the room. The same applies to conditions: an engineering constraint is written
constraint → decision → number ("a single run is capped, so the batch is split, and
each split costs 40 minutes"), never as a description of the platform we happen to
use.

## A lesson is written as a method, not as an incident

Four parts: the method in one judgement sentence with no proper nouns; why it holds,
in one sentence of mechanism; two actionable steps starting with verbs; and the
limit — where the method stops. An incident ("last time this went wrong because…")
is evidence for the ledger, not a rule for the document: it dates the rule and makes
it unreadable to whoever did not live through it.
