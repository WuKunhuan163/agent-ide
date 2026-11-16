verdict: pass           # pass | fail | marginal
by: L<line number>             # the evidence line in the export；several lines as L1,L2
unit: "1"
queue: TEMP_prelim-report
---

# unit #1 verdict

| criterion | result | evidence（L line number／path:line） |
|---|---|---|

## responsibility for a fail（fail/marginal required）
- [ ] **cutting problem**：unit too large/too small/dependency missing → change `units/`
- [ ] **dispatch problem**：purpose or acceptance line unjudgeable → change dispatch block
- [ ] **execution problem**：return missing readings、skipped steps、edited others' files → record `cutting observation:` and consider redispatch
