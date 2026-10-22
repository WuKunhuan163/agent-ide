"""Identifiers, defined once and low enough in the layering for anyone to use.

Two shapes, for two different jobs:

* a **run id** is what a human types to resume work -- so it is a timestamp plus a
  short random tail: fixed width, no source name, sorts in time order, and does not
  collide when two runs start in the same second;
* a **job id** only ever names a directory and a row in the summary; it carries no
  meaning, so it is just opaque hex.  It is deliberately the same shape everywhere a
  job is created, because two generators would mean two lengths to remember.
"""
from __future__ import annotations

import time
import uuid


def new_run_id() -> str:
    return time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]


def new_job_id() -> str:
    return uuid.uuid4().hex[:8]
