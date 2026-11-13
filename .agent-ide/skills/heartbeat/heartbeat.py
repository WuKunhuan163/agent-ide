#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""heartbeat -- no wrapping up while todos remain: push one item back to the session.

Mechanism (the CodeBuddy equivalent of OpenClaw's Heartbeat):
  When the main session is about to end, the IDE runs the Stop hook. The hook
  printing {"continue": false, "stopReason": "..."} is one "heartbeat turn" --
  stopReason enters the same session as a new user message with the full context,
  and no background task is created.
  With nothing pending it prints nothing, so there is zero interruption.

The difference from a periodic heartbeat is the trigger only: OpenClaw wakes on
cron, this wakes on "the session was about to stop". The idle tick is dropped; the
semantics are the same.

One iron rule: **only the hook may push**. No command lets the agent push an item
on demand -- it can only record (inc / done / block). "Assigning work to itself"
does not exist in the interface.
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

USAGE = f"""heartbeat -- no wrapping up while todos remain

  heartbeat.py                        Stop hook entry (reads JSON on stdin)
  heartbeat.py payload                print the payload the hook received (debug)

  install [--scope user|project] [--loop-limit N]
                                      install the Stop hook (idempotent; loop_limit = max pushes per turn)
  uninstall [--scope user|project]    remove the hook this tool installed (only its own entry)
  on [--session <id>]                 enable; with --session it applies to that session only
  off                                 disable (the hook goes silent immediately)
  bind --session <id> --work <dir>    bind a session to one working directory (todos live in this skill's data/)
  unbind <session>                    drop the binding

  (any command accepts --as <session-id> to declare the caller, equivalent to setting HEARTBEAT_SESSION)

  add "<text>" [--judge "..."] [--evidence <path>] [--pattern <re>] [--total N]
  inc <id>                            record one step (counts evidence lines; refuses if they did not grow)
  sync <id>                           pull progress back to the real line count of the evidence file
  done|doing|todo <id> [note]
  block <id> "<where it is stuck>"
  rm <id>                             delete from the queue (a blocked item need not hang there forever)
  set <id> ["<text>"] [--total N] [--evidence p] [--pattern re] [--judge s]
  list | sessions | exclude <id>... | doctor

Todos live in this skill's data/tasks/<key>.json, never in the project directory:
one project often runs several sessions, and anything stored in the project is
readable by the project's other agents.
"""


def _fail(code: int, msg: str) -> int:
    print(msg, file=sys.stderr)
    return code


def _cli_binding(cfg: dict, here: Path) -> dict | None:
    """The command line carries no identity: any process can run it. So nothing here
    is guessed.

    HEARTBEAT_SESSION must be set explicitly and must equal some binding's session.

    The previous version kept a fallback at level three -- "if there is exactly one
    session binding and its working directory contains the current directory, use
    it". Convenient-looking, and a hole: another agent in the same project running
    `heartbeat.py block t1 "..."` would hit that fallback and rewrite someone else's
    todo. It really happened once. Better that it errors than guesses.
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
        _fail(5, "not bound: run bind --session <id> --work <dir> first, "
                 "or pass --as <session-id>")
    return b


def cmd_on(cfg: dict, rest: list[str]) -> int:
    # Without --session this means "every bound session", so the old allow list has to be
    # cleared or the previous scope carries over
    if rest[:1] == ["--session"]:
        if len(rest) < 2 or not rest[1].strip():
            # This used to degrade silently to "unrestricted", widening the scope with no
            # hint at all
            return _fail(2, "on: --session needs a session id; omit the flag to widen the scope")
        cfg["sessions"] = [rest[1].strip()]
    else:
        cfg["sessions"] = []
    cfg["enabled"] = True
    store.save_config(cfg)
    print(f"on  {cfg['sessions'][0] if cfg['sessions'] else '*'}")
    return 0


def cmd_bind(cfg: dict, rest: list[str]) -> int:
    """Accepts --session only. Binding by directory is gone; see store.match_binding."""
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
            return _fail(2, "bind: --cwd is not supported. Binding by directory caught every "
                            "session of the project at once and was removed; use --session <id> "
                            "(pick the id from `sessions`)")
        else:
            return _fail(2, f"bind: unknown flag {k}")
        i += 2
    if not session:
        return _fail(2, "bind: --session <id> is required")
    if not work:
        return _fail(2, "bind: --work <dir> is required (the work root of these todos)")
    work = str(Path(work).expanduser())
    if not Path(work).is_dir():
        return _fail(2, f"bind: --work directory does not exist: {work}")
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
        return _fail(2, "unbind: a session id is required")
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
                return _fail(2, f"add: {rest[i]} needs a value")
            key = opts[rest[i]]
            kv[key] = int(rest[i + 1]) if key == "total" else rest[i + 1]
            i += 2
            continue
        words.append(rest[i])
        i += 1
    if not words:
        return _fail(2, 'add: text is required, e.g. add "find one paper" --evidence x.md --total 100')
    bad = queue.check_pattern(kv.get("evidence_pattern"))
    if bad:
        return _fail(2, f"add: {bad} (not written to the queue -- a broken pattern reads as "
                        f"'0 evidence lines' on the hook side, which ends up blocking the task "
                        f"as stalled)")
    data = store.load_tasks(binding)
    item = queue.add(data, " ".join(words), root=store.work_root(binding), **kv)
    store.save_tasks(binding, data)
    print(item["id"])
    return 0


def run_hook() -> int:
    """Hook entry. The iron rule here: never pass a failure on to the host session.

    The Stop hook sits on every session's wrap-up path. If it raises or exits
    non-zero, the IDE records that failure against that session -- an agent with no
    stake in it sees a hook error. So: swallow every exception, write one log line,
    exit 0, print nothing. Better that this heartbeat did not happen than that
    someone else's session grows an error.
    """
    try:
        payload = hook.read_payload()
        out = hook.handle(payload)
        if out is not None:
            print(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all here
        try:
            store.log(f"error {type(exc).__name__}: {exc}")
        except Exception:  # noqa: BLE001
            pass
        return 0


def _extract_identity(argv: list[str]) -> tuple[list[str], str]:
    """Strip `--as <session-id>` from anywhere, returning (remaining args, identity).

    Identity used to travel only through an environment variable, which means an
    export before every command -- annoying. Guessing it from the directory is not
    the fix either: that is exactly the hole that let another agent in the same
    project write to someone else's queue. The compromise: identity stays explicit,
    it is merely allowed to sit in the command.
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
            print("(none yet — the hook records a session only after one Stop)")
        for sid, meta in sorted(seen.items(), key=lambda kv: kv[1].get("at", ""), reverse=True):
            print(f"{sid}  {meta.get('at', '')}  {meta.get('cwd', '')}")
        return 0

    if cmd == "doctor":
        return cmd_doctor(cfg)

    # Everything below needs one concrete todo file
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
        # An anonymous nudge carries no id: these commands default to "the one to do now"
        pend = queue.pending(data)
        if cmd in ("inc", "sync", "done", "doing", "todo", "block") and pend:
            rest = [pend[0].get("id")]
        else:
            return _fail(2, f"{cmd}: a task id is required (see --help)")

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
        # The positional is text (optional); everything else is a --key. A wrong evidence
        # path no longer forces rm and re-add.
        opts = {"--total": "total", "--evidence": "evidence",
                "--pattern": "evidence_pattern", "--judge": "judge"}
        text, changed = "", []
        i = 1
        while i < len(rest):
            k = rest[i]
            if k in opts:
                if i + 1 >= len(rest):
                    return _fail(2, f"set: {k} needs a value")
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
            return _fail(2, 'set: nothing to change, e.g. set t1 --evidence x.md --pattern \'^\\|\'')
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
    """Install the Stop hook. Idempotent: re-running updates, never stacks entries.

    Registration has to be done by a command, not by hand-editing JSON: a bad manual
    edit does not error, it just goes silently dead, and that is the hardest kind of
    breakage to find.
    """
    # loop_limit = how many items may be chained after one user message.
    # Upstream accepts only -1 (unlimited) or 1..100; anything else is silently
    # lowered to 1, so 300 behaves as "one item per user message", which looks like
    # a hook that does not loop.
    scope, loop_limit, launcher_override = "user", 20, ""
    i = 0
    while i < len(rest):
        k = rest[i]
        v = rest[i + 1] if i + 1 < len(rest) else ""
        if k == "--scope":
            if v not in ("user", "project"):
                return _fail(2, "install: --scope must be user or project")
            scope = v
        elif k == "--loop-limit":
            try:
                loop_limit = int(v)
            except ValueError:
                return _fail(2, "install: --loop-limit needs an integer")
            if loop_limit != -1 and not 1 <= loop_limit <= 100:
                return _fail(2, "install: --loop-limit must be -1 (unlimited) or 1..100. "
                                "Out of range, upstream silently lowers it to 1, meaning "
                                "'one push per turn', which looks like a hook that does not loop")
        elif k == "--command":
            launcher_override = v
        else:
            return _fail(2, f"install: unknown flag {k}")
        i += 2

    here = Path(os.environ.get("HEARTBEAT_CWD") or os.getcwd())
    launcher = Path(launcher_override) if launcher_override else _launcher(here)
    if not launcher_override and not launcher.exists():
        print(f"install: launcher missing; run agent-ide install heartbeat (expected {launcher})",
              file=sys.stderr)
        return _fail(5, "install: launcher missing")

    path = _settings_path(scope, here)
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except ValueError:
        return _fail(2, f"install: {path} is not valid JSON; refusing to rewrite it")
    hooks = data.setdefault("hooks", {})

    def is_ours(e: dict) -> bool:
        return any("heartbeat" in str(h.get("command", "")) for h in (e.get("hooks") or []))

    def upsert(event: str, extra: dict | None = None) -> int:
        entries = hooks.setdefault(event, [])
        hook_obj = {"type": "command", "command": str(launcher), "timeout": 20,
                    "description": "heartbeat: feed the next todo back to the model while any remain"
                                   " (fires only for sessions a binding matches; otherwise fully"
                                   " silent, exceptions swallowed and exit 0)"}
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

    # Stop is the only mount point, and stays the only one.
    # UserPromptSubmit (refilling "work remains" when the human cuts in) and
    # SubagentStop were both tried and removed: a subagent shares its parent's
    # session_id and nothing in the payload separates them, so "dispatch to this
    # session" dispatched to every agent working inside it. Fewer mount points, less
    # collateral damage.
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
            return _fail(2, "uninstall: --scope must be user or project")
    here = Path(os.environ.get("HEARTBEAT_CWD") or os.getcwd())
    path = _settings_path(scope, here)
    if not path.exists():
        print(f"uninstall  {scope}  nothing")
        return 0
    try:
        data = json.loads(path.read_text())
    except ValueError:
        return _fail(2, f"uninstall: {path} is not valid JSON; refusing to rewrite it")
    hooks = data.get("hooks") or {}
    removed = 0
    # Scan every event instead of enumerating. An older version wrote entries under
    # UserPromptSubmit, a hardcoded list would miss them, and a missed entry stays
    # there forever running on every trigger.
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
    """A wrong binding or a missing registration shows up as silence: no error and no
    heartbeat. So self-diagnosis has to exist."""
    seen = store.seen_sessions()
    excl = set(cfg.get("exclude") or [])
    binds = cfg.get("bindings") or []
    print(f"enabled  {cfg.get('enabled')}")
    print(f"exclude  {len(excl)}")
    print(f"hook     {_hook_status()}")
    if not binds:
        print("WARN     bindings is empty; no session will be caught")
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
            print("WARN     this session never reached Stop (or the id is wrong)")
        if not store.tasks_path(b).exists():
            print("WARN     todo file missing; this binding will never fire")
    if store.LOG.exists():
        tail = store.LOG.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-2:]
        for line in tail:
            print(f"log      {line}")
    return 0


def _hook_status() -> str:
    """Look for this script in the candidate settings.json files. Not registered means
    installed but never runs."""
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
        return "not registered"
    lim = limits[0]
    if lim == -1:
        return "stop  loop_limit=-1 (unlimited)"
    if isinstance(lim, int) and 1 <= lim <= 100:
        return f"stop  loop_limit={lim} (at most {lim} pushes per turn)"
    return f"stop  loop_limit={lim} (outside 1..100; upstream lowers it to 1)"


if __name__ == "__main__":
    try:
        sys.exit(cli(sys.argv[1:]))
    except BrokenPipeError:
        # Do not spill a traceback when a downstream like `doctor | head` closes early
        os._exit(0)
