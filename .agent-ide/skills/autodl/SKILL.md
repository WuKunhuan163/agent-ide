---
name: autodl
description: >-
  AutoDL GPU rental helper: inspect stock, start, stop and release a 容器实例 Pro
  instance over the official API, then log in or run one command on it. Read this
  skill when a GPU box must be inspected or run on, or when a running box must be
  stopped so billing ends.
---

# autodl

计费只取决于一件事：实例是否开机。空闲与满载同价，所以这套工具的重点是 `stop` 与「现在还有什么在跑」。

## Verbs

| Task | Command |
|---|---|
| 当前用哪个 token | `credentials` / `credentials --set-token <t>` |
| 有哪些规格、镜像、可用区 | `gpus` |
| 某个卡型哪里有货 | `stock [--region A,B] [--gpu <exact id>]`（无价格，设计如此） |
| 账号上有哪些实例 | `ls [--page N] [--size N] [--status running]` |
| 状态、ssh、价格、端口、实时负载 | `info <uuid>` |
| 开机 / 关机 | `start <uuid> [--start-command CMD] [--no-watch]` / `stop <uuid>` |
| 按需等待有货并给控制台深链 | `watch --gpu <子串> --region <子串> [--max-price 元] [--minutes N]` |
| 彻底删除 | `release <uuid> --yes`（先做快照） |
| 登录 / 跑一条命令 | `ssh <uuid>` / `exec <uuid> "nvidia-smi"` |
| 私有镜像 | `images`、`image-save <uuid> --name <name>` |
| 市场价与机型 | `market [--gpu 子串] [--pro] [--all]` |
| 自动关机 | `watchdog [uuid] [--foreground] \| --status \| --off` |

**没有 `create`**：开发者 API 不提供租机，新实例只能在控制台创建；本工具对已存在实例做开关与执行。也没有 `await`（现名 `watch`）、没有 `start --cpu`。

## Entry

```bash
python3 .agent-ide/skills/autodl/autodl.py <command> [args]
# 或安装后
.agent-tools/autodl <command> [args]
```

## Data

全部状态是 `data/` 下的文件；不读环境变量，所以同一份 `data/` 在任何 shell 下行为一致。

`data/credentials.json`（0600，gitignored）：

```json
{ "token": "", "account": "", "defaults": { "gpu_spec": "", "image": "", "cuda": 118, "region": "" } }
```

- `token` 是唯一必填项；缺失时 exit 3 并指出文件位置与控制台路径。
- `account` 仅回显。
- `defaults.*` 当前仅被 `credentials` 回显，没有命令消费它——不要以为填了就能省掉参数。

只有一种可用 token：控制台 → 设置 → 开发者Token，**原样**粘贴（不带 `Bearer `），JWT 的 `aud` 为 `develop_api`。两条产品线共用它，都在 `https://api.autodl.com`：

| 产品线 | 同一 token | 额外条件 |
|---|---|---|
| 容器实例 Pro (`instance/pro/*`) | 是 | 个人实名或企业认证 |
| 弹性部署 (`deployment/*`) | 是 | 企业认证 |
| 弹性部署 GPU 库存 (`machine/region/gpu_stock`) | 是 | 无 |

两类形似的东西**刻意不存**：

- 浏览器会话 token：同形 JWT，但 `aud` 不是 `develop_api`，所有开发者端点都拒，存了只会制造「登录超时」的假线索。
- `private.autodl.com`：不是开发者 API 主机，`instance/pro/list` 在那里 404，库存路径回 `AuthorizeFailed`。

`credentials --set-token` 用 `POST /instance/pro/list` 验证（不需要额外权限的最低门槛），验证失败则零写入。

`data/config.json` 只放 `base_url`（空 = 官方地址；填值可指向代理或本地 stub）与 `watchdog` 配置块。

## Rules

1. **stdout 是答案，stderr 是旁白。** `ls` / `images` / `info` / `gpus` / `stock` / `ssh` / `exec` 的数据走 stdout，一行一条记录，无表头、无合计、无前缀。诊断（分页提示、警告、失败）走 stderr，前缀 `autodl: `。没有 `--json`。
2. **成功是安静的。** `start` / `stop` / `release` / `credentials --set-token` 成功时不打印，退出码即回执。`image-save` 只打印新 `image_uuid`，便于捕获。
3. **退出码是机器契约。** 0 成功、1 其他/中断、2 用法、3 无 token、4 凭据被拒、5 未找到端点、6 API 拒绝请求、7 网络、8 无当前资源访问权限、9 无法非交互 ssh。`exec` 原样透传远端退出码。
4. **花钱要有 `--yes`。** `release` 恒需人工 `--yes`：无 `--yes` 时打印 `refused: … --yes to release` 并 exit 2。
5. **`release` 前必须已关机。** 状态不是 `shutdown` 时 exit 2 并提示 `autodl stop <uuid>`，不会在一次调用里既关又删。
6. **每次开机挂看门狗。** `start` 在返回前 detach 一个，见 `docs/watchdog.md`。已知缺陷：`--foreground` 启动会因读取不存在的 `tokens` 键抛 KeyError，前台调试不可用。

