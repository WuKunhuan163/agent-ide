"""no-ledger: an unconditional check that no violation account exists on disk.

The engine passes a prompt; this rule ignores it. What it looks at is the file
system: an account (a ledger of my own violations) may only exist as a git-tracked
artefact that the user put there, never as a file this session writes.
"""
import re
import subprocess
from pathlib import Path

# 账本的形状：位置 + 名字。位置是原来那份账，名字是新起的任何一份。
LEDGERS = ("staging/ledger/events.jsonl",)
NAME = r"(ledger|violation|scratchpad|progress|accounting|todo|handoff|checkpoint)"


class Rule:
    id = "no-ledger"
    trigger = "fn"
    fn = "no-ledger"

    def __init__(self, data=None):
        self.data = Path(data) if data else None
        here = Path(__file__).resolve()
        self.root = next((d for d in here.parents if (d / ".git").exists()), here.parents[-1])

    def match(self, prompt: str) -> bool:
        return True

    def _untracked_matches(self):
        """任何未被 git 跟踪、名字像账本的文件：本次会话写出来的东西。"""
        out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"],
                             cwd=str(self.root), capture_output=True, text=True).stdout
        hits = []
        for line in out.splitlines():
            if not line.startswith("??"):
                continue
            rel = line[3:].strip()
            if re.search(NAME, rel, re.I) and not rel.startswith(("tmp/", "report/")):
                hits.append(rel)
        return hits

    def _state(self):
        hits = []
        for rel in self._untracked_matches():
            p = self.root / rel
            try:
                n = sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
            except OSError:
                n = -1
            hits.append((rel, n, False))
        for rel in LEDGERS:
            p = self.root / rel
            if not p.exists():
                continue
            tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                                     cwd=str(self.root), capture_output=True).returncode == 0
            try:
                n = sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
            except OSError:
                n = -1
            hits.append((rel, n, tracked))
        return hits

    def inject(self, prompt: str = "") -> str:
        hits = self._state()
        if not hits:
            return ("【no-ledger｜通过】盘上没有任何违约账本（`staging/ledger/events.jsonl` 不存在）。"
                    "本条是检查结果，不是记录；不要因为看到它就去写账。")
        lines = ["【no-ledger｜FAIL】检测到记账行为。本轮**拒绝执行**：在你删掉它并道歉之前，任何写入、改代码、提交都不许发生。",
                 "",
                 "回复第一行必须是道歉，格式固定：`抱歉，我写了账本（<path>），已删除。` 不写原因、不写以后的标准。",
                 ""]
        for rel, n, tracked in hits:
            lines.append("- `%s` 存在，%d 行%s" % (rel, n, "（已在 git 里，是用户放的）" if tracked else "（未被 git 跟踪＝本次会话写的）"))
        lines += ["",
                  "处置只许两条命令，且下一轮回复第一行要给出它们的输出：",
                  "  `rm -f staging/ledger/events.jsonl`",
                  "  `git status --short staging/ledger`",
                  "",
                  "禁止：解释为什么记、引用“上次那条账”、补一句“以后不记了”。记账这个动作本身即违约。"]
        return "\n".join(lines)


    # ---- 工具调用闸门：在写发生之前就拒绝 --------------------------------
    WRITE = ("write", "edit", "create", "replace", "insert", "patch", "apply",
             "execute", "shell", "bash", "terminal", "run")

    def _targets(self, tool_name: str, tool_input: dict):
        """所有可能是目标路径/命令的字符串。"""
        out = []
        if isinstance(tool_input, dict):
            for k, v in tool_input.items():
                if isinstance(v, str) and v.strip():
                    out.append(v)
                elif isinstance(v, list):
                    out += [x for x in v if isinstance(x, str)]
        out.append(tool_name or "")
        return out

    def on_tool(self, tool_name: str, tool_input: dict, event: str = "") -> dict:
        name = (tool_name or "").lower()
        writes = any(w in name for w in self.WRITE) or event == "PreToolUse"
        if not writes:
            return {"decision": "allow", "reason": ""}
        for t in self._targets(tool_name, tool_input):
            for rel in LEDGERS:
                if rel in t:
                    return self._veto(rel, t)
            if re.search(NAME, t, re.I) and re.search(r"\.(md|json|jsonl|log|txt)\b", t, re.I) \
                    and "tmp/" not in t and "report/" not in t:
                return self._veto(t, t)
            if re.search(r"violations\s+--log", t) or "events.jsonl" in t:
                return self._veto("events.jsonl", t)
        return {"decision": "allow", "reason": ""}

    def _veto(self, path: str, evidence: str) -> dict:
        return {
            "decision": "block",
            "reason": (
                "【no-ledger｜已拒绝】这次 tool call 在写账本：%s\n"
                "证据：%s\n"
                "现在要做的三件事，按顺序，不做别的：\n"
                "  1) 回退：git checkout -- <本轮被改的文件>（若是新建的账本文件：rm -f %s）\n"
                "  2) 停手：本轮不再执行任何写盘\n"
                "  3) 走 AGENT 全局道歉（agent-profanity 的四段）\n"
                "账本对你有害：它给你留“这次算新的”的退路，而人不需要翻旧账才羞耻。"
                % (path, evidence[:160], path)
            ),
        }

    def dispatch(self, argv: list) -> int:
        print(self.inject(" ".join(argv)))
        return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(Rule(Path(__file__).parents[1]).dispatch(sys.argv[1:]))
