---
name: arxiv
description: >-
  arXiv search plus the repo's PDF download engine. `download` consumes any result
  JSON carrying a pdf url — openalex `pdf_url`, arxiv `pdf_link`, any OA host — and
  writes verified PDFs to disk. Use it whenever a search result must become a local
  file for pdf_reader.
---

# arxiv

两个职责：检索 arXiv 预印本；把任意检索结果里的 PDF 落成本地文件。后者是它在流程里的主要用途。

## 核心命令

```bash
# 检索（默认 arXiv 源）
.agent-tools/arxiv <options> "query string"

# 检索 OpenAlex 源（跨学科、带被引数与 OA 链接），检索完直接下载
.agent-tools/arxiv --source openalex --in title_abstract --year_from 2023 \
    --max_results 100 --download --out papers/ "3D Gaussian Splatting"

# 事后下载任何带 pdf url 的结果 JSON
.agent-tools/arxiv download --from <result.json> [--out DIR] [--limit N] [--dry-run] \
    [--delay 1.2] [--retries 3]
```

两个源共用一个 CLI 和同一套字段（`title/year/authors/pdf_link/citations/abstract/doi/venue`），`--download` 与 `download --from` 对两者一视同仁。差异只在检索侧：

| | `--source arxiv`（默认） | `--source openalex` |
|---|---|---|
| 覆盖 | arXiv 预印本 | 跨学科，期刊+会议+预印本 |
| 排序默认 | `submittedDate` | `relevance`（`--sort_by` 可改） |
| 单次上限 | 分页，受 `--max_eval` 约束 | 200 条，无分页 |
| 独有过滤 | `--min_citations` / `--min_upvotes` / `--abstract_contains` | `--year_from` / `--year_to` / `--in` |
| 额外字段 | `hf_upvotes` | `openalex_id`、被引数来自 OpenAlex |

`--from` 接受本技能的检索快照，也接受任何含 `pdf_url`/`pdf_link` 的 JSON；链接不限于 arxiv.org，AAAI OJS、PLOS、机构库同样处理。

## 检索语义与限制（`--source arxiv`）

- 查询按空格切词，每词编码成 `all:<term>`，用 `+AND+` 连接；`and` / `or` / `not` 被丢弃，`A AND B` 等价于 `A B`。
- 不支持字段限定：`ti:gaussian` 会被当成 `all:ti:gaussian` 发给 API，返回 HTTP 400，整次搜索空结果，无降级。
- 不支持短语引号；查询过长或含特殊符号同样易 400。
- `--min_citations` 的数值来自 Crossref `query.bibliographic` 的第一条，不校验标题相似度，因此可能取到另一篇论文的计数；预印本常为 0。需要可靠被引数时用 `--source openalex`。
- 富化的代价固定：即使 `--min_upvotes`、`--min_citations` 都是 0，每篇仍发 2 次请求（HuggingFace + Crossref），串行。
- 分页每页 10 条，总评估上限 `--max_eval`（默认 100），翻页间隔 `--delay`（默认 3.0 s）；`--exclude-cache` 命中 `data/fetch/cache.json` 时打 `[cached]` 并跳过。

## 下载规则（写在代码里）

- 浏览器 User-Agent（AAAI 一类主机会断连默认 python UA）
- 首字节必须是 `%PDF`，否则删除不落盘（失败常返回 200 + HTML）
- 先写 `.part`，校验通过再原子改名；主机支持 `Range` 时可续传
- 目标文件已存在则跳过，命令可重复执行
- 4xx 计入 skipped；连接/5xx 重试 `--retries` 次（默认 3）后计入 failed，有 failed 时退出码 1

选项与示例见 [skills/01_usage.md](skills/01_usage.md)。

## 与相邻技能

| 技能 | 分工 |
|---|---|
| `crossref` | 已知 DOI/ISSN 时的权威元数据与刊内检索，只产元数据，不下载 |
| `pdf-reader` | PDF/URL → 文本，输入是本技能下好的文件 |
| `overleaf` | 块树 → LaTeX → PDF |
