"""A `tabular` inside a float.

Core LaTeX only: the shipped instances load neither `booktabs` nor
`multirow`, so rules are `\\hline` and cells are verbatim LaTeX. Anything a
cell needs beyond that (`\\textbf`, `$\\pm$`, `\\multicolumn`) is written by the
author into the cell string instead of being a content field.

Caption goes above the table, which is the CVPR convention, and `\\label`
follows the caption so `\\ref` resolves to the table number.
"""
from __future__ import annotations

from src.store import errors
from src.store.errors import DataError

from src.template.block_base import BaseBlock


class Block(BaseBlock):
    _PLACEMENTS = ("h", "t", "b", "p", "H", "!")

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

    def render(self, child_contents: str = "") -> str:
        ncols = self._ncols()
        # First column left, the rest centred: the shape of a results table.
        columns = self.content.get("columns") or ("l" + "c" * (ncols - 1))
        env = "table*" if self.content.get("span_columns", False) else "table"
        placement = str(self.content.get("placement", "t"))
        header = self.content.get("header")
        midrules = set(self.content.get("midrules") or [])

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

        lines.append(f"\\begin{{tabular}}{{{columns}}}")
        lines.append("\\hline")
        if header:
            lines.append(self._row_tex(header, ncols))
            lines.append("\\hline")
        for index, row in enumerate(self.content["rows"], start=1):
            lines.append(self._row_tex(row, ncols))
            if index in midrules:
                lines.append("\\hline")
        lines.append("\\hline")
        lines.append("\\end{tabular}")

        notes = self.content.get("notes", "")
        if notes:
            lines.append("\\vspace{2pt}")
            lines.append(f"{{\\footnotesize {notes}}}")

        lines.append("\\end{center}")
        lines.append(f"\\end{{{env}}}")
        return self.apply_layout("\n".join(lines) + "\n")
