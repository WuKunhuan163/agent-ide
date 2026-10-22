---
name: arxiv
description: >-
  arXiv search plus the repo's PDF download engine. `download` consumes any result
  JSON carrying a pdf url — openalex `pdf_url`, arxiv `pdf_link`, any OA host — and
  writes verified PDFs to disk. Use it whenever a search result must become a local
  file for pdf_reader.
---

# arxiv

两个职责：检索 arXiv 预印本；**把任意检索结果里的 PDF 落成本地文件**。后者是本技能在流程里的主要用途——OpenAlex 源与 crossref 只产元数据，全文要靠这里拿。

## 何时读

| 场景 | 读 |
|------|-----|
| 把检索结果下载成本地 PDF | 本 SKILL「核心命令」的 `download`，细节见 [skills/01_usage.md](skills/01_usage.md) |
| 文献检索（arXiv API） | 本 SKILL + [skills/01_usage.md](skills/01_usage.md) |
| 安装/更新 CLI | `agent-ide install arxiv` → `.agent-tools/arxiv` |

## 核心命令

```bash
# 检索（默认 arXiv 源）
.agent-tools/arxiv <options> "query string"

# 检索 OpenAlex 源（跨学科、带被引数与 OA 链接），检索完直接下载
.agent-tools/arxiv --source openalex --in title_abstract --year_from 2023 \
    --max_results 100 --download --out papers/ "3D Gaussian Splatting"

# 事后下载任何带 pdf url 的结果 JSON
.agent-tools/arxiv download --from <result.json> [--out DIR] [--limit N] [--dry-run]
```

两个源共用一个 CLI 和同一套记录字段（`title/year/authors/pdf_link/citations/abstract/doi/venue`），所以 `--download` 与 `download --from` 对两者一视同仁。差异只在检索侧：

| | `--source arxiv`（默认） | `--source openalex` |
|---|---|---|
| 覆盖 | arXiv 预印本 | 跨学科，期刊+会议+预印本 |
| 排序默认 | `submittedDate` | `relevance`（可用 `--sort_by` 改） |
| 单次上限 | 分页，受 `--max_eval` 约束 | 200 条，无分页 |
| 独有过滤 | `--min_citations` / `--min_upvotes` / `--abstract_contains` | `--year_from` / `--year_to` / `--in` |
| 额外字段 | `hf_upvotes` | `openalex_id`、被引数来自 OpenAlex |

`--from` 接受本技能的检索快照（`--source openalex` 时约 88% 记录带 `pdf_link`），也接受任何含 `pdf_url`/`pdf_link` 的旧 JSON。链接不限于 arxiv.org：AAAI OJS、PLOS、机构库同样处理。

### 检索语义与已知限制（`--source arxiv`）

- 查询按空格切词，每词编码成 `all:<term>`，用 `+AND+` 连接；`and` / `or` / `not` 三个词被**直接丢弃**，写 `A AND B` 等价于 `A B`。
- **不支持字段限定**：`ti:gaussian` 会被当成 `all:ti:gaussian` 发给 arXiv API，返回 HTTP 400；没有降级，整次搜索得到空结果。
- 不支持短语引号；查询过长或含特殊符号同样容易 400。
- **引用数不可当门槛**：数值来自 Crossref `query.bibliographic` 的**第一条**，不校验标题相似度。实测 3 篇里只有 1 篇匹配正确，另两篇拿到的是完全不同论文的计数；预印本在 Crossref 常为 0。需要真实被引数时用 `--source openalex`（OpenAlex 自身计数：同一领域实测 251 / 582 次，而 arxiv 侧显示 0）。
- **富化代价固定**：即使 `--min_upvotes` 和 `--min_citations` 都是 0，每篇仍发 2 次请求（HuggingFace + Crossref）。实测 3 篇 6.2 s（`--delay 0.5`），100 篇约 170 s，串行。
- 分页每页 10 条，总评估上限 `--max_eval`（默认 100）；`--exclude-cache` 命中 `data/fetch/cache.json` 的记录会打印 `[CACHED]` 并跳过。

下载规则固定在代码里，不靠调用方记得：

- 浏览器 User-Agent（AAAI 一类主机会断连默认 python UA）；
- 首字节必须是 `%PDF`，否则删掉不落盘（失败时常返回 200 + HTML）；
- 先写 `.part`，校验通过再原子改名；支持 `Range` 的主机可续传；
- 目标文件已存在则跳过，命令可重复执行；
- 4xx 计入 skipped，连接/5xx 重试 3 次后计入 failed，有 failed 时进程退出码为 1。

选项、示例与铁律见 [skills/01_usage.md](skills/01_usage.md)。

## 与相邻技能

| 技能 | 分工 |
|------|------|
| `lit_research` | 阅读流程、树挂载、Gate-M（尚未迁移） |
| `crossref` | 引用数 enrichment（arxiv 内置调用，标题首条匹配，可靠性低；准确计数用 `--source openalex`） |
| `pdf_reader` | 全文解析，输入就是本技能下好的 PDF |
