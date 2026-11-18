#!/usr/bin/env python3
"""hook — keyword or similarity triggered context injection for an IDE.

A rule is a condition and a value. The condition is "the prompt contains one of
these keywords" or "the prompt is closer than a threshold to a stored context"
(token cosine). The value is text injected into the model's context on
UserPromptSubmit.

Layout under data/, one file per rule so every rule is readable on its own:

    data/hooks/<id>.json   the rule: id, ide, trigger, keywords|key+threshold, enabled
    data/inject/<id>.md    the value injected when it fires
    data/keys/<id>.md      the stored context for a similarity rule
    data/hook.log          fire / error lines only
"""

from __future__ import annotations

import argparse
import unicodedata
import pathlib
import json
import math
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RULES = DATA
INJECT = DATA / "inject"
KEYS = DATA / "keys"
LOG = DATA / "hook.log"

IDE_PATHS = {
    "codebuddy": (Path.home() / ".codebuddy" / "settings.json", Path(".codebuddy") / "settings.json", "UserPromptSubmit"),
}
STOP = set("的 了 是 在 和 与 也 就 都 而 及 或 对 把 被 从 到 这 那 有 无 不 一个 我们 你 我 他 它".split())


def pad(text, width):
    """Pad by display width, so CJK columns line up."""
    text = str(text)
    w = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    return text + " " * max(0, width - w)


def action_phrase(text, width=44):
    """The command a rule is: its own first label, so the reader runs it before anything else."""
    body = text.strip()
    # a sourcing header is not an action: drop a leading 【…】 line that only says where the text comes from
    first, _, rest = body.partition("\n")
    if first.startswith("【") and any(k in first for k in ("chapter", "原样注入", "来源")):
        body = rest.strip() or body
    flat = " ".join(body.split())
    for pat in (r"\*\*([^*]{2,40})\*\*", r"【([^】]{2,40})】"):
        m = re.search(pat, flat)
        if m:
            return m.group(1).strip()
    return re.split(r"[。：:；;]", flat)[0][:width].strip()


def cmd_block(hid, why, value):
    """One rule, one block: the value is the context, verbatim, under a one-line head."""
    why = why if str(why).startswith("matched") else "matched " + str(why)
    return "【%s｜%s】\n%s" % (hid, why, value.strip())


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def log(line):
    DATA.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write("%s\t%s\n" % (now(), line))


# ---------- storage: one package per rule ----------

def pkg_dir(hid):
    """A rule is data/<id>/ (hook.json + inject.md + optional code); data/hooks/<id>/ still reads."""
    flat = DATA / hid
    if (flat / "hook.json").exists():
        return flat
    old = DATA / "hooks" / hid
    return old if (old / "hook.json").exists() else flat


def _paths(hid):
    """A rule is a package: data/hooks/<id>/hook.json + inject.md + whatever code it needs.

    The older layout (data/hooks/<id>.json + data/inject/<id>.md) still reads, so an
    existing rule keeps firing; `add --package` writes the package form.
    """
    d = RULES / hid
    return d / "hook.json", d / "inject.md"


def _read_rule(path: Path) -> dict:
    h = json.loads(path.read_text(encoding="utf-8"))
    d = pkg_dir(h["id"])
    for cand in ((d / "inject.md") if d.is_dir() else None, INJECT / (h["id"] + ".md")):
        if cand and cand.exists():
            h["inject"] = cand.read_text(encoding="utf-8")
            break
    if d.is_dir():
        h["package"] = str(d)
    return h


def load_rules() -> list:
    out = []
    if not RULES.exists():
        return out
    for p in sorted(RULES.iterdir()):
        if p.is_dir() and (p / "hook.json").exists():
            out.append(_read_rule(p / "hook.json"))
        elif p.suffix == ".json" and p.name != "hooks.json":
            out.append(_read_rule(p))
    return out


