#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""heartbeat —— 待办没清时不许收工：把队列里的一件推回主会话。

机制（OpenClaw 的 Heartbeat 在 CodeBuddy 里的等价物）：
  主会话本来要结束时，IDE 会跑 Stop 钩子。钩子输出
  {"continue": false, "stopReason": "..."} 就是一次「心跳轮次」——stopReason
  作为新的用户消息进入同一个会话，带完整上下文，不新建后台任务。
  没有待办就什么都不输出，零打扰。

与定时心跳的差别只在触发点：OpenClaw 由 cron 定时唤醒，这里由「本来就要停」
这个事件唤醒。省掉的是空转的 tick，保留的是同一个语义。

一条铁律：**推送权只在钩子里**。agent 没有任何命令能让它立刻推一件——
它只能记账（inc / done / block）。「自己给自己派活」在接口上不存在。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import hook, queue, store  # noqa: E402

PKG = store.PKG

USAGE = f"""heartbeat —— 待办没清时不许收工

  heartbeat.py                        Stop 钩子入口（读 stdin 的 JSON）
  heartbeat.py payload                打印钩子拿到的 payload（调试用）

  install [--scope user|project] [--loop-limit N]
                                      装 Stop 钩子（幂等；loop_limit = 每轮最多连推几次）
  uninstall [--scope user|project]    卸载本工具装的钩子（只删自己那条）
  on [--session <id>]                 启用；带 --session 则只对该会话生效
  off                                 停用（钩子立即静默）
  bind --session <id> --work <dir>    把会话绑到一份工作目录（待办存本技能 data/）
  unbind <session>                    解除绑定

  （任何命令都可以加 --as <session-id> 声明调用者身份，等价于设 HEARTBEAT_SESSION）

  add "<text>" [--judge "..."] [--evidence <path>] [--pattern <re>] [--total N]
  inc <id>                            记一次进度（数产物行数，没增长就拒绝）
  sync <id>                           把进度拉回产物文件的真实行数
  done|doing|todo <id> [note]
  block <id> "<卡在哪>"
  rm <id>                             从队列删掉（blocked 的也没必要永远挂着）
  set <id> ["<text>"] [--total N] [--evidence p] [--pattern re] [--judge s]
  list | sessions | exclude <id>... | doctor

待办存在本技能 data/tasks/<key>.json，不进项目目录：
一个项目常有多个会话，数据放项目里就会被同项目的其它 agent 读到。
"""


def _fail(code: int, msg: str) -> int:
    print(msg, file=sys.stderr)
    return code


def _cli_binding(cfg: dict, here: Path) -> dict | None:
    """命令行没有身份可言：任何进程都能跑它。所以这里不做任何猜测。

    必须显式给 HEARTBEAT_SESSION，且必须精确等于某个 binding 的 session。

    上一版第③级留了个回退——「只有一个 session 型 binding，且它的工作目录包含
    当前目录，就用它」。看着很方便，实际是个洞：同一个项目里的另一个 agent 敲一条
    `heartbeat.py block t1 "..."` 就会命中这条回退，直接改掉别人的待办。
    已经真实发生过一次。宁可让它报错，也不要让它猜。
    """
    session = os.environ.get("HEARTBEAT_SESSION") or ""
    if not session:
        return None
    for b in cfg.get("bindings") or []:
        if b.get("session") and b["session"] == session:
            return b
    return None


def _need_binding(cfg: dict, here: Path) -> dict | None:
    b = _cli_binding(cfg, here)
    if b is None:
        _fail(5, "未绑定：先 bind --session <id> --work <dir>，"
                 "或给命令加 --as <session-id>")
    return b


def cmd_on(cfg: dict, rest: list[str]) -> int:
    # 不带 --session 就是「所有已绑定的会话」，必须清掉旧的允许名单，否则会沿用上次范围
    if rest[:1] == ["--session"]:
        if len(rest) < 2 or not rest[1].strip():
            # 曾经这里静默退化成「不限」，把范围放大了却没有任何提示
            return _fail(2, "on: --session 需要一个会话 id；要放开限制就别加这个参数")
        cfg["sessions"] = [rest[1].strip()]
    else:
        cfg["sessions"] = []
    cfg["enabled"] = True
    store.save_config(cfg)
    print(f"on  {cfg['sessions'][0] if cfg['sessions'] else '*'}")
    return 0


