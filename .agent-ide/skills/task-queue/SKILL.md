---
name: task-queue
description: >-
  One durable FIFO per id. Keeps "what is next" outside the conversation and
  writes the head's verdict back to a task_tree node. Use for contract stacks,
  hand-off work items, or any list whose order must survive a crash.
---

# task-queue

一个 id 一条 FIFO。顺序只存在 `data/<id>/queue.json` 里，条目是 `data/<id>/tasks/<key>.yaml`。

## 何时用

- 有一串要按顺序做完的事，顺序不该只活在对话里
- 做完一条要留下 `pass / fail / marginal` 的结论，并写进 `task-tree` 的对应节点
- 交接：下一位只需 `next`，不必读上一段对话

## 命令

```bash
task-queue push note.md --id <queue>          # 入队尾；--front 插队
task-queue next --id <queue> [--body]         # 看队头（--body 打全文）
task-queue list --id <queue>                  # 一行一条，带状态与序号
task-queue pop --id <queue>                   # 取走队头，归档为 popped
task-queue resolve pass --id <queue> [--tree-id <tree>]
task-queue check --id <queue> [--fix]         # 索引 vs 磁盘对账
```

`--id` 可在子命令前后，缺省 `default`。

## 条目

`push` 接受任意文本文件：

- `.md`：全文进 `body`，标题取首个非空行并剥掉行首 `# `；没有标题行时取该行前 80 字
- `.yaml`：读 `title` / `status` / `body`

源文件入队后移走（队列即归属），`<key>` 为 `时间戳_标题`。

```yaml
id: <时间戳>_<slug>
title: Write the queue tests
status: pending
created: <ISO 8601>
body: |
  Cover push/next/resolve/check…
```

`resolve` 取队头，写 `status`（passed/failed/marginal）与 `verdict`，复制到 `data/<id>/_archived/`，再从索引移除。

## 与 task-tree 的分工

- 队列管顺序：下一个是谁
- 树管结构：这条挂在哪个假设下、整棵树长什么样

`resolve --tree-id <tree>` 实际调用 `task-tree --id <tree> resolve <key> <pass|fail|marginal> --evidence "…"`（裁决是位置参数，不存在 `--verdict`）。树不存在时队列只打一行提示、退出码不受影响；镜像过去时 `--evidence` 会整体覆盖节点原有 evidence。

## 数据与恢复

| 路径 | 内容 |
|---|---|
| `data/<id>/queue.json` | 顺序，唯一权威 |
| `data/<id>/tasks/<key>.yaml` | 条目 |
| `data/<id>/_archived/` | 已 pop / 已 resolve 的历史 |

`check` 找两类不一致：索引条目指向的文件不存在、磁盘上有未登记的文件。`--fix` 删悬空条目、按 key 追加未登记文件。换机器时 `queue.json` 与 `tasks/` 必须一起走。

`data/` 不进 git。

## 安装

```bash
agent-ide install task-queue        # 写 .agent-tools/task-queue
```

依赖 `pyyaml`，由 `install` 装进技能的 runtime。

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 正常 |
| 2 | 用法或数据错误（文件缺失、YAML 非法、索引损坏、索引有条目但文件缺失并提示 `check --fix`） |
| 3 | 队列为空却要求取队头 |
