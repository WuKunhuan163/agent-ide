---
name: task-queue
description: >-
  One durable FIFO per id. Keeps "what is next" outside the conversation and
  writes the head's verdict back to a task_tree node. Use for contract stacks,
  hand-off work items, or any list whose order must survive a crash.
---

# task-queue

一个 id 一条 FIFO。顺序只存在 `data/<id>/queue.json` 里，条目是 `data/<id>/tasks/<key>.yaml`；因此上下文压缩、进程崩溃、换人接手都不会让“下一步做什么”丢失，且索引随时能与磁盘对账。

## 何时用

- 有一串要按顺序做完的事，而顺序不该只活在对话里
- 做完一条要留下 `pass / fail / marginal` 的结论，并让它出现在 `task_tree` 的对应节点上
- 多人或多 agent 交接：下一位只需 `next`，不需要读上一段对话

## 命令

```bash
task-queue push note.md --id <queue>          # 入队尾；--front 插队
task-queue next --id <queue> [--body]         # 看队头（--body 打全文）
task-queue list --id <queue>                  # 一行一条，带状态与序号
task-queue pop --id <queue>                   # 取走队头，归档为 popped
task-queue resolve pass --id <queue> [--tree-id <tree>]
task-queue check --id <queue> [--fix]         # 索引 vs 磁盘对账
```

`--id` 可放在子命令前后，缺省为 `default`。

## 条目

`push` 接受任意文本文件：`.md` 的全文成为 `body`，标题取首个标题行；`.yaml` 读取 `title`/`status`/`body`。源文件在入队后移走（队列即归属），`<key>` 是 `时间戳_标题`。

```yaml
id: 20261022_200145_write_tests
title: Write the queue tests
status: pending
created: 2026-10-22T20:01:45+08:00
body: |
  Cover push/next/resolve/check…
```

`resolve` 取队头，写 `status`（passed/failed/marginal）与 `verdict`，把条目复制到 `data/<id>/_archived/`，再从索引移除。

## 与 task_tree 的分工

- 队列管**顺序**：下一个是谁
- 树管**结构**：这条挂在哪个假设下、整棵树长什么样

`resolve --tree-id <tree>` 会调用 `task_tree --id <tree> resolve <key> --verdict <v>`。树没安装时只提示一行，不影响队列推进。

## 数据与恢复

| 路径 | 内容 |
|---|---|
| `data/<id>/queue.json` | 顺序，唯一权威 |
| `data/<id>/tasks/<key>.yaml` | 条目 |
| `data/<id>/_archived/` | 已 pop / 已 resolve 的历史 |

索引与磁盘不一致时（手工拷贝、崩溃、`data/` 被 replicas 恢复），`check` 列出两类问题，`--fix` 会删掉指向缺失文件的条目、并按 key 追加未登记的文件。

`data/` 不进 git。要换机器，`queue.json` 与 `tasks/` 必须一起走：前者是顺序，后者是内容，缺一个就只能重建队列。

## 安装

```bash
agent-ide install task-queue        # 写 .agent-tools/task-queue
```

依赖 `pyyaml`，由 `install` 交给 pip 装进技能的 runtime。

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 正常 |
| 2 | 用法或数据错误（文件缺失、YAML 非法、索引损坏） |
| 3 | 队列为空却要求取队头 |