def cmd_bind(cfg: dict, rest: list[str]) -> int:
    """只接受 --session。按目录绑已经删掉了，见 store.match_binding 的注释。"""
    session = work = store_key = ""
    i = 0
    while i < len(rest):
        k = rest[i]
        v = rest[i + 1] if i + 1 < len(rest) else ""
        if k == "--session":
            session = v
        elif k == "--work":
            work = v
        elif k == "--store":
            store_key = v
        elif k == "--cwd":
            return _fail(2, "bind: 不支持 --cwd。按目录绑会让同项目的所有会话一起命中，"
                            "已删除；用 --session <id>（id 从 `sessions` 里挑）")
        else:
            return _fail(2, f"bind: 未知参数 {k}")
        i += 2
    if not session:
        return _fail(2, "bind: 需要 --session <id>")
    if not work:
        return _fail(2, "bind: 需要 --work <dir>（这份待办的工作根目录）")
    work = str(Path(work).expanduser())
    if not Path(work).is_dir():
        return _fail(2, f"bind: --work 目录不存在：{work}")
    b = {"tasks": work, "session": session}
    if store_key:
        b["store"] = store_key
    binds = [x for x in (cfg.get("bindings") or []) if x.get("session") != session]
    binds.append(b)
    cfg["bindings"] = binds
    store.save_config(cfg)
    print(f"bind  {session} -> {work}")
    return 0


def cmd_unbind(cfg: dict, rest: list[str]) -> int:
    if not rest:
        return _fail(2, "unbind: 需要 session id")
    key = rest[0]
    cfg["bindings"] = [x for x in (cfg.get("bindings") or [])
                       if x.get("session") != key and x.get("cwd") != key]
    store.save_config(cfg)
    print(f"unbind  {key}")
    return 0


def cmd_add(binding: dict, rest: list[str]) -> int:
    opts = {"--evidence": "evidence", "--pattern": "evidence_pattern",
            "--total": "total", "--judge": "judge", "--hint": "hint"}
    words, kv = [], {}
    i = 0
    while i < len(rest):
        if rest[i] in opts:
            if i + 1 >= len(rest):
                return _fail(2, f"add: {rest[i]} 需要一个值")
            key = opts[rest[i]]
            kv[key] = int(rest[i + 1]) if key == "total" else rest[i + 1]
            i += 2
            continue
        words.append(rest[i])
        i += 1
    if not words:
        return _fail(2, 'add: 需要文本，例如 add "找 1 篇论文" --evidence x.md --total 100')
    bad = queue.check_pattern(kv.get("evidence_pattern"))
    if bad:
        return _fail(2, f"add: {bad}（不会写进队列——坏正则在钩子那侧会被当成「0 行产物」，"
                        f"最后把任务误判成空转）")
    data = store.load_tasks(binding)
    item = queue.add(data, " ".join(words), root=store.work_root(binding), **kv)
    store.save_tasks(binding, data)
    print(item["id"])
    return 0


