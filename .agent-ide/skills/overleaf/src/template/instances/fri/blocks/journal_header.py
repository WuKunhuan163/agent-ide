import os
import shutil

from src.template.block_base import BaseBlock

# Bundled stand-ins shipped beside this block in `instances/fri/assets/`, used
# when the project supplies no custom image. Keeping them on disk is what makes
# this block free of any image-library dependency.
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
FALLBACK_THUMBNAILS = {
    "left": "left_placeholder.png",
    "right": "right_placeholder.png",
}
LEFT_WIDTH_CM = "2.0cm"
RIGHT_WIDTH_CM = "2.0cm"
THUMB_HEIGHT_CM = "3.0cm"
COL_GAP = r"\kern13.5pt"
MIDDLE_WIDTH = r"\dimexpr\linewidth-2.0cm-2.0cm-27pt\relax"


class Block(BaseBlock):
    def _prepare_side_image(self, project_dir, output_dir, field_name, slot):
        assets_out = os.path.join(output_dir, "assets")
        os.makedirs(assets_out, exist_ok=True)
        out_name = f"journal_{slot}_{self.block_id}.png"
        out_path = os.path.join(assets_out, out_name)

        custom = self.content.get(field_name, "")
        custom_path = os.path.join(project_dir, "assets", custom) if custom else ""
        if custom and self.content.get("use_custom_thumbnails", False) and os.path.exists(custom_path):
            try:
                shutil.copy2(custom_path, out_path)
                return out_name
            except OSError:
                pass

        shutil.copy2(os.path.join(ASSETS_DIR, FALLBACK_THUMBNAILS[slot]), out_path)
        return out_name

    def render(self, children_tex=""):
        journal_name = self.content.get("journal_name", "Heliyon")
        citation = self.content.get("citation", "Heliyon 9 (2023) e22478")
        homepage = self.content.get("homepage", "www.cell.com/heliyon")

        project_dir = self.content.get("_project_dir", "")
        output_dir = self.content.get("_output_dir", "")

        logo_file = self._prepare_side_image(project_dir, output_dir, "publisher_logo_path", "left")
        cover_file = self._prepare_side_image(project_dir, output_dir, "cover_path", "right")

        tex = [
            r"\begin{frijournalheader}",
            r"\noindent\begin{minipage}{\textwidth}",
            r"\noindent{\centering\fontsize{7}{8}\selectfont\color{elsevierteal}"
            + citation
            + r"\par\vspace{0pt}}",
            r"\noindent\rule{\linewidth}{0.25pt}\par\vspace{4pt}",
            r"\noindent",
            rf"\begin{{minipage}}[c]{{{LEFT_WIDTH_CM}}}",
            rf"\includegraphics[width={LEFT_WIDTH_CM},keepaspectratio]{{assets/{logo_file}}}",
            r"\end{minipage}%",
            COL_GAP,
            rf"\begin{{minipage}}[c]{{{MIDDLE_WIDTH}}}",
            r"\setlength{\fboxsep}{0pt}",
            r"\colorbox{elseviergray}{%",
            rf"\begin{{minipage}}[t][{THUMB_HEIGHT_CM}][t]{{\linewidth}}",
            r"\centering",
            r"\vspace{2pt}",
            r"{\fontsize{8}{9}\selectfont Contents lists available at \href{https://www.sciencedirect.com/}{\textcolor{elsevierlinkblue}{ScienceDirect}}}\par",
            r"\vfill",
            rf"{{\fontsize{{14}}{{16}}\selectfont {journal_name}}}\par",
            r"\vfill",
            rf"{{\fontsize{{8}}{{9}}\selectfont journal homepage: \href{{https://{homepage}/}}{{\textcolor{{elsevierlinkblue}}{{{homepage}}}}}}}",
            r"\vspace{2pt}",
            r"\end{minipage}}",
            r"\end{minipage}%",
            COL_GAP,
            rf"\begin{{minipage}}[c]{{{RIGHT_WIDTH_CM}}}",
            rf"\includegraphics[width={RIGHT_WIDTH_CM},keepaspectratio]{{assets/{cover_file}}}",
            r"\end{minipage}",
            r"\par\vspace{4pt}",
            r"\noindent\rule{\linewidth}{3pt}",
            r"\end{minipage}",
            r"\vspace{8pt}",
            r"\end{frijournalheader}",
        ]
        return "\n".join(tex)
