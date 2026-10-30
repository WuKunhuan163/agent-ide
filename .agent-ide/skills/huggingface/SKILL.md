---
name: huggingface
description: >-
  Manage a Hugging Face access token and download single files from a repo over
  HTTPS. Writes model/config files to a local path without the transformers
  stack. Use when a checkpoint must land on disk and no Hugging Face CLI is
  installed.
---

# Hugging Face Tool

## 安装

`.agent-tools/huggingface` 缺失时从技能目录安装：

```bash
python3 .agent-ide/skills/agent-ide/agent-ide.py install --project . huggingface
```

启动器由 `agent-ide` 生成，运行 `huggingface.py`。

## 能力边界

单次流式 GET（`requests`，`timeout=60`）：无重试、无续传、无证书兜底；响应 `Content-Length` 与实际字节数不符即失败退出。一次只取一个文件，不展开仓库、不处理分片。

## 输出契约

stdout 只有结果，一行，tab 分隔：

| 命令 | stdout |
|---|---|
| `download` | `<绝对路径>\t<字节数>` |
| `config` | `<config.json 路径>` |
| `get` | `<token>` |

进度、体积、HTTP 状态、失败信息全部走 stderr，前缀 `[hf]`；进度只在 stderr 是 TTY 时绘制，因此管道取值干净：

```bash
path=$( .agent-tools/huggingface --id <id> download --repo gpt2 --file config.json -d ./ckpt | cut -f1 )
```

退出码：`0` 成功；`1` HTTP 错误 / 网络错误 / 字节数不符 / 无 token / 缺 `--id`。

## 凭据

按 agent id 隔离，token 落在该 id 自己的配置目录：

```bash
.agent-tools/huggingface --id <id> config --token <token>
.agent-tools/huggingface --id <id> get
```

路径：`.agent-ide/skills/huggingface/data/accounts/<id>/config.json`。

## 下载

```bash
.agent-tools/huggingface --id <id> download --repo <repo_id> --file <repo 内文件名> [--revision main] -d <输出目录>
```

```bash
# 公开小文件
.agent-tools/huggingface --id <id> download --repo gpt2 --file config.json -d /tmp/

# 大权重
.agent-tools/huggingface --id <id> download --repo <repo_id> --file <file.safetensors> -d ./checkpoints/
```

## 与相邻技能

| 技能 | 分工 |
|---|---|
| `kaggle` | 另一托管 CLI，管 notebook 与数据集 |
| `agent-ide` | 启动器与 data 分层 |
| `aliyunpan` | 网盘侧传输，与 HF 无关 |