def run_hook() -> int:
    """钩子入口。这里的铁律是「绝不把失败传染给宿主会话」。

    Stop 钩子会挂进每一个会话的收尾路径。如果它抛异常、退出非零，IDE 会把
    这个失败记在那个会话头上——一个本该与它无关的 agent 会看到一次钩子报错。
    所以：任何异常都吞掉、记一行日志、以 0 退出、不输出。
    宁可这次心跳没发生，也不能让别人的会话多出一条错误。
    """
    try:
        payload = hook.read_payload()
        out = hook.handle(payload)
        if out is not None:
            print(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001 — 这里是刻意的兜底
        try:
            store.log(f"error {type(exc).__name__}: {exc}")
        except Exception:  # noqa: BLE001
            pass
        return 0


def _extract_identity(argv: list[str]) -> tuple[list[str], str]:
    """从任意位置取走 `--as <session-id>`，返回 (剩余参数, 身份)。

    命令行的身份本来只能靠环境变量传，每敲一条都要 export 一次，很烦；
    但也不能为了省事就按目录去猜（那正是让同项目别的 agent 改到别人队列的漏洞）。
    折中：身份必须显式声明，只是允许写在命令里。
    """
    out, ident = [], ""
    i = 0
    while i < len(argv):
        if argv[i] == "--as" and i + 1 < len(argv):
            ident = argv[i + 1]
            i += 2
            continue
        out.append(argv[i])
        i += 1
    return out, ident


def cli(argv: list[str]) -> int:
    argv, ident = _extract_identity(argv)
    if ident:
        os.environ["HEARTBEAT_SESSION"] = ident
    if not argv or argv[0] == "hook":
        return run_hook()
    if argv[0] == "payload":
        return hook.dump(hook.read_payload())

    cfg = store.config()
    here = Path(os.environ.get("HEARTBEAT_CWD") or os.getcwd())
    cmd, rest = argv[0], argv[1:]

    if cmd in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    if cmd == "on":
        return cmd_on(cfg, rest)
    if cmd == "off":
        cfg["enabled"] = False
        store.save_config(cfg)
        print("off")
        return 0
    if cmd == "bind":
        return cmd_bind(cfg, rest)
    if cmd == "unbind":
        return cmd_unbind(cfg, rest)
    if cmd == "exclude":
        cfg["exclude"] = list(rest)
        store.save_config(cfg)
        print(f"exclude  {len(cfg['exclude'])}")
        return 0
    if cmd == "install":
        return cmd_install(rest)
    if cmd == "uninstall":
        return cmd_uninstall(rest)

    if cmd == "sessions":
        seen = store.seen_sessions()
        if not seen:
            print("(none yet — 钩子要跑过一次 Stop 才记得住会话)")
        for sid, meta in sorted(seen.items(), key=lambda kv: kv[1].get("at", ""), reverse=True):
            print(f"{sid}  {meta.get('at', '')}  {meta.get('cwd', '')}")
        return 0

    if cmd == "doctor":
        return cmd_doctor(cfg)

    # 以下命令都要落在一份具体待办上
    binding = _need_binding(cfg, here)
    if binding is None:
        return 5
    root = store.work_root(binding)
    data = store.load_tasks(binding)

    if cmd == "add":
        return cmd_add(binding, rest)
    if cmd == "list":
        items = data.get("tasks", [])
        if not items:
            print("(no tasks)")
            return 0
        for t in items:
            tot = int(t.get("total") or 0)
            prog = f"{int(t.get('done') or 0)}/{tot}" if tot else "-"
            print(f"{t.get('id')}  {t.get('status', 'todo'):7s} {prog:>6s}  {t.get('text', '')}")
        pend = queue.pending(data)
        if pend:
            print(f"next  {pend[0].get('id')}  {pend[0].get('text', '')}")
        return 0
    if not rest:
        # 匿名模式的 nudge 不给 id：这些命令默认落在「当前该做的那一件」上
        pend = queue.pending(data)
        if cmd in ("inc", "sync", "done", "doing", "todo", "block") and pend:
            rest = [pend[0].get("id")]
        else:
            return _fail(2, f"{cmd}: 需要任务 id（--help 看用法）")

    if cmd == "rm":
        before = len(data.get("tasks", []))
        data["tasks"] = [t for t in data.get("tasks", []) if t.get("id") != rest[0]]
        if len(data["tasks"]) == before:
            return _fail(3, f"no task {rest[0]}")
        data["last_progress_at"] = time.time()
        store.save_tasks(binding, data)
        print(f"rm  {rest[0]}")
        return 0

    task = queue.find(data, rest[0])
    if task is None:
        return _fail(3, f"no task {rest[0]}")

    if cmd == "inc":
        ok, msg = queue.bump(task, root)
        if not ok:
            return _fail(4, f"refuse: {msg}")
        data["last_progress_at"] = time.time()
        store.save_tasks(binding, data)
        print(msg)
        return 0
    if cmd == "sync":
        msg = queue.sync(task, root)
        data["last_progress_at"] = time.time()
        store.save_tasks(binding, data)
        print(f"sync  {rest[0]}  {msg}")
        return 0
    if cmd in ("done", "doing", "todo", "block"):
        status = "blocked" if cmd == "block" else cmd
        queue.set_status(task, status, " ".join(rest[1:]).strip())
        data["last_progress_at"] = time.time()
        store.save_tasks(binding, data)
        print(f"{status}  {rest[0]}")
        return 0
    if cmd == "set":
        # 位置参数是 text（可省），其余用 --key。写错 evidence 路径时不必 rm 重建。
        opts = {"--total": "total", "--evidence": "evidence",
                "--pattern": "evidence_pattern", "--judge": "judge"}
        text, changed = "", []
        i = 1
        while i < len(rest):
            k = rest[i]
            if k in opts:
                if i + 1 >= len(rest):
                    return _fail(2, f"set: {k} 需要一个值")
                key = opts[k]
                if key == "evidence_pattern":
                    bad = queue.check_pattern(rest[i + 1])
                    if bad:
                        return _fail(2, f"set: {bad}")
                task[key] = int(rest[i + 1]) if key == "total" else rest[i + 1]
                changed.append(k)
                i += 2
                continue
            text = rest[i]
            i += 1
        if text:
            task["text"] = text
            changed.append("text")
        if not changed:
            return _fail(2, 'set: 没有要改的，例如 set t1 --evidence x.md --pattern \'^\\|\'')
        data["last_progress_at"] = time.time()
        store.save_tasks(binding, data)
        print(f"set  {rest[0]}  {','.join(changed)}")
        return 0

    print(USAGE)
    return 2


def _launcher(here: Path) -> Path:
    for root in (here, store.PKG.parent.parent.parent):
        p = root / ".agent-tools" / "heartbeat"
        if p.exists():
            return p
    return store.PKG.parent.parent.parent / ".agent-tools" / "heartbeat"


def _settings_path(scope: str, here: Path) -> Path:
    if scope == "user":
        return Path.home() / ".codebuddy" / "settings.json"
    return here / ".codebuddy" / "settings.json"


def cmd_install(rest: list[str]) -> int:
    """装 Stop 钩子。幂等：重复跑只更新，不叠加条目。

    注册这件事必须由命令完成，不能靠人手改 JSON——改错了不会报错，只会静默失效，
    而那正是最难查的一种坏法。
    """
    # loop_limit = 用户一句话之后，最多允许它连着干几件。
    # 上游只认 -1（不限）或 1..100，超出范围会被静默降成 1——
    # 填 300 的后果是「每次用户说话只能推进一件」，症状看着像钩子不循环。
    scope, loop_limit, launcher_override = "user", 20, ""
    i = 0
    while i < len(rest):
        k = rest[i]
        v = rest[i + 1] if i + 1 < len(rest) else ""
        if k == "--scope":
            if v not in ("user", "project"):
                return _fail(2, "install: --scope 只能是 user 或 project")
            scope = v
        elif k == "--loop-limit":
            try:
                loop_limit = int(v)
            except ValueError:
                return _fail(2, "install: --loop-limit 需要一个整数")
            if loop_limit != -1 and not 1 <= loop_limit <= 100:
                return _fail(2, "install: --loop-limit 只能是 -1（不限）或 1..100。"
                                "超出范围上游会静默降成 1，等于「每轮只推一件」，"
                                "症状是钩子看起来不循环")
        elif k == "--command":
            launcher_override = v
        else:
            return _fail(2, f"install: 未知参数 {k}")
        i += 2

    here = Path(os.environ.get("HEARTBEAT_CWD") or os.getcwd())
    launcher = Path(launcher_override) if launcher_override else _launcher(here)
    if not launcher_override and not launcher.exists():
        print(f"install: 启动器不存在，先跑 agent-ide install heartbeat（期望 {launcher}）",
              file=sys.stderr)
        return _fail(5, "install: 缺少启动器")

    path = _settings_path(scope, here)
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except ValueError:
        return _fail(2, f"install: {path} 不是合法 JSON，拒绝改写")
    hooks = data.setdefault("hooks", {})

    def is_ours(e: dict) -> bool:
        return any("heartbeat" in str(h.get("command", "")) for h in (e.get("hooks") or []))

    def upsert(event: str, extra: dict | None = None) -> int:
        entries = hooks.setdefault(event, [])
        hook_obj = {"type": "command", "command": str(launcher), "timeout": 20,
                    "description": "heartbeat：待办没清时把下一项喂回模型"
                                   "（只对 bindings 命中的会话生效；未命中完全静默、"
                                   "异常吞掉并以 0 退出）"}
        entry = {"hooks": [hook_obj]}
        if extra:
            entry.update(extra)
        n = 0
        for idx, e in enumerate(entries):
            if is_ours(e):
                entries[idx] = entry
                n += 1
        if n == 0:
            entries.append(entry)
        return n or 1

    # 只挂 Stop 一个点，没有第二个。
    # 曾经还挂过 UserPromptSubmit（人中途插话时把「还有活」补进上下文）和
    # SubagentStop，两个都撤了：子代理与父会话共用同一个 session_id，payload 里
    # 没有任何字段能把它们分开，于是「派给这个会话」实际派给了这个会话里所有正在
    # 干活的 agent。挂载点越少，误伤面越小。
    n_stop = upsert("Stop", {"loop_limit": loop_limit})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"install  {scope}  stop={n_stop} loop_limit={loop_limit}")
    return 0


