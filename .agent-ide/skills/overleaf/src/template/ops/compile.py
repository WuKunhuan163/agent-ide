"""TeX lint and tectonic compilation for a rendered document."""
from __future__ import annotations

import os
import re
import subprocess

_INTERMEDIATE_EXTS = (".aux", ".bbl", ".blg", ".brf", ".out", ".log")
# A hung tectonic would otherwise wedge the CLI forever.
COMPILE_TIMEOUT_SECONDS = 300


class CompileError(RuntimeError):
    pass


def lint_tex(filepath: str) -> list[str]:
    """Report hyperref / float-label ordering problems.

    Read-only by design: a linter that rewrites the document it inspects makes
    the generated `.tex` stop being what the template produced. Anything that
    must change belongs in the instance's TeX, and is warned about here.
    """
    warnings: list[str] = []
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    envs = re.findall(
        r"\\begin\{(?:figure|table)\*?\}.*?\\end\{(?:figure|table)\*?\}", content, re.DOTALL
    )
    for env in envs:
        caption_pos = env.find(r"\caption")
        label_pos = env.find(r"\label{")
        if caption_pos != -1 and label_pos != -1 and label_pos < caption_pos:
            match = re.search(r"\\label\{([^}]+)\}", env[label_pos:])
            name = match.group(1) if match else "unknown"
            warnings.append(
                f"\\label{{{name}}} appears before \\caption; hyperlink targets may jump."
            )

    if r"\usepackage{hyperref}" in content:
        preamble = content.split(r"\begin{document}")[0]
        packages = re.findall(r"\\usepackage(?:\[.*?\])?\{.*?\}", preamble)
        if packages and "hyperref" not in packages[-1]:
            warnings.append(r"\usepackage{hyperref} is not the last package loaded.")
        if re.search(r"\\hypersetup\s*\{", content) and "breaklinks" not in content:
            warnings.append(r"\hypersetup does not set breaklinks; long URLs will not break.")
    return warnings


def compile_tex(filepath: str) -> str:
    """Run tectonic once and return the produced PDF path.

    Runs in the `.tex` directory via `cwd=` rather than `os.chdir`, so the
    process never mutates global state.
    """
    basename = os.path.splitext(os.path.basename(filepath))[0]
    dirname = os.path.dirname(os.path.abspath(filepath))
    pdf_path = os.path.join(dirname, f"{basename}.pdf")

    for stale in _intermediates(dirname, basename):
        if os.path.exists(stale):
            os.remove(stale)

    try:
        res = subprocess.run(
            ["tectonic", "--print", os.path.basename(filepath)],
            capture_output=True,
            text=True,
            cwd=dirname,
            timeout=COMPILE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise CompileError(f"tectonic did not finish within {COMPILE_TIMEOUT_SECONDS}s")

    output = res.stdout + "\n" + res.stderr
    if res.returncode != 0:
        raise CompileError(f"tectonic failed:\n{output}")
    if "errors were issued by BibTeX" in output.lower():
        raise CompileError(f"BibTeX errors in tectonic output:\n{output}")

    if not os.path.exists(pdf_path):
        raise CompileError(f"expected output PDF {os.path.basename(pdf_path)} was not generated")
    size = os.path.getsize(pdf_path)
    if size < 1024:
        raise CompileError(f"PDF {os.path.basename(pdf_path)} is suspiciously small ({size} bytes)")

    # keep only the PDF: drop LaTeX/BibTeX intermediates
    for junk in _intermediates(dirname, basename):
        try:
            if os.path.exists(junk):
                os.remove(junk)
        except OSError:
            pass
    return pdf_path


def tail_warnings(pdf_path: str, *, max_words: int = 3, min_fill: float = 0.20,
                  limit: int = 5) -> list[str]:
    """段末行断尾：在成品 PDF 上量，返回可直接展示的提示。

    为什么在这里而不是在 block 里：断尾是排版结果，块层看不到。判据只用几何——
    两端对齐的正文里非段末行必然被撑满，所以"墨迹明显短于本栏右界"就是段末行。

    栏宽自标定：按行首 x0 分栏（实例可能是单栏或双栏），同栏里最长的 x1 就是该栏右界，
    因此不需要每个实例再报一次 \\textwidth，也不需要知道是 article 还是 twocolumn。
    """
    try:
        import fitz
    except ImportError:
        return []
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return []

    skip = re.compile(r"^(\d{1,4}|[ivxlcdm]{1,6}|Chapter\s+\d+\..*|References|"
                      r"Table of Contents|Contents|Abstract)$", re.IGNORECASE)
    lines = []
    refs_page = None
    for page in doc:
        raw = []
        for blk in page.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                txt = "".join(s["text"] for s in ln["spans"]).strip()
                if not txt:
                    continue
                if refs_page is None and txt.lower() == "references":
                    refs_page = page.number + 1
                bold = all(("Bold" in s["font"]) or ("Black" in s["font"])
                           or ("CMBX" in s["font"]) for s in ln["spans"])
                raw.append({"page": page.number + 1,
                            "x0": ln["bbox"][0], "x1": ln["bbox"][2],
                            "y0": ln["bbox"][1], "y1": ln["bbox"][3],
                            "txt": txt, "bold": bold,
                            "size": round(max(s["size"] for s in ln["spans"]), 1)})
        if refs_page is not None and page.number + 1 >= refs_page:
            break
        for r in raw:
            if skip.match(r["txt"]) or r["txt"].count(".") >= 4 or r["bold"]:
                continue
            lines.append(r)
    if not lines:
        return []

    mode = max({r["size"] for r in lines}, key=lambda s: sum(1 for r in lines if r["size"] == s))
    lines = [r for r in lines if r["size"] == mode]
    if not lines:
        return []

    starts = sorted({round(r["x0"]) for r in lines})
    column = {s: s for s in starts}
    anchor = starts[0]
    for s in starts:                     # 把相差 < 25bp 的行首并成一栏（段首缩进、悬挂）
        if s - anchor < 25:
            column[s] = anchor
        else:
            anchor = s
            column[s] = anchor
    right = {}
    for r in lines:
        c = column[round(r["x0"])]
        right[c] = max(right.get(c, 0.0), r["x1"])

    out: list[str] = []
    for r in lines:
        c = column[round(r["x0"])]
        width = right[c] - c
        if width <= 0 or r["x1"] >= right[c] - 4:      # 满行：不是段末
            continue
        words = len([t for t in r["txt"].split()
                     if re.search(r"[0-9A-Za-z\u4e00-\u9fff]", t)])
        fill = (r["x1"] - r["x0"]) / width
        if words > max_words and fill >= min_fill:
            continue
        out.append(
            f"p{r['page']} tail: last line holds {words} word(s), {fill:.0%} of the column "
            f"— …{r['txt'][-48:]!r}. hint: shorten the closing sentence so the tail joins the "
            f"line above, or add a clause long enough to fill it; fix the prose, not the spacing "
            f"(parfillskip/rightskip only move the gap)."
        )
    if len(out) > limit:
        out = out[:limit] + [f"…and {len(out) - limit} more short paragraph tails"]
    return out


def _intermediates(dirname: str, basename: str) -> list[str]:
    return [os.path.join(dirname, basename + ext) for ext in _INTERMEDIATE_EXTS]


def has_tectonic() -> bool:
    from shutil import which

    return which("tectonic") is not None
