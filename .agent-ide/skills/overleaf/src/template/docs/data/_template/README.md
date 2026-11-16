# `indicator/<identifier>/` 's标准骨架

新开一个 id 时，**整目录照抄本文件夹**，把 `<identifier>` 换掉，不要自由发挥。

```
indicator/<id>/
  README.md              ← 本目录说明＋掉语境自检（照 _template/README.md 的正文）
  supervisor-prompt.md   ← 收到围栏后立刻存原文（不改写、不摘要）
  loop_state.json          ← 有序树（叶子 weight/state/ratio/evidence）＋ history n
  units/#n-<slug>.md     ← 切好的执行单元（照 units/_template.md，六行齐）
  returns/#n.md          ← 执行层交回（照 returns/_template.md）
  returns/#n-verdict.md  ← 组长判定（照 returns/_verdict-template.md）
```

**队列不在目录里**：`task-queue --id TEMP_<id>`。**编号 `#n` 必须三处一致**：`units/#n-*.md`、队列 title 的 `# unit #n` 前缀、`returns/#n*.md`。

## 四张做事用的表（照抄，不要临场发明）

| 什么时候用 | 用哪张 |
|---|---|
| 收到上司围栏 | `intake.md`（八步，未打勾不许切） |
| 要下发 | `dispatch-block.md`（块内禁三反引号；块外只写报数） |
| 被问闭环口径 | `closure-answers.md`（四问四段＋两块清单＋四样状态） |
| 被要求评估/回收 | `review.md`（九步，顺序不能倒） |

**本目录五件（缺一件就算骨架不全）**：`README.md`／`loop_state.json`／`intake.md`／`dispatch-block.md`／`closure-answers.md`／`review.md`；另在上级目录：`units/_template.md`、`returns/_template.md`、`returns/_verdict-template.md`。

**自查**：`02-lead.md` §自查的三条命令，**三条输出都贴出来**才算结构做完。
