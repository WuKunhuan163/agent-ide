"""conduct rule: the basic conduct text goes in on every prompt, unconditionally.

Trigger is `fn`, not a keyword: nothing about conduct should depend on whether the
prompt happens to contain 行为准则 or 越界即停.
"""
from pathlib import Path


class Rule:
    id = "agents-conduct"
    trigger = "fn"
    fn = "conduct"

    def __init__(self, data=None):
        self.data = Path(data) if data else None

    def match(self, prompt: str) -> bool:
        return True

    def inject(self, prompt: str = "") -> str:
        p = self.data / self.id / "inject.md" if self.data else Path(__file__).with_name("inject.md")
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def dispatch(self, argv: list) -> int:
        text = self.inject(" ".join(argv))
        if text:
            print(text)
        return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(Rule(Path(__file__).parents[1]).dispatch(sys.argv[1:]))
