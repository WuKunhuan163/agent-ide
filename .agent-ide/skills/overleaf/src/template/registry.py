"""Instance discovery and block resolution.

The only module in the skill that performs dynamic imports. Resolution order
for a block type:

    1. `instances/<id>/blocks/<type>.py`   (instance-specific override)
    2. the `blocks_*` feature directories, in a fixed order
    3. -> DataError(BLOCK_TYPE_UNKNOWN)

Instance and block modules are loaded by absolute path and must therefore use
absolute package imports (`from src.template... import ...`). The skill root is
already on `sys.path`; instance directories are deliberately not injected.
"""
from __future__ import annotations

import importlib.util
import json
import os

from src.store import errors
from src.store.errors import DataError

from src.template.template_base import BaseTemplate

# Fixed scan order for block groups under `blocks/`; first hit wins.
BLOCK_GROUPS = ("text", "media", "tables", "math", "refs")

_loaded_blocks: dict[tuple[str, str], object] = {}
# Parsed `template.json`, keyed by instance and guarded by the file's mtime, so
# a process that needs the same instance twice (manifest + render) parses once.
_spec_cache: dict[str, tuple[float, dict]] = {}


def template_root() -> str:
    """`<skill>/src/template`."""
    return os.path.dirname(os.path.abspath(__file__))


def instances_root() -> str:
    return os.path.join(template_root(), "instances")


def instance_dir(instance_id: str) -> str:
    return os.path.join(instances_root(), instance_id)


# --------------------------------------------------------------------------- instances


def list_instances() -> list[str]:
    root = instances_root()
    if not os.path.isdir(root):
        return []
    return sorted(
        name
        for name in os.listdir(root)
        if os.path.isfile(os.path.join(root, name, "template.json"))
    )


def load_instance(instance_id: str) -> tuple[dict, BaseTemplate]:
    """Return (spec, template) for an instance id."""
    idir = instance_dir(instance_id)
    if not os.path.isdir(idir):
        raise DataError(errors.TEMPLATE_NOT_FOUND, idir, f"no such instance '{instance_id}'")

    spec = _load_spec(instance_id, idir)

    py_entry = spec.get("python")
    if py_entry:
        template = _load_python_template(idir, py_entry, spec)
    else:
        template = BaseTemplate(idir, spec)
    return spec, template


def _load_spec(instance_id: str, idir: str) -> dict:
    """Parsed `template.json`, cached per instance until the file changes."""
    spec_path = os.path.join(idir, "template.json")
    if not os.path.exists(spec_path):
        raise DataError(errors.TEMPLATE_NOT_FOUND, spec_path, "template.json is missing")

    mtime = os.path.getmtime(spec_path)
    cached = _spec_cache.get(instance_id)
    if cached is not None and cached[0] == mtime:
        return dict(cached[1])

    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            spec = json.load(f)
    except json.JSONDecodeError as exc:
        raise DataError(errors.MALFORMED_FILE, spec_path, f"invalid JSON: {exc}")
    if not isinstance(spec, dict):
        raise DataError(errors.MALFORMED_FILE, spec_path, "template.json must be an object")

    spec.setdefault("name", instance_id)
    spec.setdefault("version", 1)
    _spec_cache[instance_id] = (mtime, spec)
    return dict(spec)


def _load_python_template(idir: str, py_entry: str, spec: dict) -> object:
    path = os.path.join(idir, py_entry)
    if not os.path.exists(path):
        raise DataError(errors.TEMPLATE_NOT_FOUND, path, "declared python entry is missing")
    module = _import_from_path(path, f"overleaf_instance_{os.path.basename(idir)}")
    cls = getattr(module, "Template", None)
    if cls is None:
        raise DataError(errors.MALFORMED_FILE, path, "python entry must define `Template`")
    return cls(idir, spec)


# --------------------------------------------------------------------------- blocks


def resolve_block_class(instance_id: str, block_type: str):
    """Locate and load the `Block` class for a block type."""
    key = (instance_id, block_type)
    if key in _loaded_blocks:
        return _loaded_blocks[key]

    path = _locate_block_file(instance_id, block_type)
    if path is None:
        raise DataError(
            errors.BLOCK_TYPE_UNKNOWN,
            None,
            f"no block plugin '{block_type}.py' for instance '{instance_id}'",
            field="type",
        )

    module = _import_from_path(path, f"overleaf_block_{instance_id}_{block_type}")
    block_cls = getattr(module, "Block", None)
    if block_cls is None:
        raise DataError(errors.MALFORMED_FILE, path, "block plugin must define `Block`")

    _loaded_blocks[key] = block_cls
    return block_cls


def _locate_block_file(instance_id: str, block_type: str) -> str | None:
    filename = f"{block_type}.py"
    override = os.path.join(instance_dir(instance_id), "blocks", filename)
    if os.path.isfile(override):
        return override
    groups_root = os.path.join(template_root(), "blocks")
    for group in BLOCK_GROUPS:
        candidate = os.path.join(groups_root, group, filename)
        if os.path.isfile(candidate):
            return candidate
    return None


def _import_from_path(path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise DataError(errors.MALFORMED_FILE, path, "cannot load module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest_for(instance_id: str) -> dict:
    """Build a store-layer manifest dict from an instance's `template.json`."""
    spec, _ = load_instance(instance_id)
    return {
        "template": spec.get("name", instance_id),
        "version": spec.get("version", 1),
        "required_metadata": spec.get("required_metadata", []),
        "blocks": spec.get("blocks", {}),
    }
