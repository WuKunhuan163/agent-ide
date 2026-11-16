verdict: pass           # 恰好一个词，后面不接说明：pass | fail(process) | fail(marginal) | fail(result) | blocked
by: L<line number>             # the evidence line in the export；several lines as L1,L2
leaf: <leaf id>           # and loop_state.json 的接线；缺这一行，判词只能靠文件名去猜属于哪片叶子
unit: "1"
queue: TEMP_<id>
---

# unit #1 verdict

| criterion | result | evidence（L line number／path:line） |
|---|---|---|

## responsibility for a fail（`fail(...)`／`marginal` required）
- [ ] **cutting problem**：unit too large/too small/dependency missing → change `units/`
- [ ] **dispatch problem**：purpose or acceptance line unjudgeable → change dispatch block
- [ ] **execution problem**：return missing readings、skipped steps、edited others' files → record `cutting observation:` and consider redispatch
