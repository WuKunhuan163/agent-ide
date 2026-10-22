This booklet is the rule set for **structural** duplication: the same fact living in several places, a shared module that knows one deployment, a file with no stable boundary. It does not cover prose (see `06_natural_logic.md`) or patch shape. It applies while advising — the agent names the risk and the canonical move; the user applies the change unless a turn explicitly authorises otherwise.

**One line:** high entropy means a maintainer must reconcile several truths; de-entropy means one canonical layer per concern, splits at stable boundaries, and asserts or regeneration so dependents stay tied to the canonical source.

# 1. Signals worth raising

- The same constant, rule or copy appears in two or more places with no canonical pointer.
- A shared module, symbol or class name embeds a deployment-specific id — one product, one tenant, one screen, one feature.
- A monolith grows without a single reviewable unit or a stable boundary.
- A generated artifact was edited while its source stayed unchanged.
- A plan proposes audit plus massive rewrite in one turn, or refactoring outside the numbered scope.

Report as **risk plus canonical move**, not as a drive-by rewrite.

# 2. One canonical layer per concern

| Concern | Canonical source | Everyone else |
|---|---|---|
| Content and copy | versioned files, CMS, DB | services, templates, renderers |
| Rules and workflow | one graph or rules module | executors, handlers, workers |
| Live user state | database or session store | application code |
| Assets | storage tree plus manifest | build, URL builder, runtime |

- Conflict: fix the canonical layer first, then regenerate or update dependents.
- Variants: parameters (`variant`, `mode`, `locale`, `tenant`), never a copied path.
- If two consumers disagree, the vocabulary is the bug: one event or state name, or a documented alias map.

# 3. Naming

- No instance-specific identifiers in shared code; stable semantic names there, one-off layout or screen names only in scoped modules.
- Short names in shared code; verbose names stay scoped.
- Migrating an implementation: delegate or wrap the old one. Parallel duplicate logic is a new source of truth.

# 4. State and workflow

- One graph defines states, allowed events and transitions.
- Current state is persisted in one place; transitions go through one executor — not ad-hoc patches from several entry points.
- Legacy entry points delegate to that executor during migration.
- Every consumer — UI, worker, CLI, test — uses the same vocabulary or the alias map.

# 5. Generated versus hand-edited

- Source chunks are edited by hand; bundles and aggregates are rebuilt by script. The flow is source → validate → generate → runtime. Editing the output alone is the classic drift.
- Generated artifacts must be reproducible; a hand-edit that does not reach the source is a defect.
- Structured trees, packs and seed inputs get one manifest or schema, then an **assert** that fails loudly: files exist, variants are equivalent, no orphan or typo names.

# 6. Audit, then execute

1. Read-only audit, written down: classify each finding as **blocker**, **medium**, or **dead**.
2. Numbered plan; confirm once if the scope is genuinely ambiguous.
3. One numbered step per turn, unless the user asks for a batch.
4. Keep the audit turn and the big rewrite in separate turns when practical.
5. Do not re-ask a decision that is already recorded; execute it.
6. If an edit makes a unit unreviewable, finish the split in the same turn — do not leave a half-migrated boundary for later.

# 7. Closing a step

- Assert or validation for the touched canonical data exits zero.
- Codegen check or diff shows no unexpected drift.
- No new instance-specific name in a shared module.
- At least one regression guard for a removal or a split: a test, a schema field, an invariant marker.
- Boundary README updated if folders or canonical paths moved.

# 8. Size is not the criterion

Low entropy does not mean short files. A cohesive subsystem may span thousands of lines if it is one concern, one boundary, one canonical module, and its diffs stay reviewable. Split when concerns tangle, when a fact appears twice, or when changes stop being reviewable — never because a counter crossed a number.

# 9. Boundary README

At each new or split boundary, a short README answering: what belongs here, what is canonical versus generated, which file to edit first, the rebuild command, and the naming convention. Operational, not historical.

# 10. Anti-patterns

| High entropy | Low-entropy direction |
|---|---|
| Logic copied N times | Extract and parameterise |
| Generated bundle edited | Fix canonical, regenerate |
| Unreviewable monolith with mixed concerns | Split at a stable boundary |
| One consumer patched, canonical untouched | Fix the source, then all consumers |
| Transition strings scattered | One executor, one vocabulary |
| Instance id in a shared interface | Parameterise or narrow the scope |
| Audit and rewrite in one turn | Separate the audit; keep a baseline |
| "Helpful" refactor off-plan | Stay inside the numbered step |

# 11. HTTP and browser bindings

Only the parts that differ from the sections above:

- **One transition endpoint** with a small payload beats many ad-hoc endpoints; legacy routes delegate to it during migration.
- **One browser helper** performs transitions. Scattered `fetch` calls duplicate event strings and drift.
- Templates, JS and CSS take timings, flags and labels from bootstrap config, not from literals repeated per file; template expressions stay out of script blocks.
- Shared UI classes are semantic; screen-scoped classes stay thin and local.
- When template, CSS and JS disagree, fix the canonical row first, then the files.

# 12. Non-goals

Language-agnostic lint rules, framework choices, deployment topology, and any particular code generator. Also out of scope: prose quality (`06_natural_logic.md`) and patch shape (`101_advisor_mode.md`).
