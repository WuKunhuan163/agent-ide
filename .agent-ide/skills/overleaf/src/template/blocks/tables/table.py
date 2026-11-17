"""A `tabular` inside a float.

Core LaTeX only: the shipped instances load neither `booktabs` nor
`multirow`, so rules are `\\hline` and cells are verbatim LaTeX. Anything a
cell needs beyond that (`\\textbf`, `$\\pm$`, `\\multicolumn`) is written by the
author into the cell string instead of being a content field.

Caption goes above the table, which is the CVPR convention, and `\\label`
follows the caption so `\\ref` resolves to the table number.

宽度：一张表比版心宽时 LaTeX 不会报错，它只是把表画到版心外面去；表头比列宽时
也不会报错，相邻表头直接压在一起。两者都要靠渲染才看得见，所以这里默认兜一层：
`fit: auto`（默认）把表量一遍，只在**超出**版心时按版心等比缩小，不超宽时一个
字节都不改；`fit: none` 输出与旧版完全一致；`fit: scale` 总是缩到版心宽。
`fit: auto` 依赖 `graphicx` 的 `\\resizebox`，实例前言没加载时用 `\\ifdefined`
退回原样输出——宁可不出效果，也不能让编译挂掉。
"""
from __future__ import annotations

from src.store import errors
from src.store.errors import DataError

from src.template.core.block_base import BaseBlock


