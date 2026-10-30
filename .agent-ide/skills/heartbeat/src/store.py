"""状态存放：配置、待办、日志全部落在本技能自己的 data/ 下，绝不进项目目录。

为什么强调这一点——上一版把待办写在 <project>/.codebuddy/lobster/tasks.json，
同一个项目里的另一个会话（另一个 agent）能读到它，于是「一个会话的心跳」
变成了「整个项目的心跳」。数据放哪，决定了作用域有多大；作用域要等于会话，
数据就必须离开项目目录。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
DATA = PKG / "data"
CONFIG = DATA / "config.json"
LOG = DATA / "heartbeat.log"
SEEN = DATA / "sessions.json"
TASKS = DATA / "tasks"

DEFAULT_CONFIG = {
    "enabled": False,
    # 允许名单：非空时只有这些会话会心跳；空表示不限（但仍要命中 bindings）。
    "sessions": [],
    "exclude": [],
    # binding = {session: <会话 id>, tasks: <工作根目录>}，session 是唯一身份。
    # 没有按目录绑这一说：一个项目常有多个会话，按目录绑会把同项目的其它 agent
    # 一起拦，那是上一版真实的污染方式。
    "bindings": [],
    # 一条链（一段无人值守的连续推进）里最多推多少次。
    "max_nudge_per_chain": 200,
    # 距上一次推送超过这个间隔，视为新链、计数归零。
    "chain_gap_seconds": 1800,
    # 同一项连续多少次推送都没换来产物增长，就自动 block 换下一项。
    "stall_limit": 6,
    # 待办超过这么多小时没有新产物就不再拦。
    # 注意是按「最后一次推进」（last_progress_at）算，不是按「最后一次推送」——
    # 按推送算的话，只要它还在推就永远不会过期，这道闸等于没有。
    "max_age_hours": 24,
    # 推送前跑的一条外部命令（可选）：stdout 非空就把它附在提示里。
    # 上一版这里写死了「查 GPU 是否在计费」，那属于某个项目的耦合，不该进通用工具。
    "pre_nudge_check": "",
}


def config() -> dict:
    if CONFIG.exists():
        try:
            return {**DEFAULT_CONFIG, **json.loads(CONFIG.read_text())}
        except ValueError:
            return dict(DEFAULT_CONFIG)
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")


def log(line: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%m-%d %H:%M:%S')} {line}\n")


def match_binding(cfg: dict, session: str = "") -> dict | None:
    """会话 → 命中的 binding。只认 session 精确相等，别的路径一律不命中。

    返回 None 意味着「这不是我的会话」，调用方必须完全静默：不打印、不写日志。

    为什么连「按目录」都不留：同一个项目里通常同时开着几个会话（不同任务、不同
    agent），它们的 cwd 完全相同。按目录匹配等于「一个会话开心跳，全项目被拦」，
    这正是上一版的污染方式。cwd 在这个判断里没有任何信息量——它只能说明大家
    在同一个仓库里，不能说明谁该被派活。
    """
    for b in cfg.get("bindings") or []:
        if b.get("session") and session and session == b["session"]:
            return b
    return None


def store_key(binding: dict | None) -> str:
    """待办文件名。按会话隔离，同一个项目里的不同会话各有各的文件。"""
    b = binding or {}
    if b.get("store"):
        return str(b["store"])
    return "s-" + str(b.get("session") or "unbound")[:16]


def tasks_path(binding: dict | None) -> Path:
    return TASKS / f"{store_key(binding)}.json"


def work_root(binding: dict | None) -> Path:
    return Path((binding or {}).get("tasks") or ".").expanduser()


def load_tasks(binding: dict | None) -> dict:
    p = tasks_path(binding)
    if not p.exists():
        return {"tasks": []}
    try:
        return json.loads(p.read_text())
    except ValueError:
        return {"tasks": []}


def save_tasks(binding: dict | None, data: dict) -> None:
    p = tasks_path(binding)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def remember_session(session: str, cwd: Path) -> None:
    """记住见过的会话，这样 `bind --session` 才有 id 可选。

    这是唯一在「未命中」路径上发生的写操作，且只写一次 per 会话；
    除此之外未命中的路径什么都不做。
    """
    if not session:
        return
    try:
        seen = json.loads(SEEN.read_text()) if SEEN.exists() else {}
    except ValueError:
        seen = {}
    if seen.get(session, {}).get("cwd") == str(cwd):
        return
    seen[session] = {"cwd": str(cwd), "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(seen, ensure_ascii=False, indent=2) + "\n")


def seen_sessions() -> dict:
    try:
        return json.loads(SEEN.read_text()) if SEEN.exists() else {}
    except ValueError:
        return {}
