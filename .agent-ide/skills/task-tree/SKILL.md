---
name: task-tree
description: >-
  A hypothesis tree whose nodes carry a verdict. Structure in
  data/<tree>/tree.json; resolve records pass/fail/marginal, settles parents, and
  moves the focus to the next open leaf. Use when the work branches (alternatives,
  prerequisites) instead of forming a line.
---

# task-tree

一棵树就是一个文件：`data/<tree>/tree.json`。节点是假设、检查项或目标；叶子被 `resolve` 裁决，父节点由子节点聚合，`focus` 永远指向下一个该验证的叶子。

## 何时用

- 同一个问题有多条互斥路线（`one_of`：一条通过即父节点通过，一条失败就换下一条）
- 有前置依赖（`--requires`：依赖未通过时节点 `blocked`，通过后自动 `open`）
- 需要把“为什么走这条路、哪些已经排除”留给下一位 agent 或未来的自己

线性任务用 `task-queue`；树管的是分叉与证据。

## 命令

```bash
task-tree init --root <node> --title "<goal>"          # 建树（一个根节点）
task-tree add <node> --parent <node> --title "..." [--type hypothesis|check|goal] [--body-file FILE]
task-tree add <node> --parent <node> --requires a b     # 依赖未满足则 blocked
task-tree mode <node> all|one_of                       # 该节点如何聚合子节点
task-tree next [--body]                                # 现在做什么（焦点叶子），--body 带正文
task-tree body <node> --file FILE                      # 写入或替换节点正文
task-tree resolve <node> pass|fail|marginal --evidence "..." [--force]
task-tree focus [<node>]                               # 查看或手动改焦点
task-tree show                                         # 整棵树，* 标焦点
task-tree rm <node> --force                            # 删子树
task-tree check [--fix]                                # 悬空 parent/child/requires 对账
task-tree export [--out FILE]                           # 自包含 HTML，可折叠
```

`--id` 可放在子命令前后，缺省 `default`。

## 状态与推进

| 状态 | 含义 |
|---|---|
| `open` | 待验证（只有叶子会进入焦点） |
| `passed` / `failed` / `marginal` | 已裁决；`marginal` 表示部分成立，焦点留在该节点等它拆子节点 |
| `blocked` | `requires` 里还有未通过的节点 |

`resolve` 依次做四件事：

1. 写节点状态、`verdict`、`evidence`，追加 `history`
2. 向上聚合父节点（`all`：子全过才过，**有失败时父保持 open**——失败的是一条被排除的分支，不是目标；`one_of`：任一通过即通过，全失败才失败）
3. `pass` 时解锁依赖它的 `blocked` 节点
4. 把焦点移到 DFS 顺序里下一个 `open` 叶子；没有则报 `no open node left`

`marginal` 不推进：它提示的是“这条假设需要拆细”，下一步用 `add --parent <node>` 拆。

## 与 task-queue 的分工

- 队列管**顺序**：一条线，下一件是什么
- 树管**结构**：分叉、依赖、每条分支的证据

队列条目可以带 `node: <node-id>`，`task-queue resolve ... --tree-id <tree>` 会把同一个裁决写进这棵树；不带 `node` 时用队列自己的 key 当节点 id。

## 导出

`export` 写一个自包含 HTML（内联样式、原生折叠），不启动服务、不依赖网络，`<details>` 可逐层展开。默认落在 `data/<tree>/tree.html`。

## 数据与恢复

| 路径 | 内容 |
|---|---|
| `data/<tree>/tree.json` | 节点（含正文）、焦点、历史，唯一权威 |
| `data/<tree>/tree.html` | 最近一次导出 |

`tree.json` 是可读 JSON，可以直接看、可以直接 diff。节点正文存在 `body`，`show` 不打印，`next --body` 与导出的 HTML 才展开。`check` 找四类问题：非根的 `parent` 为空、`parent` 不存在、子节点未在父节点 `children` 里、`requires` 指向已删除节点；`--fix` 会丢掉这些悬空引用并把焦点移到合法位置。

`data/` 不进 git。

## 安装

```bash
agent-ide install task-tree
```

纯标准库，无第三方依赖。

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 正常 |
| 2 | 用法或数据错误（树不存在、节点不存在、重复 id、拒绝删根） |
