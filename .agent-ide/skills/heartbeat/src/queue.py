"""待办队列：状态机 + 产物计数。

核心约束：进度不由调用方断言，而是从产物文件里数出来。
「记得要记账」和「真的做了」因此变成同一件事——没有新产物就没有新进度。
"""
from __future__ import annotations

import re
import time
from pathlib import Path

DEFAULT_PATTERN = r"^\|\s*\d+\s*\|"
STATUSES = ("todo", "doing", "done", "blocked")


def pending(data: dict) -> list[dict]:
    """待推进的项：doing 优先（手上的做完），其余按登记顺序。blocked/done 不出现。"""
    items = [t for t in data.get("tasks", [])
             if (t.get("status") or "todo") in ("todo", "doing")]
    return sorted(items, key=lambda t: 0 if t.get("status") == "doing" else 1)


def find(data: dict, tid: str) -> dict | None:
    for t in data.get("tasks", []):
        if t.get("id") == tid:
            return t
    return None


def check_pattern(pattern: str | None) -> str | None:
    """校验正则，合法返回 None，否则返回一句人话。

    没有这道校验时，坏正则能一路进库：`inc` 直接抛 traceback，钩子那侧则把它当成
    「匹配到 0 行」，于是空转计数一路涨上去，最后把任务自动 block 掉——
    一个笔误被解释成「模型一直在空转」。
    """
    if not pattern:
        return None
    try:
        re.compile(pattern, re.M)
    except re.error as exc:
        return f"evidence_pattern 不是合法正则：{pattern!r}（{exc}）"
    return None


def evidence_lines(task: dict, root: Path) -> int | None:
    """数产物文件里「算数」的行。

    返回 None = 无法核对（没有 evidence，或正则坏了）。两种都必须让调用方
    跳过 stall 判定，不能当成「0 行产物」——否则配置错误会伪装成空转。
    """
    ev = task.get("evidence")
    if not ev:
        return None
    path = Path(ev)
    if not path.is_absolute():
        path = Path(root) / path
    if not path.exists():
        return 0
    pattern = task.get("evidence_pattern") or DEFAULT_PATTERN
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    if check_pattern(pattern):
        return None
    return len(re.findall(pattern, text, flags=re.M))


def add(data: dict, text: str, root: Path | None = None, **opts) -> dict:
    """登记一项。done 的起点是产物**当前**已有的行数，不是 0。

    为什么必须这样：产物文件通常不是空的（上一件刚往里写了几行）。从 0 起算的话，
    登记完第一次 `inc` 不需要写任何东西就能把 done 从 0 跳到已有行数——白拿一段
    进度，正好绕过「没有新产物就不许记账」这道闸。起点必须先对上现有产物。
    """
    tasks = data.setdefault("tasks", [])
    item = {"id": f"t{len(tasks) + 1}", "text": text, "status": "todo"}
    item.update({k: v for k, v in opts.items() if v is not None})
    if root is not None and item.get("evidence"):
        item["done"] = evidence_lines(item, root) or 0
    tasks.append(item)
    now = time.time()
    data.setdefault("created_at", now)
    data["last_progress_at"] = now      # 刚登记就算一次推进，别一上手就被判成过期
    return item


def bump(task: dict, root: Path) -> tuple[bool, str]:
    """记一次进度。返回 (是否成功, 说明)。

    有 evidence 的项：只有产物行数严格增长才接受，否则拒绝——这是防谎报的唯一硬闸。
    没有 evidence 的项：退化为计数，但 stall 判不出进展，只能靠 max_age/链上限兜底。
    """
    ev = task.get("evidence")
    total = int(task.get("total") or 0)
    if not ev:
        task["done"] = int(task.get("done") or 0) + 1
    else:
        path = Path(ev)
        if not path.is_absolute():
            path = Path(root) / path
        if not path.exists():
            return False, f"产物文件不存在：{path}"
        pattern = task.get("evidence_pattern") or DEFAULT_PATTERN
        bad = check_pattern(pattern)
        if bad:
            return False, bad
        found = len(re.findall(pattern, path.read_text(encoding="utf-8", errors="replace"), flags=re.M))
        prev = int(task.get("done") or 0)
        if found <= prev:
            return False, (f"{path.name} 里没有新增登记（{found} 行，进度仍是 {prev}）"
                           f"——先把这一件做出来再记账")
        task["done"] = found
    task["_stall"] = 0
    if total and int(task["done"]) >= total:
        task["status"] = "done"
    return True, f"{task['id']} {task['done']}/{total or '?'}"


def sync(task: dict, root: Path) -> str:
    """把 done 拉回产物文件里的真实行数：多记的在这里被纠正。"""
    ev = task.get("evidence")
    if not ev:
        return "这一项没有产物，无法对齐"
    bad = check_pattern(task.get("evidence_pattern"))
    if bad:
        return bad
    found = evidence_lines(task, root) or 0
    old = task.get("done") or 0
    task["done"] = found
    return f"{old} -> {found}"


def set_status(task: dict, status: str, note: str = "") -> None:
    if status not in STATUSES:
        return
    task["status"] = status
    if note:
        task["blocked_reason" if status == "blocked" else "note"] = note
    if status != "blocked":
        task.pop("blocked_reason", None)
    if status in ("done", "todo"):
        task["_stall"] = 0
