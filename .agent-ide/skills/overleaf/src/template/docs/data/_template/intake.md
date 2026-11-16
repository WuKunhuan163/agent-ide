# 接盘检查表（收到上司围栏后，逐项打勾才许切）

- [ ] **1 存原文**：追加一段 `## ROUND n · <日期 时间>` ＋ `> source：<key> 的回复（导出 :起–止）`，正文原样贴入——**不覆盖**（覆盖＝把上一轮委托留给下一轮）
- [ ] **2 读状态**：`loop_state.json` 的未完成叶子与 `history{kind:"prune"}`；`task-queue list --id TEMP_<id>`
- [ ] **3 对账**：围栏 §4 每条 vs 队列已有项 —— 重复的不入栈，缺口的新发现压栈顶
- [ ] **4 判口径**：每条项问“产物是读数还是判断”；判断的收回本层或上报
- [ ] **5 标依赖**：每条项写 `depends:#k`（无则空）；两项合格线读同一产物却没标依赖 = 拆解错误
- [ ] **6 切**：落 `units/#n-<slug>.md`（六行：purpose·which file·acceptance line·depends·预算·return）
- [ ] **7 入队**：`cp units/#n-*.md /tmp/ && task-queue push /tmp/#n-*.md --id TEMP_<id>`（原件留在 `units/`）；**队列＝未下发池，下发时 `pop` 出池**，完成凭据是 `returns/#n-verdict.md`
- [ ] **8 自查**：跑 `02-lead.md` §自查的三条命令，把输出贴在收口处

**任何一项没打勾就下发**：切出来的东西会在回收时暴露成“执行层不行”，而原因在接盘。
