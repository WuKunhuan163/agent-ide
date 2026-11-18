"""no-ledger: an unconditional check that no violation account exists on disk.

The engine passes a prompt; this rule ignores it. What it looks at is the file
system: an account (a ledger of my own violations) may only exist as a git-tracked
artefact that the user put there, never as a file this session writes.
"""
import subprocess
from pathlib import Path

LEDGERS = ("staging/ledger/events.jsonl",)


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

    def _state(self):
        hits = []
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
        lines = ["【no-ledger｜FAIL】检测到记账行为，本轮判定 fail 并作废：", ""]
        for rel, n, tracked in hits:
            lines.append("- `%s` 存在，%d 行%s" % (rel, n, "（已在 git 里，是用户放的）" if tracked else "（未被 git 跟踪＝本次会话写的）"))
        lines += ["",
                  "处置只许两条命令，且下一轮回复第一行要给出它们的输出：",
                  "  `rm -f staging/ledger/events.jsonl`",
                  "  `git status --short staging/ledger`",
                  "",
                  "禁止：解释为什么记、引用“上次那条账”、补一句“以后不记了”。记账这个动作本身即违约。"]
        return "\n".join(lines)

    def dispatch(self, argv: list) -> int:
        print(self.inject(" ".join(argv)))
        return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(Rule(Path(__file__).parents[1]).dispatch(sys.argv[1:]))
