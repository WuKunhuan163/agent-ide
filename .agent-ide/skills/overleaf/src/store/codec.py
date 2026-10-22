"""Strict parse/serialize for `project.json` and `block.json`.

Owns the exact on-disk field set. No extra keys, no defaults for required
fields, no inference. This is the only place JSON is read or written.
"""
from __future__ import annotations

import json
import os

from src.store import errors
from src.store.errors import DataError
from src.store.model import SCHEMA_VERSION

_PROJECT_KEYS = ("schema", "template", "template_version", "metadata")
_BLOCK_KEYS = ("schema", "type", "order", "display", "content")


def _read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise DataError(errors.BLOCK_NOT_FOUND, path, "file does not exist")
    except json.JSONDecodeError as exc:
        raise DataError(errors.MALFORMED_FILE, path, f"invalid JSON: {exc}")
    if not isinstance(data, dict):
        raise DataError(errors.MALFORMED_FILE, path, "top level must be an object")
    return data


def _require_schema(data: dict, path: str) -> None:
    schema = data.get("schema")
    if schema != SCHEMA_VERSION:
        raise DataError(
            errors.SCHEMA_UNSUPPORTED,
            path,
            f"expected schema {SCHEMA_VERSION}, got {schema!r}",
            field="schema",
        )


def _reject_unknown(data: dict, allowed: tuple[str, ...], path: str) -> None:
    extra = [k for k in data if k not in allowed]
    if extra:
        raise DataError(
            errors.MALFORMED_FILE, path, f"unknown keys: {', '.join(sorted(extra))}"
        )


# --------------------------------------------------------------------------- project


def load_project_json(path: str) -> dict:
    _path = path
    if not os.path.exists(_path):
        raise DataError(errors.PROJECT_NOT_FOUND, _path, "project.json does not exist")
    data = _read_json(_path)
    _require_schema(data, _path)
    _reject_unknown(data, _PROJECT_KEYS, _path)

    template = data.get("template")
    if not isinstance(template, str) or not template.strip():
        raise DataError(
            errors.MALFORMED_FILE, _path, "template must be a non-empty string", field="template"
        )
    version = data.get("template_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise DataError(
            errors.MALFORMED_FILE,
            _path,
            "template_version must be a positive integer",
            field="template_version",
        )
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        raise DataError(
            errors.MALFORMED_FILE, _path, "metadata must be an object", field="metadata"
        )
    return {
        "schema": SCHEMA_VERSION,
        "template": template.strip(),
        "template_version": version,
        "metadata": metadata,
    }


def dump_project_json(path: str, data: dict) -> None:
    payload = {
        "schema": SCHEMA_VERSION,
        "template": data["template"],
        "template_version": data["template_version"],
        "metadata": data["metadata"],
    }
    _write_json(path, payload)


# --------------------------------------------------------------------------- block


def load_block_json(path: str) -> dict:
    _path = path
    if not os.path.exists(_path):
        raise DataError(errors.BLOCK_NOT_FOUND, _path, "block.json does not exist")
    data = _read_json(_path)
    _require_schema(data, _path)
    _reject_unknown(data, _BLOCK_KEYS, _path)

    btype = data.get("type")
    if not isinstance(btype, str) or not btype.strip():
        raise DataError(
            errors.MALFORMED_FILE, _path, "type must be a non-empty string", field="type"
        )
    order = data.get("order")
    if not _is_int(order):
        raise DataError(errors.MALFORMED_FILE, _path, "order must be an integer", field="order")
    display = data.get("display")
    if not isinstance(display, bool):
        raise DataError(errors.MALFORMED_FILE, _path, "display must be a boolean", field="display")
    content = data.get("content")
    if not isinstance(content, dict):
        raise DataError(
            errors.MALFORMED_FILE, _path, "content must be an object", field="content"
        )
    return {
        "schema": SCHEMA_VERSION,
        "type": btype.strip(),
        "order": order,
        "display": display,
        "content": content,
    }


def dump_block_json(path: str, data: dict) -> None:
    payload = {
        "schema": SCHEMA_VERSION,
        "type": data["type"],
        "order": data["order"],
        "display": bool(data["display"]),
        "content": data["content"],
    }
    _write_json(path, payload)


# --------------------------------------------------------------------------- helpers


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _write_json(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
