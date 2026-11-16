id: <identifier>
unit: "1"
level: <freeze | pave | take the number | scale>   # 一叶一级；放大的单元以最小规模那片为前置
title: <项名，与队列 title 的 `#n ` 前缀一致>
leaf: <loop_state.json 里的叶子 key>   # 没有这一行不许下发：它在树上无处落地，进度算不进去
weight: <本单元承担的执行量点，正整数；同一叶子拆成多单元时，各单元之和 = 该叶 weight>
ratio-target: <做到几成算 this unit done，默认 1>
status: <dispatched | resolved | void>
depends: []            # 例 ["3"]；空数组表示无依赖
budget: {steps: <上限>, wall_min: <上限>, cards: <张数>}
---

# unit #1 <item名>

- **purpose**：`paves:` 哪条分句／哪条路
- **which file**：可写的草稿或产物路径（不是入口、不是模板）
- **acceptance line（with a number）**：可重算的读数，e.g. `exit=0`、`non-finite=0`、`ocr_hits≥3/4 种子`
- **return**：`returns/#1.md`，首行 `id:` ＋ `# unit #1`，读数带命令与 `path:line`
- **must not**：读 `units/#m`（m≠1）、change `indicator/` 以外的管理文件