不轮询：`start` / `stop` / `release` 在 API 接受后立即返回，事后用 `info <uuid>` 查看结果。

## Limits

- 只覆盖**容器实例 Pro**，只有按量付费。控制台的标准实例不可寻址；`ls` 里没有的实例，本工具管不了。
- **API 不支持无卡模式开机。** 官方 Pro 文档写明 `payload` 取 `gpu`、暂不支持 API 以无卡模式开机。便宜地改代码要走控制台的无卡模式。
- **没有定时关机端点**，API 只回报 `timed_shutdown_at`。
- **容器不能自己关机。** `--start-command "…; poweroff"` 不结束计费；结束只能从外部 `stop`。
- **`无当前资源访问权限` 是账号×产品闸门，不是没货、也不是实名问题。** 参数非法（`{}`、`disk 9999`）会先被参数校验挡掉并回 `RequestParameterIsWrong`；而伪造的 `gpu_spec_uuid`、伪造的 `image_uuid`、伪造的 region 都回同一句话，说明资源查询之前有一道统一闸门。等货无用，需账号开通「容器实例Pro 开放API」；找客服时带 `request_id`。
- **`stock` 按 GPU 型号报 `idle/total`，不按 Pro 规格，且是单卡计数**：200 张空闲 4090 不等于有 8 卡机。响应为 `[{model: {total_gpu_num, idle_gpu_num, chip_corp, cpu_arch}}]`，无价格字段。`region_sign` 必填，区在请求里而不在响应里，所以按区逐个请求再合并。
- **`stock --gpu` 按标识整串匹配**：`4090` 会被拒（需要 `RTX 4090`），错误信息会列出可用标识。响应形状无文档，解析按结构而非字段位置，遇到没见过的形状 exit 6 一行。
- **`market` 是唯一带价格的接口，且免 token。** 走 `POST /api/v1/machine/list`（body：`page_index` / `page_size` / `region_sign_list` / `gpu_name_list` / `charge_type: payg`），返回开发者 API 不给的 `region_name`、`gpu_idle_num`、`payg_price`（**整机价**，除以 `gpu_number` 得单卡价）、`enable_container_pro`（该机器能否承载 Pro 实例）。默认只列 `gpu_idle_num>0`。
- **`payg_price` 有两套标度，取数时看来源。** `market`/`watch` 侧按**厘**处理（`round(price/10)` 得分，再 ÷100 得元，1980 → ¥1.98/card·h）；`info`/`snapshot` 侧直接按**分**（÷100）。同名不同口径，代码未统一，交叉引用时先确认来自哪个命令。
- **信封裁判。** 成功只认 `code == "Success"`，不看 HTTP 状态（拒绝也会是 200）。拒绝时保留 `request_id`，那是客服唯一能追的串。
- `snapshot` 与 `status` 官方文档写成 `GET` 带 JSON body，不可移植，实际按 query 参数发送。

## Reading `AuthorizeFailed`

报错文案是 `登录超时，请重新登录`，描述症状不描述原因。每次鉴权失败都会附上本地诊断——从 JWT 里解出的 `aud`：

| `aud=…` | 含义 | 下一步 |
|---|---|---|
| `develop_api` | 类型对但已失效 | 重新生成（控制台重新登录会使旧 token 失效）；新 token 同样失败说明账号还不能用容器实例 Pro |
| 其它值 | 为别的受众签发 | 贴错了串 |
| 无 | 不是签名 token | 复制开发者Token原文 |

`credentials` 会打印同一字段，租机之前就能看出凭据类型。

## On the box

1. **两个文件系统，一条规则。** `/` 小，只放环境；`/root/autodl-tmp` 大，放权重、数据、runs。尺寸一律 `df -h / /root/autodl-tmp` 实测。
2. **`start` 默认按 GPU 开机。** 想不付卡钱改代码，用控制台的无卡模式，API 没有这条路。
3. **探针走 `exec`，长任务走 `nohup`。** `exec` 里跑训练会随会话静默死掉。
4. **`stop` 是唯一止付动作。** 容器不能自关机，也没有定时关机 API；`start` 挂的看门狗在无任务时替你 `stop`。
5. 产物不能只留在机器上：`stop` 保数据盘、`release` 删数据盘，拉回本地再 `release`。

## ssh and exec

`ssh <uuid>` 打印 ssh 命令与 root 密码（取自 snapshot），第一行可用 `head -1` 取。`exec` 需要非交互路径，即 `sshpass`（`brew install hudochenkov/sshpass/sshpass`）；缺失时 exit 9 一行，不会挂在密码提示上。

## Files

| File | Holds |
|---|---|
| `src/client.py` | 数据文件、端点路径、信封、失败分类 |
| `src/cli.py` | 动词、花费闸门、行格式 |
| `src/watchdog.py` | 后台关机：探针、判据、detach、状态文件 |
| `data/README.md` | 逐字段说明该填哪个文件 |
| `docs/*.md` | 机器侧细节：生命周期、磁盘、环境、长任务、产物、看门狗、症状表 |