class Block(BaseBlock):
    _PLACEMENTS = ("h", "t", "b", "p", "H", "!")
    _FITS = ("auto", "scale", "none")

    def validate(self) -> None:
        super().validate()

        rows = self.content.get("rows")
        if not isinstance(rows, list) or not rows:
            raise DataError(
                errors.CONTENT_INVALID,
                None,
                "table block needs a non-empty 'rows' list",
                field="rows",
            )
        for index, row in enumerate(rows):
            if not isinstance(row, list) or not row:
                raise DataError(
                    errors.CONTENT_INVALID,
                    None,
                    f"rows[{index}] must be a non-empty list of cells",
                    field="rows",
                )

        header = self.content.get("header")
        if header is not None and (not isinstance(header, list) or not header):
            raise DataError(
                errors.CONTENT_INVALID,
                None,
                "'header' must be a non-empty list of cells when given",
                field="header",
            )

        midrules = self.content.get("midrules")
        if midrules is not None:
            if not isinstance(midrules, list) or not all(isinstance(n, int) for n in midrules):
                raise DataError(
                    errors.CONTENT_INVALID,
                    None,
                    "'midrules' must be a list of 1-based body row indices",
                    field="midrules",
                )
            if any(n < 1 or n >= len(rows) for n in midrules):
                raise DataError(
                    errors.CONTENT_INVALID,
                    None,
                    "'midrules' index out of range: a rule may only follow a body row but the last",
                    field="midrules",
                )

        placement = str(self.content.get("placement", "t"))
        if placement not in self._PLACEMENTS:
            raise DataError(
                errors.CONTENT_INVALID,
                None,
                f"'placement' must be one of {', '.join(self._PLACEMENTS)}",
                field="placement",
            )

        fit = str(self.content.get("fit", "auto"))
        if fit not in self._FITS:
            raise DataError(
                errors.CONTENT_INVALID,
                None,
                f"'fit' must be one of {', '.join(self._FITS)}",
                field="fit",
            )

        first_width = self.content.get("first_column_width")
        if first_width is not None:
            if not isinstance(first_width, str) or not first_width.strip():
                raise DataError(
                    errors.CONTENT_INVALID,
                    None,
                    "'first_column_width' must be a TeX length such as '0.42\\\\linewidth'",
                    field="first_column_width",
                )
            if "columns" in self.content:
                raise DataError(
                    errors.CONTENT_INVALID,
                    None,
                    "'first_column_width' and 'columns' both set the column spec; keep one",
                    field="first_column_width",
                )

    def _ncols(self) -> int:
        widths = [len(self.content.get("header") or [])]
        widths.extend(len(row) for row in self.content["rows"])
        return max(widths)

    def _row_tex(self, cells: list, ncols: int) -> str:
        # Ragged input is padded rather than rejected: a short row is nearly
        # always a missing trailing cell, and LaTeX would only report the
        # column count at compile time, far from the block that caused it.
        padded = [str(cell) for cell in cells] + [""] * (ncols - len(cells))
        return " & ".join(padded) + r" \\"

    def _tabular(self, ncols: int) -> str:
        columns = self.content.get("columns")
        if not columns:
            first_width = self.content.get("first_column_width")
            if first_width:
                # 行名列改成定宽可折行的列：长行名自己折行，而不是把后面几列挤到一起。
                # 只改第一列，其余列仍取内容自然宽度；需要 `array`（实例前言已加载）。
                columns = (">{\\raggedright\\arraybackslash}p{" + first_width + "}"
                           + "c" * (ncols - 1))
            else:
                # First column left, the rest centred: the shape of a results table.
                columns = "l" + "c" * (ncols - 1)

        header = self.content.get("header")
        midrules = set(self.content.get("midrules") or [])

        lines = [f"\\begin{{tabular}}{{{columns}}}", "\\hline"]
        if header:
            lines.append(self._row_tex(header, ncols))
            lines.append("\\hline")
        for index, row in enumerate(self.content["rows"], start=1):
            lines.append(self._row_tex(row, ncols))
            if index in midrules:
                lines.append("\\hline")
        lines += ["\\hline", "\\end{tabular}"]
        return "\n".join(lines)

    @staticmethod
    def _fit_wrapper(fit: str) -> tuple[str, str]:
        """返回（定义块, 环境名）。定义块把 `ovlfit` 定成"超宽才缩"的环境。

        用 `lrbox` 环境而不是把 tabular 当宏参数传：参数化会让表首的 `\\hline`
        多出半个 `\\arrayrulewidth`，整表因此左移约 1.7bp——装得下的表必须一个像素都不动。
        也因为这句话，量宽度不能用 `\\width`：它只在 `\\includegraphics` 那条路上由
        graphicx 赋值，裹一段 tabular 时取不到。
        """
        if fit == "none":
            return "", ""

        if fit == "scale":
            body = "\n".join([
                r"\ifdefined\resizebox",
                r"  \ifdefined\ovlfitbox\else\newsavebox\ovlfitbox\fi",
                r"  \def\ovlfitprint{\resizebox{\linewidth}{!}{\usebox\ovlfitbox}}",
                r"\else",
                r"  \def\ovlfitprint{}",
                r"\fi",
                r"\ifdefined\ovlfit\else",
                r"  \newenvironment{ovlfit}{\begin{lrbox}{\ovlfitbox}}{\end{lrbox}\ovlfitprint}",
                r"\fi",
            ])
            return body, "ovlfit"

        body = "\n".join([
            r"\ifdefined\resizebox",
            r"  \ifdefined\ovlfitbox\else\newsavebox\ovlfitbox\fi",
            r"  \def\ovlfitprint{\ifdim\wd\ovlfitbox>\linewidth",
            r"    \resizebox{\linewidth}{!}{\usebox\ovlfitbox}\else\usebox\ovlfitbox\fi}",
            r"\else",
            r"  \def\ovlfitprint{\usebox\ovlfitbox}",
            r"  \ifdefined\ovlfitbox\else\newsavebox\ovlfitbox\fi",
            r"\fi",
            r"\ifdefined\ovlfit\else",
            r"  \newenvironment{ovlfit}{\begin{lrbox}{\ovlfitbox}}{\end{lrbox}\ovlfitprint}",
            r"\fi",
        ])
        return body, "ovlfit"

    def render(self, child_contents: str = "") -> str:
        ncols = self._ncols()
        env = "table*" if self.content.get("span_columns", False) else "table"
        placement = str(self.content.get("placement", "t"))
        fit = str(self.content.get("fit", "auto"))

        tabular = self._tabular(ncols)

        lines = [f"\\begin{{{env}}}[{placement}]", "\\begin{center}"]
        caption = self.content.get("caption", "")
        if caption:
            lines.append(f"\\caption{{{caption}}}")
        label = self.content.get("label", "")
        if label:
            lines.append(f"\\label{{{label}}}")

        size = self.content.get("size", "")
        if size:
            lines.append(size)

        preamble, envname = self._fit_wrapper(fit)
        if preamble:
            lines.append(preamble)
            lines.append(f"\\begin{{{envname}}}\n{tabular}\n\\end{{{envname}}}")
        else:
            lines.append(tabular)

        notes = self.content.get("notes", "")
        if notes:
            lines.append("\\vspace{2pt}")
            lines.append(f"{{\\footnotesize {notes}}}")

        lines.append("\\end{center}")
        lines.append(f"\\end{{{env}}}")
        return self.apply_layout("\n".join(lines) + "\n")
