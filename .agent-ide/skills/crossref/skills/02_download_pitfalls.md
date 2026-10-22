# 02 · 下载踩坑记录（Download Pitfalls）

实战踩坑总结（持续更新）。所有坑均为真实发生过。

## 各来源反爬/可用性速查

| 来源 | 状态 | 处理方式 |
|---|---|---|
| Nature 官网（OA 文章） | ✅ 可直下 | `https://www.nature.com/articles/<id>.pdf`，UA 伪装 Chrome |
| Europe PMC | ✅ 可绕过官方 PMC | `https://europepmc.org/articles/PMC<id>?pdf=render` 直下真 PDF |
| 官方 PMC（ncbi.nlm.nih.gov/pmc） | ❌ reCAPTCHA | curl 只返回 HTML，必须换 Europe PMC |
| MDPI | ❌ IP 封锁 | 放弃，等网络环境 |
| Elsevier ScienceDirect | ❌ 403 | 放弃；FQ&P/Appetite 等 Elsevier 刊多为付费墙 |
| Emerald（BFJ 等） | ❌ 反爬强 | 放弃 |
| Springer | ⚠️ Cloudflare | 偶可 agent-browser 绕，成本高 |
| 机构库 DSpace 7（citaREA 等） | ⚠️ Angular SPA | curl/API 全被壳页面拦截，agent-browser snapshot 可见链接但 download 定位失败（shadow DOM），高成本 |
| CiteSeerX | ⚠️ 不稳定 | DOI 格式常变，命中率低 |

## 已验证技巧

- **UA 伪装**：`-A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0"`，curl 默认 UA 必被拦
- **Europe PMC 绕过**：官方 PMC 反爬时，把 `https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9998796/pdf/` 换成 `https://europepmc.org/articles/PMC9998796?pdf=render`
- **下载后必须验证**：`file xxx.pdf`，若是 `HTML document` 说明被反爬，不是真 PDF
- **Unpaywall 免费查 OA**（无需 key，限流宽松）：
  `curl -s "https://api.unpaywall.org/v2/<DOI>?email=<your-email>"`，看 `oa_locations[].url_for_pdf`

## 高被引经典文献（无 OA 但有公开镜像）

如 Ajzen 1991 TPB（被引 7 万+）：官网 people.umass.edu/aizen 只提供测量问卷，不提供原文。可试大学课程镜像（Bing/DDG 搜 `title filetype:pdf`），但搜索引擎本身也被反爬，命中率约 30%，按快速失败纪律控制。

## 教训

1. **先查 OA 再下载**：先 Unpaywall/OpenAlex 确认 `is_oa`，付费墙直接跳过，别先下载再发现是 HTML
2. **单篇 ≤ 3 来源**：超过立即记录放弃，转向下一篇
3. **不要把时间耗在 SPA 机构库**：shadow DOM 内链接 download 命令无法定位，属高成本低回报