def cmd_uninstall(rest: list[str]) -> int:
    scope = "user"
    if rest[:1] == ["--scope"] and len(rest) > 1:
        scope = rest[1]
        if scope not in ("user", "project"):
            return _fail(2, "uninstall: --scope 只能是 user 或 project")
    here = Path(os.environ.get("HEARTBEAT_CWD") or os.getcwd())
    path = _settings_path(scope, here)
    if not path.exists():
        print(f"uninstall  {scope}  nothing")
        return 0
    try:
        data = json.loads(path.read_text())
    except ValueError:
        return _fail(2, f"uninstall: {path} 不是合法 JSON，拒绝改写")
    hooks = data.get("hooks") or {}
    removed = 0
    # 扫全部事件，不枚举。旧版本往 UserPromptSubmit 里写过条目，硬编码列表会漏，
    # 而漏掉的那条会永远留在那里、每次触发都跑一遍。
    for event in list(hooks.keys()):
        entries = hooks.get(event) or []
        kept = [e for e in entries
                if not any("heartbeat" in str(h.get("command", "")) for h in (e.get("hooks") or []))]
        removed += len(entries) - len(kept)
        if kept:
            hooks[event] = kept
        elif event in hooks:
            hooks.pop(event)
    if not removed:
        print(f"uninstall  {scope}  nothing")
        return 0
    if not hooks:
        data.pop("hooks", None)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"uninstall  {scope}  -{removed}")
    return 0


