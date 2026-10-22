# arxiv — CLI 用法

## 铁律

检索命令返回后，**同一 turn 内**必须解析结果并继续下游工具（Write、Shell 等）。不得仅执行 arxiv 即结束 turn。

## 安装

```bash
python3 .agent-ide/skills/agent-ide/agent-ide.py install --project . arxiv
```

## 命令

```bash
.agent-tools/arxiv <options> "query string"
.agent-tools/arxiv download --from <result.json> [--out DIR] [--limit N] [--delay S] [--dry-run]
```

### 选项

* `query`：空格分隔关键词，隐式 AND。勿写字面 `AND`/`OR`/`NOT`。
* `--max_results`, `-m`：展示条数上限。
* `--sort_by`, `-s`：`relevance` | `submittedDate` | `lastUpdatedDate`（未指定时：arxiv 源 `submittedDate`，openalex 源 `relevance`；openalex 源没有 last-updated 排序，该值回落为 relevance）。
* `--min_citations`：Crossref 引用数下限。
* `--min_upvotes`：Hugging Face Daily Papers 点赞下限。
* `--abstract_contains`：摘要必须包含的关键词。
* `--max_eval`：最多评估篇数（默认 100）。
* `--delay`：分页请求间隔（秒）。
* `--exclude-cache`：跳过 cache.json 中已见论文。
* `--source arxiv|openalex`：检索源，默认 `arxiv`。openalex 源跨学科、带被引数与 OA 链接。
* `--year_from` / `--year_to`：openalex 源的年份过滤。
* `--in fulltext|title_abstract`：openalex 源的检索范围，`title_abstract` 噪声小得多。
* `--download`：检索后直接下载命中记录的 PDF。
* `--out`：`--download` 的目标目录，默认 `data/fetch/pdfs/`。

### 查询语法（arxiv 源）

| 想写 | 实际行为 |
|---|---|
| `health claim` | `all:health +AND+ all:claim`，标题/摘要/全文/作者里都匹配 |
| `health AND claim` | 同上一行，`AND` 被丢弃 |
| `ti:gaussian` | **HTTP 400**，`ti:gaussian` 被当成一个普通词 |
| `"3D Gaussian Splatting"` | 引号不生效，按三个词 AND |

没有字段限定（`ti:`/`au:`/`abs:`）、没有短语、没有 OR。查询报 400 时不会降级，直接返回空。

### 过滤链与代价

每篇论文依次过：本地 `--abstract_contains` → HuggingFace 点赞 → Crossref 引用数。后两项**无条件发请求**（即使阈值为 0，也要取值用于展示）：

- 每篇 2 次外部请求，串行；实测 3 篇 6.2 s（`--delay 0.5`），100 篇约 170 s。
- Crossref 引用数取 `rows=1` 的第一条，**不校验标题**，实测 3 篇错 2 篇；预印本常为 0。`--min_citations` 会按错误数字误杀，不要用它当硬门槛。
- 要准确的被引数：`--source openalex`（OpenAlex 自有计数）。

### 示例

```bash
.agent-tools/arxiv --max_results 3 "controllable neural scene generation"
.agent-tools/arxiv --max_results 5 --sort_by relevance --exclude-cache "neural rendering score distillation"
.agent-tools/arxiv --max_results 3 --min_upvotes 50 --abstract_contains "keyword" "Example Topic"
.agent-tools/arxiv --max_results 5 --delay 1.0 "NeRF reconstruction"

# openalex 源：跨学科、按被引/相关度，检索完直接落盘
.agent-tools/arxiv --source openalex --in title_abstract --year_from 2023 --max_results 50 --download --out papers/ "3D Gaussian Splatting"
```

## 下载

```bash
# 吃本技能自己的检索快照（openalex 源与 arxiv 源格式一致）
.agent-tools/arxiv download --from .agent-ide/skills/arxiv/data/fetch/results/<ts>_<hash>.json --out papers/

# 先看会下哪些，再决定
.agent-tools/arxiv download --from results.json --dry-run

# 只要前 10 篇，1.2s 间隔（默认）
.agent-tools/arxiv download --from results.json --limit 10 --delay 1.2
```

| 选项 | 作用 |
|---|---|
| `--from` | 结果 JSON：本技能的 `pdf_link`，或旧快照里的 `pdf_url`/`link` |
| `--out` | 目标目录，默认 `data/fetch/pdfs/` |
| `--limit` | 只下前 N 篇 |
| `--delay` | 每次请求间隔，默认 1.2s；arXiv 不要低于 1s |
| `--retries` | 连接/5xx 重试次数，默认 3 |
| `--dry-run` | 只打印 URL，不下载 |

行为：

- 文件名 = `标题 slug + URL 哈希前 8 位`，同一 URL 稳定；已存在直接跳过（可重复执行）。
- 先写 `<name>.pdf.part`，首 4 字节校验 `%PDF` 后才原子改名；不是 PDF 则删除并计入失败。
- 部分主机会断连默认 `python-requests` UA，因此固定发送浏览器 UA；AAAI/PLOS/机构库同样适用。
- 支持 `Range` 的主机（arXiv：`206`）可断点续传；不支持的整包重下。
- 4xx → skipped；连接错误与 5xx → 重试后 failed。有 failed 时退出码 1。