def save_rule(h: dict):
    rp, ip = _paths(h["id"])
    rp.parent.mkdir(parents=True, exist_ok=True)
    w = {k: v for k, v in h.items() if k not in ("inject", "package")}
    tmp = rp.with_suffix(".tmp")
    tmp.write_text(json.dumps(w, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, rp)
    ip.write_text(h.get("inject", ""), encoding="utf-8")


def drop_rule(hid):
    d = pkg_dir(hid)
    if d.is_dir():
        for child in sorted(d.rglob("*"), reverse=True):
            child.unlink() if child.is_file() else child.rmdir()
        d.rmdir()
    for p in (RULES / (hid + ".json"), INJECT / (hid + ".md"), KEYS / (hid + ".md")):
        if p.exists():
            p.unlink()


def find(hid):
    d = pkg_dir(hid)
    if d.is_dir() and (d / "hook.json").exists():
        return _read_rule(d / "hook.json")
    p = RULES / (hid + ".json")
    return _read_rule(p) if p.exists() else None


def log_inject(matched: str, inject: str) -> None:
    """The full context handed to the agent this turn, one line in data/plan/data/log.log."""
    try:
        f = DATA / "plan" / "data" / "log.log"
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write("%s\top=inject\tmatched=%s\tchars=%d\tinject=%s\n"
                     % (now(), matched.replace("\t", " "), len(inject),
                        inject.replace("\n", "\\n") if inject else "-"))
    except Exception:
        pass


def capture_prompt(hid: str, prompt: str, matched: str = "") -> None:
    """Keep the prompt a rule fired on, with provenance.

    The text is only ever written here, from the IDE's payload, together with a record
    carrying its hash: a consumer (e.g. `hook plan init`) can then refuse a prompt that
    was typed or copied by hand. Every firing also appends a line to the log, so an
    overwritten text never erases that a different prompt once fired.
    """
    import hashlib
    d = pkg_dir(hid) / "data" / "capture"
    d.mkdir(parents=True, exist_ok=True)
    (d / (hid + ".txt")).write_text(prompt, encoding="utf-8")
    sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    (d / (hid + ".json")).write_text(json.dumps(
        {"sha256": sha, "chars": len(prompt), "at": now(), "matched": matched,
         "first": prompt.strip().split("\n")[0][:80]}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    with (d / (hid + ".log")).open("a", encoding="utf-8") as f:
        f.write("%s\t%s\t%d\t%s\n" % (now(), sha[:16], len(prompt),
                                        prompt.strip().split("\n")[0][:60]))


def stored_prompt(hid: str) -> str:
    p = DATA / "capture" / (hid + ".txt")
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ---------- triggers ----------

def tokens(text: str) -> set:
    t = re.sub(r"[\s，。；：、！？（）()「」“”'\"/\\.,;:!?<>\[\]{}|_=+*#`~-]+", " ", text or "")
    out = set()
    for w in t.split():
        w = w.strip().lower()
        if len(w) >= 2 and w not in STOP:
            out.add(w)
    for ch in re.findall(r"[\u4e00-\u9fff]{2,}", text or ""):
        for i in range(len(ch) - 1):
            g = ch[i:i + 2]
            if g not in STOP:
                out.add(g)
    return out


def cosine(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / math.sqrt(len(a) * len(b))


def skills_dir() -> Path:
    return project_root() / ".agent-ide" / "skills"


def skill_front(path: Path):
    """name and description from the YAML head, without a yaml parser."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return path.parent.name, ""
    head = text[:2000]
    name = re.search(r"(?m)^name:\s*(.+)$", head)
    desc = re.search(r"(?ms)^description:\s*(.+?)^(?:[a-z_]+:|---)", head)
    d = " ".join((desc.group(1) if desc else "").split())
    d = d.lstrip(">- ").strip()
    return (name.group(1).strip() if name else path.parent.name), d


def skill_hits(prompt: str):
    """Every installed tool whose name appears in the prompt.

    A tool is installed if it has a launcher under `.agent-tools/` or a
    directory with SKILL.md under `.agent-ide/skills/`; the two sets overlap
    and are merged by name.
    """
    out, seen = [], set()
    base = skills_dir()
    tools = project_root() / ".agent-tools"
    names = set()
    if base.exists():
        names |= {d.name for d in base.iterdir() if (d / "SKILL.md").exists()}
    if tools.exists():
        names |= {p.name for p in tools.iterdir() if p.is_file()}
    low = prompt.lower()
    for name in sorted(names):
        if name in seen:
            continue
        if not re.search(r"(?<![a-z0-9-])" + re.escape(name.lower()) + r"(?![a-z0-9-])", low):
            continue
        seen.add(name)
        skill = base / name / "SKILL.md"
        if skill.exists():
            n, desc = skill_front(skill)
            short = re.split(r"(?<=[.。])\s", desc)[0][:110].strip()
            out.append("【%s】先读 %s（%d 行）%s" % (name, skill.relative_to(project_root()),
                                                   len(skill.read_text(encoding="utf-8").split("\n")),
                                                   ("：" + short) if short else ""))
        else:
            out.append("【%s】已安装：%s（无 SKILL.md）" % (name, tools / name))
    return out


def load_pkg(hid: str):
    h = find(hid)
    if not h or not h.get("entry"):
        return None
    d = pkg_dir(hid)
    mod_path = d / h["entry"]
    if not mod_path.exists():
        mod_path = ROOT / h["entry"]
    if not mod_path.exists():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("hook_pkg_%s" % hid, mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def auto_instance_text(hid: str, prompt: str, matched: str = "") -> str:
    """Store happens already; here the rule's package allocates or resumes the tree."""
    mod = load_pkg(hid)
    if mod is None or not hasattr(mod, "auto_start"):
        return ""
    try:
        return mod.auto_start(DATA, prompt, matched) or ""
    except Exception as exc:
        log("auto_instance error\t%s" % exc)
        return ""


def plan_state_text(hid: str) -> str:
    """Ask the rule's package what the open tree wants next; empty when nothing is open."""
    h = find(hid)
    if not h or not h.get("entry"):
        return ""
    d = pkg_dir(hid)
    mod_path = d / h["entry"]
    if not mod_path.exists():
        mod_path = ROOT / h["entry"]
    if not mod_path.exists():
        return ""
    import importlib.util
    spec = importlib.util.spec_from_file_location("hook_state_%s" % hid, mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        return mod.next_text(DATA) or ""
    except Exception:
        return ""


def evaluate(prompt: str, rules: list, verbose=False):
    hits = []
    for h in rules:
        if not h.get("enabled", True):
            continue
        if h.get("auto_instance"):
            hits.append((dict(h, inject=""), 1.0, "every prompt"))
            continue
        if h["trigger"] == "fn" and h.get("fn") == "plan":
            text = plan_state_text(h["id"])
            if text:
                hits.append((dict(h, inject=text), 1.0, "open tree"))
            continue
        if h["trigger"] == "fn":
            found = skill_hits(prompt) if h.get("fn", "tools") == "tools" else []
            if found:
                hits.append((dict(h, inject="\n".join(found)), 1.0,
                             "tool " + ",".join(re.findall(r"【([^】]+)】", " ".join(found)))))
            continue
        if h["trigger"] == "keyword":
            found = [k for k in h.get("keywords", []) if k in prompt]
            ok = bool(found) if h.get("match", "any") == "any" else len(found) == len(h.get("keywords", []))
            if ok:
                hits.append((h, 1.0, "matched %s" % ",".join(found)))
        else:
            kp = KEYS / h.get("key", "")
            if not kp.exists():
                continue
            s = cosine(tokens(prompt), tokens(kp.read_text(encoding="utf-8")))
            thr = h.get("threshold", 0.55)
            if s >= thr:
                hits.append((h, s, "cosine %.3f >= %.2f" % (s, thr)))
            elif verbose:
                print(pad(h["id"],18)+"%.3f < %.2f" % (s, thr))
    return hits


# ---------- ide side ----------

def project_root() -> Path:
    return ROOT.parents[2]


def settings_path(ide: str, scope: str) -> Path:
    user, proj, _ = IDE_PATHS[ide]
    return user if scope == "user" else project_root() / proj


def launcher() -> str:
    cand = project_root() / ".agent-tools" / "hook"
    return str(cand) if cand.exists() else str(ROOT / "hook.py")


GUARD_RE = re.compile(r"\.agent-tools/hook\b|hook\.py\b")


def ensure_registered(ide: str = "codebuddy", scope: str = "user"):
    """The entry is one: add already refused a duplicate id, so this only
    keeps the command current, or appends the entry the first time."""
    path = settings_path(ide, scope)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    groups = data.setdefault("hooks", {}).setdefault(IDE_PATHS[ide][2], [])
    want = shlex.quote(launcher())
    for g in groups:
        for h in g.get("hooks", []):
            if GUARD_RE.search(h.get("command", "")):
                if h.get("command") != want:
                    h["command"] = want
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                return path
    groups.append({"hooks": [{"type": "command", "command": want,
                              "description": "agent-ide hook: keyword, similarity or skill triggered context injection",
                              "timeout": 10}]})
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def drop_entry_when_empty():
    rules = load_rules()
    if rules:
        return
    for ide, (user, proj, ev) in IDE_PATHS.items():
        for path in {user, settings_path(ide, "project")}:
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            groups = data.get("hooks", {}).get(ev, [])
            keep = []
            for g in groups:
                hs = [h for h in g.get("hooks", []) if not GUARD_RE.search(h.get("command", ""))]
                if hs:
                    g["hooks"] = hs
                    keep.append(g)
            if len(keep) != len(groups):
                data["hooks"][ev] = keep
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------- registration ----------

def slug(text: str) -> str:
    s = re.sub(r"[^0-9A-Za-z_.-]+", "-", text.strip().lower()).strip("-")
    return s or "hook"


def cmd_add(a):
    hid = a.id.strip()
    if not re.match(r"^[A-Za-z0-9_.-]+$", hid):
        print("hook: bad id %r ([A-Za-z0-9_.-]+)" % hid, file=sys.stderr)
        return 2
    if find(hid):
        print("hook: %s: already registered" % hid, file=sys.stderr)
        return 3
    inject = Path(a.inject[1:]).read_text(encoding="utf-8") if a.inject.startswith("@") else a.inject
    if a.trigger == "fn":
        inject = inject or "（由判定函数生成，不含静态文本）"
    if not inject.strip() and not a.capture_only:
        print("hook: empty --inject", file=sys.stderr)
        return 2
    h = {"id": hid, "ide": a.ide, "trigger": a.trigger, "enabled": True, "created": now(), "fired": 0, "inject": inject}
    if a.package:
        pkg_dir(hid).mkdir(parents=True, exist_ok=True)
    if a.entry:
        h["entry"] = a.entry
    if a.capture or a.capture_only:
        h["capture"] = True
    if a.capture_only:
        h["capture_only"] = True
    if (a.cmd or "").strip():
        h["cmd"] = a.cmd.strip()
    if a.trigger == "fn":
        h["fn"] = a.fn
    elif a.trigger == "keyword":
        words = [w.strip() for w in re.split(r"[,，\s]+", a.keywords or "") if w.strip()]
        if not words:
            print("hook: --keywords required", file=sys.stderr)
            return 2
        h["keywords"], h["match"] = words, a.match
    else:
        if not a.key:
            print("hook: --key required", file=sys.stderr)
            return 2
        KEYS.mkdir(parents=True, exist_ok=True)
        src = Path(a.key)
        if src.exists():
            (KEYS / (hid + ".md")).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        elif not (KEYS / a.key).exists():
            print("hook: no such key %s" % a.key, file=sys.stderr)
            return 2
        h["key"], h["threshold"] = hid + ".md", float(a.threshold)
    save_rule(h)
    ensure_registered(a.ide)
    where = "data/hooks/%s/inject.md" % hid if a.package else "data/inject/%s.md" % hid
    print("+ %-16s %-3s %s\n  inject %s (%dB)" % (
        hid, {"keyword": "kw", "sim": "sim", "fn": "fn"}[h["trigger"]],
        (",".join(h["keywords"]) if h["trigger"] == "keyword"
         else "fn=%s" % h.get("fn", "tools") if h["trigger"] == "fn"
         else "key=%s thr=%.2f" % (h["key"], h["threshold"])),
        where, len(inject.encode())))
    return 0


def cmd_set(a):
    h = find(a.id)
    if not h:
        print("hook: no such id %s" % a.id, file=sys.stderr)
        return 3
    if a.inject:
        h["inject"] = Path(a.inject[1:]).read_text(encoding="utf-8") if a.inject.startswith("@") else a.inject
    if a.cmd is not None:
        h["cmd"] = a.cmd.strip()
    if a.keywords is not None:
        h["keywords"] = [w.strip() for w in re.split(r"[,，\s]+", a.keywords) if w.strip()]
        h["trigger"] = "keyword"
    if a.threshold is not None:
        h["threshold"] = float(a.threshold)
        h["trigger"] = "sim"
    save_rule(h)
    print("= %s" % a.id)
    return 0


def cmd_rm(a):
    n = 0
    for hid in a.id:
        if find(hid):
            drop_rule(hid)
            n += 1
    drop_entry_when_empty()
    print("- %d" % n)
    return 0


def cmd_onoff(a, state):
    n = 0
    for h in load_rules():
        if not a.id or h["id"] in a.id:
            h["enabled"] = state
            save_rule(h)
            n += 1
    print("%s %d" % ("on" if state else "off", n))
    return 0


def cmd_list(a):
    rules = load_rules()
    if not rules:
        print("hook: none")
        return 0
    print(pad("ID",18)+pad("T",4)+pad("CONDITION",36)+pad("BYTES",7)+pad("FIRED",7)+"ON")
    for h in rules:
        cond = (",".join(h.get("keywords", [])) if h["trigger"] == "keyword"
                else "fn=%s" % h.get("fn", "tools") if h["trigger"] == "fn"
                else "key=%s thr=%.2f" % (h.get("key"), h.get("threshold", 0)))
        print(pad(h["id"],18)+pad({"keyword":"kw","sim":"sim","fn":"fn"}[h["trigger"]],6)+pad(cond[:34],36)
              +pad(len(h.get("inject","").encode()),7)+pad(h.get("fired",0),7)+("+" if h["enabled"] else "-"))
    return 0


def read_payload():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        return raw, {}
    for k in ("prompt", "message", "text", "content"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return v, data
    return "", data


def run_prompt():
    try:
        prompt, _ = read_payload()
        if not prompt:
            return 0
        hits = evaluate(prompt, load_rules())
        if not hits:
            return 0
        blocks = []
        for h, s, why in hits:
            if h.get("capture"):
                capture_prompt(h["id"], prompt, why)
            if h.get("auto_instance"):
                text = auto_instance_text(h["id"], prompt,
                                          ", ".join(x["id"] for x, _, _ in hits))
                if text:
                    blocks.append(cmd_block(h["id"], "instance " + h.get("instance_name", ""), text))
                continue
            if not str(h.get("inject", "")).strip():
                continue          # capture-only rule: the prompt is kept, nothing is injected
            blocks.append(cmd_block(h["id"], why, h["inject"]))
            h["fired"] = h.get("fired", 0) + 1
            h["last"] = now()
            save_rule(h)
        log("fire\t%s" % ",".join(h["id"] for h, _, _ in hits))
        text = "\n\n".join(blocks)
        log_inject(",".join(h["id"] for h, _, _ in hits), text)
        sys.stdout.write(text + "\n")
    except Exception as exc:
        log("error\t%s" % exc)
    return 0


def dispatch(hid: str, rest: list) -> int | None:
    """`hook <id> <args>` runs the package's own module, so a rule can own a state machine."""
    h = find(hid)
    if not h or not h.get("entry"):
        return None
    d = pkg_dir(hid)
    mod_path = d / h["entry"]
    if not mod_path.exists():
        mod_path = ROOT / h["entry"]      # shipped code lives beside hook.py
    if not mod_path.exists():
        print("hook: %s: entry %s missing" % (hid, h["entry"]), file=sys.stderr)
        return 2
    import importlib.util
    spec = importlib.util.spec_from_file_location("hook_pkg_%s" % hid, mod_path)
    mod = importlib.util.module_from_spec(spec)
    mod.__dict__["HOOK_DATA"] = DATA
    spec.loader.exec_module(mod)
    return mod.main(rest, DATA)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("add", "set", "rm", "on", "off", "list", "-h", "--help"):
        rc = dispatch(argv[0], argv[1:])
        if rc is not None:
            return rc
    if not argv or argv[0] not in ("add", "set", "rm", "on", "off", "list", "-h", "--help"):
        return run_prompt()          # bare `hook`: the IDE calls this with the payload

    p = argparse.ArgumentParser(prog="hook", description="keyword / similarity / skill triggered context injection")
    sub = p.add_subparsers(dest="cmd")
    d = sub.add_parser("add")
    d.add_argument("--id", required=True); d.add_argument("--ide", default="codebuddy")
    d.add_argument("--trigger", default="keyword", choices=["keyword", "sim", "fn"])
    d.add_argument("--fn", default="tools", help="predicate name, e.g. tools")
    d.add_argument("--keywords"); d.add_argument("--match", default="any", choices=["any", "all"])
    d.add_argument("--key"); d.add_argument("--threshold", default=0.55)
    d.add_argument("--inject", default=""); d.add_argument("--cmd")
    d.add_argument("--package", action="store_true", help="write data/hooks/<id>/ (hook.json + inject.md + code)")
    d.add_argument("--entry", default="", help="module in the package that `hook <id> ...` dispatches to")
    d.add_argument("--capture", action="store_true", help="keep the last prompt that fired")
    d.add_argument("--capture-only", action="store_true", help="capture the prompt and inject nothing")
    d.set_defaults(f=cmd_add)
    d = sub.add_parser("set"); d.add_argument("id"); d.add_argument("--inject"); d.add_argument("--cmd"); d.add_argument("--keywords"); d.add_argument("--threshold"); d.set_defaults(f=cmd_set)
    d = sub.add_parser("rm"); d.add_argument("id", nargs="+"); d.set_defaults(f=cmd_rm)
    d = sub.add_parser("on"); d.add_argument("id", nargs="*"); d.set_defaults(f=lambda a: cmd_onoff(a, True))
    d = sub.add_parser("off"); d.add_argument("id", nargs="*"); d.set_defaults(f=lambda a: cmd_onoff(a, False))
    d = sub.add_parser("list"); d.set_defaults(f=cmd_list)
    a = p.parse_args(argv)
    if not getattr(a, "f", None):
        p.print_help()
        return 2
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
