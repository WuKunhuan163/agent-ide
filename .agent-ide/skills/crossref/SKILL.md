---
name: crossref
description: >-
  Crossref metadata for known identifiers — a DOI or an ISSN. Returns authoritative
  records, license/CC status, and journal-scoped search. Not a topic search engine: for
  "find papers about X", use arxiv --source openalex. Keyless and bot-friendly.
---

# crossref

Crossref 是 DOI 注册机构的元数据中心，只处理**已知标识**：给出 DOI 或 ISSN，返回权威记录；不负责按主题找论文。

## 调用形式

顶层参数写在子命令**之前**，写在后面会被 argparse 拒绝：

```bash
.agent-tools/crossref --id <id> [--mailto <email>] <subcommand> ...
```

| 子命令 | 用途 |
|---|---|
| `search-issn <ISSN> "<词>" [--rows] [--from-year] [--sort]` | 刊内检索，唯一能限定单本刊的入口 |
| `search "<词>" [--rows] [--from-year]` | 全库检索，无相关性排序，不适合选题 |
| `work <DOI>` | DOI 权威元数据 |
| `journal <ISSN>` | 期刊画像 |

规整参数：`--rows`（默认 10）、`--from-year`、`--budget-seconds`（默认 120）、`--max-retries`（默认 3）、`--sort`（`search-issn` 独有，`relevance|score|published`，缺省即 API 默认）。`--mailto` 进 polite pool，可提速；默认取环境变量 `CROSSREF_MAILTO`。无需 key。

结果 JSON 存 `.agent-ide/skills/crossref/data/results/<id>/<时间戳>_<命令>_<hash>.json`。

## 输出

结果只走 stdout，`tab` 分隔，无颜色、无前缀、无分隔线；匹配数、警告、失败原因走 stderr。

`search-issn` 一行一篇，列序固定：

```
title → year → cited → doi → journal
```

所以 `| cut -f4` 取 DOI、`| cut -f2` 按年排。总数在 stderr（`[crossref] <N> matches in ISSN <ISSN>`）。

`work` 是 `key<TAB>value`，一行一项，缺值统一写 `-`：

```
title / year / journal / volume / pages / doi / type / cited / license / license_url / authors / abstract
```

`journal` 的字段：`name / issn / publisher / subject`。

## 字段含义

- `license` / `license_url`：`License: None` 只表示 Crossref 未登记开放许可，不等于闭源；判断能否复用全文看 OA 侧有无全文链接。
- `abstract`：取决于出版商，同一批数据里有的有、有的恒为 `-`，不要假定存在。
- `cited`：Crossref 计数，与 OpenAlex 口径不同，跨源比较前先统一。
- `subject`：常为空，不要依赖它做学科判断。

## 快速失败

- `--budget-seconds` 耗尽即中止重试并打印 `[QUICK-FAIL]`，不要在一个检索上反复重试。
- 本工具只产元数据，不下载全文。全文由 `arxiv download` 负责。
- 详细纪律见 [skills/01_quick_fail_discipline.md](skills/01_quick_fail_discipline.md)。

## 适用范围

| 方面 | 说明 |
|---|---|
| 适用 | 任意有 DOI 的期刊/书籍/会议记录 |
| 优势 | 按 ISSN 精确过滤；无需 key；返回标题/作者/年/DOI/卷期页/许可 |
| 限制 | 摘要取决于出版商；只覆盖注册了 DOI 的出版物；无全文 |
| 不适用 | 按主题找论文、找 OA 副本、CS 会议 venue → `arxiv --source openalex` |

## 安装

```bash
python3 .agent-ide/skills/agent-ide/agent-ide.py install --project . crossref
```

## 与相邻技能

| 技能 | 分工 |
|---|---|
| `arxiv` | 主题检索（arXiv + OpenAlex 双源）与 PDF 下载 |
| `pdf-reader` | PDF/URL → 文本 |
| `overleaf` | 块树 → LaTeX → PDF |
