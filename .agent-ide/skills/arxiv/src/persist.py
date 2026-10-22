"""Cache, config, and result snapshot persistence."""
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime

from src.paths import cache_file, data_dir, default_config_file, results_dir

_DEFAULT_CONFIG = {
    "max_results": 5,
    "min_citations": 0,
    "sort_by": "submittedDate",
}


def init_folders() -> None:
    import os

    os.makedirs(data_dir(), exist_ok=True)
    os.makedirs(results_dir(), exist_ok=True)
    cfg = default_config_file()
    if not os.path.exists(cfg):
        try:
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump(_DEFAULT_CONFIG, f, indent=2)
        except OSError:
            pass
    cf = cache_file()
    if not os.path.exists(cf):
        try:
            with open(cf, "w", encoding="utf-8") as f:
                json.dump({"cached_ids": []}, f)
        except OSError:
            pass


def load_default_config() -> dict:
    init_folders()
    try:
        with open(default_config_file(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return dict(_DEFAULT_CONFIG)


def load_cache() -> set[str]:
    init_folders()
    try:
        with open(cache_file(), "r", encoding="utf-8") as f:
            return set(json.load(f).get("cached_ids", []))
    except (OSError, json.JSONDecodeError):
        return set()


def save_cache(cached_set: set[str]) -> None:
    try:
        with open(cache_file(), "w", encoding="utf-8") as f:
            json.dump({"cached_ids": list(cached_set)}, f, indent=2)
    except OSError:
        pass


def save_result_to_json(papers: list[dict]) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rand_hash = hashlib.md5(f"{timestamp}_{random.random()}".encode()).hexdigest()[:8]
    filepath = f"{results_dir()}/{timestamp}_{rand_hash}.json"
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(papers, f, indent=2, ensure_ascii=False)
    except OSError:
        pass
