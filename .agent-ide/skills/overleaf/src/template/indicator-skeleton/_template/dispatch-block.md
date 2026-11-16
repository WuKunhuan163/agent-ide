# Dispatch block template (the lead hands over 1–5 per round)

**Copy the block below for each item**, changing only what is in angle brackets. **No triple backticks inside a block**; **no prose outside the blocks**; after all blocks, **only the count**.

```PROMPT
id: prelim-report
root：<absolute path of the project root>
entry：<project root>/.agent-ide/skills/overleaf/src/template/docs/strategy-roleplay/03-executor.md
# unit #<n> <item name>
purpose：<which clause or which road this item serves; the `paves:` line goes here>
what to do：<one summary line, enough for the user to judge whether to copy this>
which file：<a writable path, not an entry point or a template>
acceptance line：<a recomputable number: exit=0 / non-finite 0 / ocr_hits≥3/4 …>
depends：#<k> (write "none" when none)
budget：<steps cap / elapsed cap / device count>
return：indicator/prelim-report/returns/#<n>.md (first line `# unit #<n>`)
```

**The last paragraph after all are posted (this paragraph only, nothing else)**:

> this round dispatches N items：#<a> <one-line purpose>; #<b> <one-line purpose>… (an item whose dependency is unresolved is written `excluded: #k because <dependency>`)

**Why the first three lines are fixed**: the executor must receive exactly what the lead received — **`id` (which round) + entry (which layer you are) + root (where the work happens)**. Without a root it guesses a tree; without an entry it does not know it owns only one item.

**Five self-checks**: ① the block count equals the N in the count line; ② each block's first two lines are `purpose` / `what to do`; ③ triple backticks inside a block = 0; ④ the first three lines are `id:` / `root：` / `entry：`; ⑤ **the opening line is `\`\`\`PROMPT`, not a bare `\`\`\``**.

**Counter-example (measured this round, `9200e4b3`)**: opening with a bare `\`\`\`` and putting `PROMPT` on the body's first line — **a search for `\`\`\`PROMPT` hits none of them**, and six fences become "code blocks with no label". **`PROMPT` is the fence's language label, not a line of the body.**