def cmd_doctor(cfg: dict) -> int:
    """绑错/没注册的典型症状是「一声不响」：没报错，也没有心跳。所以必须能自检。"""
    seen = store.seen_sessions()
    excl = set(cfg.get("exclude") or [])
    binds = cfg.get("bindings") or []
    print(f"enabled  {cfg.get('enabled')}")
    print(f"exclude  {len(excl)}")
    print(f"hook     {_hook_status()}")
    if not binds:
        print("WARN     bindings 为空，任何会话都不会被拦")
        return 0
    for b in binds:
        sid = b.get("session") or b.get("cwd") or "?"
        data = store.load_tasks(b)
        pend = queue.pending(data)
        chain = data.get("_chain") or {}
        if b.get("session"):
            hits = [sid] if sid in seen else []
        else:
            root = str(Path(b["cwd"]).expanduser().resolve())
            hits = [k for k, m in seen.items() if str(m.get("cwd", "")).startswith(root)]
        print(f"bind     {str(sid)[:40]}")
        print(f"  work   {b.get('tasks')}  seen={len(hits)}")
        print(f"  store  {store.tasks_path(b)}")
        print(f"  queue  {len(data.get('tasks', []))} item  {len(pend)} pending  "
              f"nudge={chain.get('count', 0)}/{cfg.get('max_nudge_per_chain')}")
        if pend:
            print(f"  next   {pend[0].get('id')}  {pend[0].get('text', '')[:50]}")
        for t in data.get("tasks", []):
            extra = ""
            if t.get("_stall"):
                extra += f" stall={t['_stall']}"
            if t.get("blocked_reason"):
                extra += f" why={t['blocked_reason'][:40]}"
            prog = f"{t.get('done') or 0}/{t.get('total') or '-'}"
            print(f"         {t.get('id')}  {t.get('status', 'todo'):7s} {prog:>6s}  "
                  f"{t.get('text', '')[:40]}{extra}")
        if b.get("session") and not hits:
            print("WARN     这个 session 没出现过 Stop（或 id 写错）")
        if not store.tasks_path(b).exists():
            print("WARN     待办文件不存在，这个绑定永远不会触发")
    if store.LOG.exists():
        tail = store.LOG.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-2:]
        for line in tail:
            print(f"log      {line}")
    return 0


def _hook_status() -> str:
    """在几个可能的 settings.json 里找有没有注册本脚本。没注册 = 装了也不会跑。"""
    cands = [store.PKG.parent.parent.parent / ".codebuddy" / "settings.json",
             Path.home() / ".codebuddy" / "settings.json",
             Path.cwd() / ".codebuddy" / "settings.json",
             Path.cwd() / ".codebuddy" / "settings.local.json"]
    found, limits = [], []
    for p in cands:
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text())
        except ValueError:
            continue
        stop = (d.get("hooks") or {}).get("Stop") or []
        for entry in stop:
            blob = json.dumps(entry, ensure_ascii=False)
            if "heartbeat" in blob:
                found.append(str(p))
                limits.append(entry.get("loop_limit", "?"))
    if not found:
        return "未注册"
    lim = limits[0]
    if lim == -1:
        return "stop  loop_limit=-1 (不限)"
    if isinstance(lim, int) and 1 <= lim <= 100:
        return f"stop  loop_limit={lim} (每轮最多连推 {lim})"
    return f"stop  loop_limit={lim} (超出 1..100，上游会降成 1)"


if __name__ == "__main__":
    try:
        sys.exit(cli(sys.argv[1:]))
    except BrokenPipeError:
        # `doctor | head` 这类下游提前关闭管道时，不要再吐 traceback
        os._exit(0)
