"""The injected GPU CHECK: make a CPU session fail loudly instead of silently burning an hour.

Only manual-mode pushes need it - a background push reaches Kaggle with
``enable_gpu=true`` and never lands on a CPU box. The injection is best-effort:
a notebook that cannot be rewritten still gets pushed, with a warning.
"""
from __future__ import annotations

import json
import os

from src.notebook.preflight import meta_bool


def inject_gpu_assertion(meta: dict, push_dir: str) -> tuple[dict, bool]:
    """Inject the GPU CHECK cell when authoring ``enable_gpu``; return (meta, enabled).

    The injected text only speaks to the human reading the Kaggle log. Whether an
    API ERROR means "waiting for the human" is decided by the ledger the caller
    writes (``requires_user_gpu``), never by this prose.
    """
    code_path = os.path.join(push_dir, meta.get("code_file", ""))
    required_gpu = meta.get("required_gpu", "T4")
    accelerator = "GPU T4 x2" if required_gpu == "T4" else f"GPU {required_gpu}"
    enable_gpu_authoring = meta_bool(meta.get("enable_gpu", False))

    if os.path.exists(code_path):
        try:
            assert_code = (
                "# === CRITICAL GPU CHECK ===\n"
                "import torch\n"
                "assert torch.cuda.is_available(), (\n"
                "    \"[gpu_check] FAIL cuda=unavailable"
                f" expected={required_gpu}\\n\"\n"
                f"    \"  fix: Settings -> Accelerator -> '{accelerator}'"
                " -> wait for restart -> Run All\"\n"
                ")\n"
                "gpu_name = torch.cuda.get_device_name(0)\n"
                "assert \""
                f"{required_gpu}"
                "\" in gpu_name, (\n"
                "    f\"[gpu_check] FAIL gpu={gpu_name}"
                f" expected={required_gpu}\\n\"\n"
                f"    \"  fix: Settings -> Accelerator -> '{accelerator}' -> Run All\"\n"
                ")\n"
                "print(f\"[gpu_check] ok gpu={gpu_name} n_gpu={torch.cuda.device_count()}\")\n"
                "# ==========================\n"
            )
            if meta.get("kernel_type") == "notebook":
                with open(code_path, encoding="utf-8") as f:
                    notebook = json.load(f)
                has_assert = any(
                    "CRITICAL GPU CHECK" in "".join(cell.get("source", []))
                    for cell in notebook.get("cells", [])
                )
                if enable_gpu_authoring and not has_assert:
                    print(f"[INFO] Auto-injecting GPU assertion cell into {meta.get('code_file')}")
                    notebook.setdefault("cells", []).insert(
                        0,
                        {
                            # nbformat>=5.5 requires every cell to carry an id.
                            "id": "gpu_check",
                            "cell_type": "code",
                            "execution_count": None,
                            "metadata": {},
                            "outputs": [],
                            "source": assert_code.splitlines(keepends=True),
                        },
                    )
                with open(code_path, "w", encoding="utf-8") as f:
                    json.dump(notebook, f, indent=2)
            else:
                with open(code_path, encoding="utf-8") as f:
                    script = f.read()
                if enable_gpu_authoring and "CRITICAL GPU CHECK" not in script:
                    print(f"[INFO] Auto-injecting GPU assertion header into {meta.get('code_file')}")
                    with open(code_path, "w", encoding="utf-8") as f:
                        f.write(assert_code + "\n" + script)
            if enable_gpu_authoring:
                print(
                    "[INFO] Authoring enable_gpu=true -> GPU CHECK injected; "
                    "API push uses transient enable_gpu=false (authoring metadata preserved on disk)."
                )
        except Exception as exc:  # injection is best-effort; the push still matters
            print(f"[WARNING] Failed to auto-inject GPU assertion: {exc}")

    authoring_meta = dict(meta)
    if enable_gpu_authoring:
        authoring_meta["enable_gpu"] = True
    return authoring_meta, enable_gpu_authoring
