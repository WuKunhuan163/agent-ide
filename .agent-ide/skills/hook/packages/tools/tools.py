"""tools rule: which installed tools does this prompt name?

The package owns its code and its interface: `class Rule` is constructed by the
engine with the data root, and `inject(prompt)` returns the text to feed. Nothing
about this rule lives in hook.py.
"""
import re
import sys
from pathlib import Path


def project_root() -> Path:
    for p in [Path.cwd()] + list(Path.cwd().parents):
        if (p / ".agent-ide").is_dir() or (p / ".git").is_dir():
            return p
    return Path.cwd()


def _front(skill: Path):
    name = desc = ""
    for line in skill.read_text(encoding="utf-8").split("\n")[:12]:
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("description:"):
            desc = line.split(":", 1)[1].strip()
    return name, desc


def main(argv: list, data=None) -> int:
    """`hook tools <prompt>` and `python3 tools.py <prompt>` both land here."""
    prompt = " ".join(argv) if argv else sys.stdin.read()
    text = Rule(data).inject(prompt)
    if text:
        print(text)
    return 0 if text else 0


class Rule:
    """One class per rule package; the engine instantiates it and calls inject()."""

    id = "tools"
    trigger = "fn"
    fn = "tools"

    def __init__(self, data=None):
        self.data = Path(data) if data else None

    def dispatch(self, argv: list) -> int:
        return main(argv, self.data)

    def inject(self, prompt: str) -> str:
        base = project_root() / ".agent-ide" / "skills"
        tools = project_root() / ".agent-tools"
        names = set()
        if base.exists():
            names |= {d.name for d in base.iterdir() if (d / "SKILL.md").exists()}
        if tools.exists():
            names |= {p.name for p in tools.iterdir() if p.is_file()}
        low = prompt.lower()
        out = []
        for name in sorted(names):
            if not re.search(r"(?<![a-z0-9-])" + re.escape(name.lower()) + r"(?![a-z0-9-])", low):
                continue
            skill = base / name / "SKILL.md"
            if skill.exists():
                _, desc = _front(skill)
                short = re.split(r"(?<=[.。])\s", desc)[0][:110].strip()
                out.append("【%s】先读 %s（%d 行）%s" % (
                    name, skill.relative_to(project_root()),
                    len(skill.read_text(encoding="utf-8").split("\n")),
                    ("：" + short) if short else ""))
            else:
                out.append("【%s】已安装：%s（无 SKILL.md）" % (name, tools / name))
        return "\n".join(out)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
