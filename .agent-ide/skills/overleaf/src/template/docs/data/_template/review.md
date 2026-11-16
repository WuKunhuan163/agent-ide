# 回收检查表（用户要求“评估／回收”时，逐项打勾）

- [ ] **1 框轮次**：先定 `# rN` 与起止时间；判据只从回复正文取
- [ ] **2 逐块对**：交回件 `returns/#n.md` 是否存在、首行 `id:`＋`# unit #n`、`status` 合法
- [ ] **3 判执行**：按 `guide-repro-test.md` 四步（框轮次→取正文→取动作→最后开文件），每条 verdict 带 `L<line number>`
- [ ] **4 写 verdict**：`returns/#n-verdict.md`，首行 `verdict:` ＋ 恰好一个词（词表见 `returns/_verdict-template.md`，五选一，没有裸 `fail`、词后不接说明），次行 `by: L<line number>`，第三行 `leaf: <leaf id>`
- [ ] **5 出栈**：**队列是未下发池**——下发时已 `pop`；回收只写 `returns/#n-verdict.md`（`task-queue resolve` 只用于作废/取消，且只能队头）
- [ ] **6 改状态**：`loop_state.json` 的对应行；`## EXIT-READINGS` 需要时补
- [ ] **7 归因**：fail 时勾一条——cutting problem／dispatch problem／execution problem
- [ ] **8 回流**：`loop_state.json` 的 `history` 记一条 `{kind:"reweight", why:"cutting observation: …"}`，下次切分前先读最近三条
- [ ] **9 自查**：跑 `02-lead.md` §自查的三条命令，把输出贴在收口处

**顺序不能倒**：先判后改树（`loop_state.json`）；先出栈再改 loop_state.json；归因写在 verdict 里，不写在对话里。

## 行号从哪来（`by: L<n>` 不是凭记忆写的）

```bash
# 1) 用执行层回复里的一句原话做针
printf '%s\n' "<从它的回复里抄一整句>" > /tmp/needle.txt
agent-ide context --probe /tmp/needle.txt          # → key  hits  msgs  bytes
# 2) 导出该场，行号就是文件里的行号
agent-ide context --key <key> > /tmp/exec.md
grep -n "<那句话>" /tmp/exec.md                     # → line number
```

**verdict 里写 `by: /tmp/exec.md:L<n>`**（带导出路径，别人能重放）。**没有导出就没有行号——那就写 `unjudged`，不许估。**
