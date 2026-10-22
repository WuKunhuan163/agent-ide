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


def _intermediates(dirname: str, basename: str) -> list[str]:
    return [os.path.join(dirname, basename + ext) for ext in _INTERMEDIATE_EXTS]


def has_tectonic() -> bool:
    from shutil import which

    return which("tectonic") is not None
