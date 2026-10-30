"""钩子处理体：在「本来就要停下来」的那一刻，把队列里的一件推回去。

为什么用 Stop 而不是定时器：定时心跳即使没活也要调一次模型；Stop 钩子只在
本轮自然结束的时刻判断，没待办就什么都不做，没有额外成本。这是同一个机制
（主会话里的一个轮次，带完整上下文），只是触发点换了。

一条铁律贯穿全文件：**推送权只在这里**。agent 没有任何命令能让它「现在就推
一件」——它只能记账。所以「自己给自己派活」在接口上不存在。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import queue, store


def message(task: dict, remaining: int, extra: str = "") -> str:
    """喂回给模型的话：派哪一件、做成什么样算完、怎么销账、做完就停。"""
    hint = str(task.get("hint") or "").strip()
    if hint:
        # 匿名模式：不报 id、不报进度。该做哪一件由产物文件自己决定——
        # 报编号会让人按编号去凑，而不是回头去看已经写了什么。
        lines = [f"[heartbeat] {hint}"]
    else:
        total = int(task.get("total") or 0)
        done = int(task.get("done") or 0)
        head = (f"[heartbeat] {task.get('id')} 进度 {done}/{total}，还剩 {total - done} 次。"
                if total else f"[heartbeat] 待办未清（还剩 {remaining} 项）。")
        lines = [head, f"这一次只派 1 件：{task.get('id')} — {task.get('text')}"]

    if task.get("judge"):
        lines.append(f"判据（做成什么样算完）：{task['judge']}")
    if task.get("evidence"):
        pat = task.get("evidence_pattern") or queue.DEFAULT_PATTERN
        lines.append(f"产物：{task['evidence']}（记账时数其中匹配 {pat} 的行）")

    arg = "" if hint else f" {task.get('id')}"      # 匿名模式下不给 id，inc 自动取当前件
    lines.append(
        f"做完执行一次 `heartbeat.py inc{arg}`，然后立刻结束这一轮。"
        f"没有新产物它 refuse；做不成用 `heartbeat.py block{arg} \"卡在哪\"`，不要谎报完成。"
    )
    lines.append("不要在同一轮里接着做第 2 件。下一次派活由钩子在你停下时发出，"
                 "不由你发起——你也没有能主动触发它的命令。")
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def _pre_check(cfg: dict, root: Path) -> str:
    cmd = str(cfg.get("pre_nudge_check") or "").strip()
    if not cmd:
        return ""
    try:
        out = subprocess.run(cmd, shell=True, cwd=str(root), capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _target(payload: dict) -> tuple[str, dict, dict, dict] | None:
    """统一的会话解析：该不该管这个会话、它绑在哪、队列是什么。

    两个挂载点共用这一段，避免各写一遍前置判断而慢慢长出两套规则。
    未命中一律返回 None，调用方必须完全静默：不输出、不写日志——否则别的会话
    每收尾一次就往日志里塞一行，真正的信号会被淹掉。
    """
    cfg = store.config()
    if not cfg.get("enabled"):
        return None
    session = str(payload.get("session_id") or "")
    if session and session in (cfg.get("exclude") or []):
        return None
    allow = cfg.get("sessions") or []
    if allow and session not in allow:
        return None
    binding = store.match_binding(cfg, session)
    if binding is None:
        return None
    return session, cfg, binding, store.load_tasks(binding)


def handle(payload: dict) -> dict | None:
    """只在主会话的 Stop 上工作；返回要输出的 JSON（要拦），或 None（不拦、不吭声）。

    为什么拒绝 SubagentStop：子代理与父会话共用同一个 session_id，payload 里没有
    任何字段能把它们分开。一旦接受 SubagentStop，父会话派出去的子代理（跑下载、
    跑构建这类长任务）一收尾就会被当成「主会话停了」，于是被塞进一条完全无关的
    待办。session 绑定在这种场景下失效——不是匹配写错了，而是 session 本身粒度
    不够。宁可少一个挂载点，也不能把活派给正在干别的事的 agent。
    """
    if (payload.get("hook_event_name") or "Stop") != "Stop":
        return None
    store.remember_session(str(payload.get("session_id") or ""),
                           Path(payload.get("cwd") or os.getcwd()))

    target = _target(payload)
    if target is None:
        return None
    session, cfg, binding, data = target

    todo = queue.pending(data)
    if not todo:
        store.log(f"idle session={session[:8]}")
        return None

    now = time.time()
    root = store.work_root(binding)

    # 闸一：太久没有新产物就不再拦。
    # 按「最后一次推进」算，不按「最后一次推送」——后者每次推送都会刷新，
    # 只要它还在推就永远不过期，那道闸等于不存在。
    last_progress = float(data.get("last_progress_at") or data.get("created_at") or now)
    age_h = (now - last_progress) / 3600
    if age_h > float(cfg.get("max_age_hours") or 24):
        store.log(f"stale {age_h:.1f}h pending={len(todo)}")
        return None

    # 闸二：一条链最多推多少次。隔得够久就算新链、计数归零。
    chain = data.get("_chain") or {}
    fresh_chain = (now - float(chain.get("at") or 0)) > float(cfg.get("chain_gap_seconds") or 1800)
    chain_count = 0 if fresh_chain else int(chain.get("count") or 0)
    limit = int(cfg.get("max_nudge_per_chain") or 200)
    if chain_count >= limit:
        store.log(f"giveup chain={chain_count}/{limit} pending={len(todo)}")
        return None

    # 闸三：同一件连着推却没产物，就累加 stall；到顶换下一件。
    # 「有没有进展」只有一个判据：上一次推送时记下的行数，和现在比。
    first = todo[0]
    cur = queue.evidence_lines(first, root)
    last = data.get("_last_nudge") or {}
    no_progress = (last.get("task") == first.get("id")
                   and cur is not None
                   and cur <= int(last.get("lines") or -1))
    first["_stall"] = int(first.get("_stall") or 0) + 1 if no_progress else 0

    if int(first["_stall"]) >= int(cfg.get("stall_limit") or 6):
        first["status"] = "blocked"
        first["blocked_reason"] = f"连续 {first['_stall']} 次推送后产物仍是 {cur} 行，自动 block"
        store.log(f"autoblock task={first.get('id')} stall={first['_stall']} lines={cur}")
        store.save_tasks(binding, data)
        rest = queue.pending(data)
        if not rest:
            return None
        first = rest[0]
        first["_stall"] = 0
        cur = queue.evidence_lines(first, root)

    if (first.get("status") or "todo") == "todo":
        first["status"] = "doing"
    data["_chain"] = {"at": now, "count": chain_count + 1}
    data["_last_nudge"] = {"at": now, "task": first.get("id"),
                           "lines": cur if cur is not None else -1}
    store.save_tasks(binding, data)

    store.log(f"nudge session={session[:8]} chain={chain_count + 1}/{limit} "
              f"task={first.get('id')} pending={len(todo)}")
    return {"continue": False, "stopReason": message(first, len(todo), _pre_check(cfg, root))}


def dump(payload: dict) -> int:
    """把钩子拿到的 payload 打出来，用于确认上游到底传了什么。"""
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def read_payload() -> dict:
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        return json.loads(raw) if raw.strip() else {}
    except ValueError:
        return {}
