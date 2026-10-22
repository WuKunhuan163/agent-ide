import os
import sys
from src.store import errors
from src.store.errors import DataError

from src.template.block_base import BaseBlock

class Block(BaseBlock):
    def validate(self):
        if "path" not in self.content and "images" not in self.content:
            raise DataError(
                errors.CONTENT_INVALID,
                None,
                "figure block needs 'path' or 'images'",
                field="content",
            )

    def render(self, child_contents: str = "") -> str:
        # Normalize images input: support both legacy 'path', list of strings, and list of dicts.
        raw_images = self.content.get('images', [self.content.get('path')]) if 'images' in self.content or 'path' in self.content else []
        normalized_images = []
        for img in raw_images:
            if isinstance(img, str):
                normalized_images.append({'path': img})
            elif isinstance(img, dict):
                normalized_images.append(img)

        caption = self.content.get('caption', '')
        label = self.content.get('label', '')
        global_width = str(self.content.get('width', '1.0'))
        span_cols = self.content.get('span_columns', False)
        caption_margin_top = self.content.get('caption_margin_top', '')
        placement = self.content.get('placement', 't')
        is_teaser = self.content.get('is_teaser', False)
        
        # Determine grid layout parameters
        columns = int(self.content.get('columns', len(normalized_images) if normalized_images else 1))
        use_subfigures = self.content.get('use_subfigures', len(normalized_images) > 1)
        
        # Resolve and copy to export/assets
        import os
        import shutil
        actual_path_base = self.content.get('_output_dir', os.getcwd())
        project_dir = self.content.get('_project_dir', actual_path_base)
        input_dir = os.path.join(project_dir, "input")
        assets_dir = os.path.join(actual_path_base, "assets")
        os.makedirs(assets_dir, exist_ok=True)
        
        env = "figure*" if span_cols else "figure"
        if is_teaser:
            tex = f"\\begin{{cvprteaser}}\n"
            tex += f"\\begin{{center}}\n"
            # caption/label will be added at the end
        else:
            tex = f"\\begin{{{env}}}[{placement}]\n\\begin{{center}}\n"
        
        for i, img_obj in enumerate(normalized_images):
            path = img_obj.get('path', '')
            actual_path = os.path.normpath(os.path.join(actual_path_base, path))
            if not os.path.exists(actual_path) and os.path.exists(os.path.join(input_dir, path)):
                actual_path = os.path.join(input_dir, path)
                
            tex_path = path
            if os.path.exists(actual_path):
                img_name = os.path.basename(actual_path)
                safe_name = f"{self.block_id}_{i}_{img_name}"
                dst = os.path.join(assets_dir, safe_name)
                shutil.copy2(actual_path, dst)
                tex_path = f"assets/{safe_name}"
                
            # Process width
            item_width = str(img_obj.get('width', global_width))
            has_unit = any(unit in item_width for unit in ['\\linewidth', '\\textwidth', '\\columnwidth', 'px', 'cm', 'in', 'pt', 'em', 'ex'])
            
            if use_subfigures:
                # If using subfigures, the subfigure block itself needs a width (typically 1/columns of the line width)
                # We default to equally splitting the line width minus a tiny margin
                subfig_width_default = f"{1.0/columns - 0.02:.3f}\\linewidth"
                subfig_width = img_obj.get('sub_width', subfig_width_default)
                
                # Image inside the subfigure defaults to \linewidth unless explicitly overridden with a unit
                img_width_str = item_width if has_unit else f"{item_width}\\linewidth"
                
                tex += f"   \\begin{{subfigure}}[b]{{{subfig_width}}}\n"
                tex += f"       \\centering\n"
                tex += f"       \\includegraphics[width={img_width_str}]{{{tex_path}}}\n"
                if 'caption' in img_obj:
                    tex += f"       \\caption{{{img_obj['caption']}}}\n"
                if 'label' in img_obj:
                    tex += f"       \\label{{{img_obj['label']}}}\n"
                tex += f"   \\end{{subfigure}}"
            else:
                # Legacy simple layout
                if len(normalized_images) > 1 and not has_unit:
                    eff_width = float(item_width) / len(normalized_images) - 0.02
                    img_width_str = f"{eff_width:.2f}\\linewidth"
                else:
                    img_width_str = item_width if has_unit else f"{item_width}\\linewidth"
                    
                tex += f"   \\includegraphics[width={img_width_str}]{{{tex_path}}}"
                
            # Layout formatting: newlines and hfills
            if i < len(normalized_images) - 1:
                if (i + 1) % columns == 0:
                    tex += "\\\\[0.5em]\n" # Start a new row
                else:
                    tex += "\\hfill\n"
            else:
                tex += "\n"
            
        tex += f"\\end{{center}}\n"
        if is_teaser:
            if caption_margin_top:
                tex += f"   \\vspace{{{caption_margin_top}}}\n"
            if caption:
                tex += f"   \\captionof{{figure}}{{{caption}}}\n"
            if label:
                tex += f"   \\label{{{label}}}\n"
            tex += f"\\vspace{{2em}}\n"
            tex += f"\\end{{cvprteaser}}"
            return tex
            
        if caption_margin_top:
            tex += f"   \\vspace{{{caption_margin_top}}}\n"
        if caption:
            tex += f"   \\caption{{{caption}}}\n"
        if label:
            tex += f"   \\label{{{label}}}\n"
            
        tex += f"\\end{{{env}}}"
        return tex
