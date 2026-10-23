import logging
import os
import shutil
import struct

from src.store import errors
from src.store.errors import DataError

from src.template.block_base import BaseBlock

logger = logging.getLogger("teaser")
SPACING_RATIO = 0.02
FALLBACK_WIDTH_RATIO = 0.98


def _image_aspect_ratio(path: str) -> float:
    """Width/height of a PNG, JPEG or GIF, decoded with the stdlib only.

    Replaces the previous `python3 -c "import PIL..."` subprocess, which made
    image sizing silently depend on the host interpreter shipping Pillow.
    """
    with open(path, "rb") as fh:
        head = fh.read(26)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            width, height = struct.unpack(">II", head[16:24])
            return width / height
        if head[:3] == b"GIF":
            width, height = struct.unpack("<HH", head[6:10])
            return width / height
        if head[:2] == b"\xff\xd8":
            fh.seek(2)
            while True:
                marker = fh.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    break
                (length,) = struct.unpack(">H", fh.read(2))
                if 0xC0 <= marker[1] <= 0xCF and marker[1] not in (0xC4, 0xC8, 0xCC):
                    fh.read(1)
                    height, width = struct.unpack(">HH", fh.read(4))
                    return width / height
                fh.seek(length - 2, 1)
    raise ValueError("unsupported or corrupt image")


class Block(BaseBlock):
    def validate(self):
        if "path" not in self.content and "paths" not in self.content:
            raise DataError(
                errors.CONTENT_INVALID,
                None,
                "cvpr teaser block needs 'path' or 'paths'",
                field="content",
            )

    def render(self, child_contents: str = "") -> str:
        paths = self.content.get('paths', [])
        if not paths:
            paths = [self.content.get('path')]
            
        caption = self.content.get('caption', 'CVPR Teaser Image')
        tex = f"\\begin{{cvprteaser}}\n"
        tex += f"\\begin{{center}}\n"
        
        if len(paths) >= 1:
            try:
                actual_path_base = self.content.get('_output_dir') or self.content.get('_project_dir')
                assets_dir = os.path.join(actual_path_base, "assets")
                os.makedirs(assets_dir, exist_ok=True)

                aspect_ratios = []
                final_paths = []
                for i, p in enumerate(paths):
                    actual_path = os.path.normpath(os.path.join(actual_path_base, p))
                    if os.path.exists(actual_path):
                        # Copy to export/assets/
                        img_name = os.path.basename(actual_path)
                        safe_name = f"{self.block_id}_{img_name}"
                        dst = os.path.join(assets_dir, safe_name)
                        shutil.copy2(actual_path, dst)
                        final_paths.append(f"assets/{safe_name}")
                        
                        try:
                            aspect_ratios.append(_image_aspect_ratio(actual_path))
                        except (OSError, struct.error, ValueError) as exc:
                            logger.warning("cannot size %s: %s", actual_path, exc)
                            aspect_ratios.append(1.0)
                    else:
                        final_paths.append(p)
                        aspect_ratios.append(1.0)
                
                total_ratio = sum(aspect_ratios)
                for i, p in enumerate(final_paths):
                    available_width = 1.0 - SPACING_RATIO
                    relative_width = (aspect_ratios[i] / total_ratio) * available_width
                    if len(paths) == 1:
                        tex += f"   \\includegraphics[width=1.0\\textwidth]{{{p}}}\n"
                    else:
                        tex += f"   \\includegraphics[width={relative_width:.3f}\\textwidth]{{{p}}}"
                        if i < len(final_paths) - 1:
                            tex += "\\hfill\n"
                        else:
                            tex += "\n"
            except Exception as e:
                logger.error(f"Exception in teaser aspect ratio: {e}")
                # Fallback if PIL is not available
                width_ratio = FALLBACK_WIDTH_RATIO / len(paths)
                for i, p in enumerate(paths):
                    if len(paths) == 1:
                        tex += f"   \\includegraphics[width=1.0\\textwidth]{{{p}}}\n"
                    else:
                        tex += f"   \\includegraphics[width={width_ratio:.3f}\\textwidth]{{{p}}}"
                        if i < len(paths) - 1:
                            tex += "\\hfill\n"
                        else:
                            tex += "\n"
            
        tex += f"   \\captionof{{figure}}{{ {caption} }}\n"
        label = self.content.get('label', '')
        if label:
            tex += f"   \\label{{{label}}}\n"
        tex += f"\\end{{center}}\n"
        tex += f"\\end{{cvprteaser}}\n"
        return tex
