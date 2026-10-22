---
name: crossref
description: >-
  Crossref metadata for known identifiers — a DOI or an ISSN. Returns authoritative
  records, license/CC status, and journal-scoped search. Not a topic search engine: for
  "find papers about X", use arxiv --source openalex. Keyless and bot-friendly.
---

# Crossref Literature Tool（轻量书目检索）

## 何时读

| 场景 | 读 |
|------|------|
| 查 DOI / 引用元数据 / 快速失败纪律 | 本 SKILL + [skills/01_quick_fail_discipline.md](skills/01_quick_fail_discipline.md) |
| 全文下载踩坑 | [skills/02_download_pitfalls.md](skills/02_download_pitfalls.md) |

## 主要功能（实测 2026-10-22）

Crossref 是 DOI 注册机构（约两万家出版商）的元数据中心，只处理**已知标识**：给出 DOI 或 ISSN，它返回权威记录；不负责“按主题找论文”。四项能力按实际使用频率排列。

### 1. 期刊内精确检索（最常用）

```bash
.agent-tools/crossref --id 毕设 search-issn 0195-6663 "health claim" --rows 3
```

```
Functional foods: health claim-food product compatibility and the impact of health claim framing on consumer evaluation	2005	312	10.1016/j.appet.2005.01.009	Appetite
Effect of a health claim and personal characteristics on consumer acceptance of fruit juices...	2009	129	10.1016/j.appet.2009.05.014	Appetite
```

一条一行，制表符分隔：`title → year → cited → doi → journal`。总数走 stderr（`[crossref] 333 matches in ISSN 0195-6663`），所以 `| cut -f4` 直接拿 DOI、`| cut -f2` 按年份排。

唯一的“限定在单本刊内”的入口。对比：全库 `search "consumer health claim"` 返回 total 528 万且无相关性排序，不适合选题。

### 2. DOI 权威元数据

```bash
.agent-tools/crossref --id 毕设 work 10.1016/j.appet.2005.01.009
```

```
title	Functional foods: health claim-food product compatibility and the impact of health claim framing on consumer evaluation
year	2005
journal	Appetite
volume	44(3)
pages	299-308
doi	10.1016/j.appet.2005.01.009
type	journal-article
cited	312
license	-
license_url	-
authors	Ellen van Kleef, Hans C.M. van Trijp, Pieternel Luning
abstract	-
```

`key<TAB>value` 一行一项，缺值统一 `-`。实测 ACM TOG、PLOS 有 `abstract`，Elsevier 为 `-`。用于引用格式核对与去重。

### 3. 许可判定

| DOI | 出版方 | 实测输出 |
|---|---|---|
| `10.1371/journal.pcbi.1002195` | PLOS | `License: CC-BY` + `creativecommons.org/licenses/by/4.0/` |
| `10.3390/nu12010001` | MDPI | `License: CC-BY` |
| `10.1145/3592433` | ACM (TOG) | `License: None`（订阅） |

`License: None` 只表示 Crossref 未登记开放许可，不等于闭源；要判断能否复用全文，看 `arxiv --source openalex` 结果里的 `pdf_link` 是否为空。

### 4. 期刊画像

```bash
.agent-tools/crossref --id 毕设 journal 0195-6663
```

```
name	Appetite
issn	0195-6663, 1095-8304
publisher	Elsevier
subject	-
```

给出一本刊的 ISSN 对（印刷 + 电子）与出版方；`subject` 恒为 `-` 时不要依赖它做学科判断。

> 输出约定：结果只走 stdout（`tab` 分隔，无颜色、无 `[INFO]`、无分隔线），匹配数/警告/失败原因全部走 stderr。和 `arxiv` 的搜索输出保持同一套习惯。

### 不适用

- 只有主题词、要跨库找论文 → `arxiv --source openalex`
- 找 OA 链接 → 同上，结果里的 `pdf_link` 即 OA 副本
- 下载 PDF → `arxiv download --from <那个 JSON>`
- CS 会议 venue → `arxiv --source openalex`（venue 列即 `primary_location.source.display_name`，已聚合 DBLP）

**无需 key、爬虫友好**，`--mailto` 可进 polite pool。

## 适用性与局限性（SCOPE）

| 方面 | 说明 |
|------|------|
| ✅ 适用范围 | 任意学科（DOI 注册的期刊/书籍/会议） |
| ✅ 核心优势 | 按期刊 ISSN 精确过滤；无需 key；返回标题/作者/年份/DOI/卷期页/CC 许可 |
| ✅ 稳定性 | 爬虫友好（JSON API），polite pool（加 `--mailto`）可提速 |
| ⚠️ 限制 1 | 摘要取决于出版商：实测 ACM（TOG）、PLOS 返回完整摘要，Elsevier 等常缺；无全文 |
| ⚠️ 限制 2 | 只覆盖注册了 DOI 的出版物 |
| ❌ 不适用 | 查找 OA 副本/Pdf 下载位置、CS 会议 venue → `arxiv --source openalex` |

## Mandatory Initialization

**CRITICAL RULE**: Whenever you start working in a new repository or directory, you **MUST** first check if the project already has the `crossref` executable installed:

```bash
python3 .agent-ide/skills/agent-ide/agent-ide.py install --project . crossref
```

## Usage

```bash
.agent-tools/crossref --id <agent_id> search-issn <ISSN> "<主题词>" [--rows 10] [--from-year 2023]
.agent-tools/crossref --id <agent_id> search "<主题词>" [--rows 10] [--from-year 2023]
.agent-tools/crossref --id <agent_id> work <DOI>
.agent-tools/crossref --id <agent_id> journal <ISSN>
# 可选规制参数：
.agent-tools/crossref --id <agent_id> search-issn <ISSN> "<主题词>" --budget-seconds 60 --max-retries 2
```

推荐始终加 `--mailto your@email.com` 进入 polite pool（提升速率限制）。结果 JSON 自动保存到 `data/results/<agent_id>/`。

## Mandatory Time Budget（快速失败纪律）

**CRITICAL RULE**: 找论文/下载全文默认快速失败，只有用户明确要求"仔细找"等极少数情况才放开。

- 工具内置 `--budget-seconds`（默认 120s）与 `--max-retries`（默认 3）：预算耗尽即中止重试并打印 `[QUICK-FAIL]`
- 单篇全文下载预算 ≤ 5 分钟、≤ 3 种来源，超时记录 `refXXX 未获取全文 | 原因` 并转向下一篇
- 付费墙且无 OA（Unpaywall/OpenAlex 均 `is_oa=False`）→ 不下载，直接保留元数据
- 禁止 Sci-Hub/非法镜像（版权红线）
- 详细纪律与踩坑见 `skills/01_quick_fail_discipline.md`、`skills/02_download_pitfalls.md`
## 与相邻技能

| 技能 | 分工 |
|------|------|
| `arxiv` | 主题检索（arXiv + OpenAlex 双源）与 PDF 下载 |
| `lit_research` | 深读与实证迁移（尚未迁移到 .agent-ide，仅 tmp 快照） |

