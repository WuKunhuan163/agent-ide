---
name: heartbeat
description: 待办没清时不许收工。用 Stop 钩子在会话本来要结束时把一个队列项推回主会话，一次只派一件，进度靠数产物文件而不是靠自述。绑定到具体 session，不绑项目；未命中的会话完全静默。适用于长链无人值守推进、以及「模型中途掉语境就忘了自己在干什么」的场景。
---

# heartbeat

会话级心跳：推送权在钩子手上，不在模型手上。

## 机制

Stop 钩子读 payload，匹配到绑定会话且队列有未完成项时，输出 `{"continue": false, "stopReason": "<prompt>"}`；提示词只点名一件，含该项的判据、产物路径和收尾要执行的 `inc`/`block` 命令，并写明不得在同一轮里开始第二件。任何异常被吞掉、记日志、退出 0——钩子不许让宿主会话失败。

## 规则

1. 只有钩子能发起推送。CLI 没有「现在就推一件」的动词，模型只能记账（`inc` / `done` / `block` / `doing` / `todo`）。
2. 一次只派一件，派完即止。
3. 进度验产物，不接受自述：`inc` 数 `--evidence` 文件里匹配 `--pattern` 的行数，不严格增长就拒绝（exit 4）。
4. 绑定到具体 session，不绑项目。session 型绑定不因目录相同而命中。
5. 待办数据存在本技能 `data/`，按会话分文件，不放项目目录——数据放哪，作用域就有多大。
6. 未命中的会话完全静默：不输出、不写日志；日志只记 nudge / hold / autoblock / error。
7. 同一项连续 `stall_limit` 次推送而产物行数没动 → 自动 `blocked` 并换下一项。
8. 链要有上限与过期：`max_nudge_per_chain`、`chain_gap_seconds`、`max_age_hours`。
9. 装没装得上必须能诊断，用 `doctor`：绑定是否命中会话、待办文件在不在、钩子是否注册、链计数到哪。
10. 项目特有的推送前检查用 `pre_nudge_check` 配外部命令，不写死进工具。
11. 配置由命令完成，不手改配置文件：手写错一个字符不报错，只会静默失效。
12. 不做身份猜测：CLI 只认精确 session，不回退到「只有一个 binding 且目录对得上」；钩子只信 payload 里的 `session_id`。不要把本技能注入到多 agent 并行的项目——`SKILL.md` 会被同项目所有会话加载。需要时直接跑 `.agent-tools/heartbeat`。
13. 一个会话同时只跑一条任务线；主线还有活而来了不相干的新任务时，先 `off`。

只处理 `Stop`。`SubagentStop` 与 `UserPromptSubmit` 都不可用：子代理与父会话共用同一个 `session_id`，payload 里没有字段能分开它们。`install` 只写 `Stop` 一个事件，`uninstall` 扫全部事件里含本工具命令的条目。

## 安装与绑定

```bash
agent-ide install heartbeat    # 写启动器（解释器路径烘焙进去）
heartbeat.py install [--scope user|project] [--loop-limit N|-1]   # 装 Stop 钩子，幂等
```

默认装到用户级，作用域靠 `bindings` 收窄；`--loop-limit` 是重入上限（默认 20，合法 -1 或 1..100，超出被上游静默降成 1）。

```bash
heartbeat.py sessions                    # 会话 id 从这里挑；要先跑过一次 Stop 才被记住
heartbeat.py bind --session <id> --work /path/to/project
heartbeat.py on --session <id>
heartbeat.py doctor
```

`bind` 只接受 `--session`，`--cwd` 会被拒。`unbind <session>` 解绑，`exclude <id>...` 排除。

## 待办

```bash
heartbeat.py add "<text>" --evidence <path> --pattern '<re>' \
  --judge "<做成什么样算完>" --total <N>
```

- `--evidence` + `--pattern`：进度来源。不给也能跑，但 `stall` 判不出进展，只能靠链上限兜底。
- `--total`：产物里的目标总行数，不是本件要新增的行数。登记那刻从文件里数出起点，所以 `--total 12` 是「凑到 12 行」。到数自动 `done`。
- `--judge`：写进提示词，是给模型看的判据文本，工具不执行它。
- `set <id> [text]` 可改 `--total / --evidence / --pattern / --judge`，路径或正则写错不必重建队列。

状态机 `todo → doing → done`，任意时刻可 `blocked`（带原因，不参与推送）。

## 命令

| 命令 | 作用 |
|---|---|
| `heartbeat.py` / `hook` | Stop 钩子入口，读 stdin |
| `payload` | 打印钩子收到的 JSON |
| `on [--session <id>]` / `off` | 启用 / 停用（`off` 立即静默） |
| `bind` / `unbind <session>` | 绑定 / 解绑 |
| `add` / `rm <id>` / `set <id>` | 登记、删除、改目标 |
| `inc` / `sync` / `done` / `doing` / `todo` / `block` | 记账与改状态；省略 id 时作用于当前项 |
| `list` / `sessions` / `exclude <id>...` / `doctor` | 查看与自检 |

任何命令可带 `--as <session-id>` 声明调用者身份（等价 `HEARTBEAT_SESSION`）。

退出码：`2` 用法错、`3` 无此任务、`4` 产物未增长被拒、`5` 未绑定（或 install 无启动器）。

## 配置（`data/config.json`，默认值）

`enabled` false、`sessions` []、`exclude` []、`bindings` []、`max_nudge_per_chain` 200、`chain_gap_seconds` 1800（更长间隔算新链并重置计数）、`stall_limit` 6、`max_age_hours` 24（从最后一次进度算，不是最后一次推送）、`pre_nudge_check` ""（推送前执行的 shell 命令，非空 stdout 追加进提示词）。

## 数据布局

全部在本技能 `data/`，不进项目目录：`config.json`、`sessions.json`（见过的会话）、`heartbeat.log`（只记 nudge / hold / autoblock / error）、`tasks/<key>.json`（每会话一条队列）。

## 边界

- 不跨会话；多会话各建一份待办。
- 不注入到多 agent 并行的项目。
- 不做定时：只在「本来就要停」的时刻介入，精确定时用 cron。
- 不替代 `task-queue`：队列管「下一步是什么」（持久 FIFO），心跳管「什么时候把下一步推给你」。
- 不做内容判断。

## 症状 → 命令

| 症状 | 命令 |
|---|---|
| 完全没反应 | `doctor`（绑定命中、任务文件在、钩子注册） |
| 没有可绑的会话 id | `sessions`（要先跑过一次 Stop） |
| exit 5 unbound | `bind --session <id> --work <dir>`，或加 `--as <session-id>` |
| `inc` 报 exit 4 | 产物没增长：去干活，或 `sync` 拉回真实行数 |
| 任务被自动 blocked | `list` 看原因，`todo <id>` 重新启用 |
| 钩子像装了但从不触发 | 重跑 `install`，再 `doctor` |
