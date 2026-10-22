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
