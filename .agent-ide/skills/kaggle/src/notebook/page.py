"""Prompt pages: the UI for actions the API cannot take on the user's behalf.

Two verbs end the same way — ``stop`` (kill a run) and ``interact`` (ask the
human to do something on a page that is already open) — so the markup lives here
once instead of twice.

A page is deliberately one headline, one button and a small reference line. The
agent's job is to say what to do and where; the human's job is the click. Any
explanation longer than a sentence belongs in the terminal output, not on the
page the human is staring at.
"""
from __future__ import annotations

import html
import os

from src import paths

_TEMPLATE = """<!doctype html>
<meta charset="utf-8">
<title>{ref}</title>
<style>
  html, body {{ height: 100%; margin: 0; }}
  body {{
    display: flex; flex-direction: column; gap: 28px;
    align-items: center; justify-content: center; text-align: center;
    background: #101112; color: #f2f2f2;
    font: 20px/1.6 -apple-system, "PingFang SC", "Helvetica Neue", sans-serif;
  }}
  h1 {{ font-size: 30px; font-weight: 600; margin: 0; max-width: 26ch; }}
  .ref {{ color: #8a8f98; font-size: 15px; margin: 0; font-family: ui-monospace, monospace; }}
  a {{
    background: #f5c518; color: #101112; text-decoration: none;
    font-weight: 600; padding: 14px 30px; border-radius: 8px;
  }}
  a:hover {{ background: #ffd84d; }}
</style>
<h1>{headline}</h1>
<p class="ref">{ref}</p>
<a href="{url}">{button}</a>
"""


def kernel_url(ref: str) -> str:
    """Editor URL for ``owner/slug`` (where Stop Session and the tabs live)."""
    owner, _, slug = ref.partition("/")
    return f"https://www.kaggle.com/code/{owner}/{slug}"


def write_page(
    *, kind: str, ref: str, headline: str, url: str, button: str
) -> str:
    """Write ``<kind>_<ref>.html`` under the agent's runtime dir; return its path.

    ``kind`` keeps the two verbs from overwriting each other when they target the
    same kernel, and makes the file self-describing a week later.
    """
    ctx = paths.require_ctx()
    os.makedirs(ctx.runtime_dir, exist_ok=True)
    safe = ref.replace("/", "__")
    target = os.path.join(ctx.runtime_dir, f"{kind}_{safe}.html")
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(
            _TEMPLATE.format(
                ref=html.escape(ref),
                headline=html.escape(headline),
                url=html.escape(url),
                button=html.escape(button),
            )
        )
    return target
