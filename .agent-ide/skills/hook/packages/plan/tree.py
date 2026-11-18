"""The plan tree as objects: Store finds instances, Tree owns nodes, Node owns a state.

`plan.py` keeps the CLI; nothing here parses arguments or prints. The rule object
(`plan.Rule`) talks to `Store`/`Tree`, so the tree's behaviour lives in classes instead
of a thousand lines of module functions.
"""
import json
import shutil
from pathlib import Path

OPEN = ("pending", "active")


def now() -> str:
    import datetime as _d
    return _d.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


class Node:
    """One item: its own state machine, with the transitions that are legal."""

    def __init__(self, data: dict):
        self.data = data

    # ---- identity -------------------------------------------------------
    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def state(self) -> str:
        return self.data.get("state", "pending")

    @property
    def root(self) -> bool:
        return bool(self.data.get("root"))

    @property
    def criterion(self) -> str:
        return self.data.get("criterion") or ""

    @property
    def context(self) -> str:
        return self.data.get("context") or ""

    @property
    def title(self) -> str:
        return self.data.get("title") or ""

    # ---- transitions ----------------------------------------------------
    def start(self):
        if self.state not in OPEN:
            raise ValueError("%s 当前 %s，不能 start" % (self.id, self.state))
        self.data["state"] = "active"
        self.data["started"] = now()

    def done(self, note: str):
        if self.state == "pending":
            raise ValueError("%s 还没 start：先 `hook plan start %s`" % (self.id, self.id))
        if self.state != "active":
            raise ValueError("%s 当前 %s，不能 done" % (self.id, self.state))
        self.data["state"] = "done"
        self.data["note"] = note
        self.data["done_at"] = now()

    def ack(self, recheck: str):
        if self.state != "done":
            raise ValueError("%s 当前 %s：只有 done 过的项才能 ack" % (self.id, self.state))
        self.data["state"] = "ack"
        self.data["recheck"] = recheck
        self.data["ack_at"] = now()

    def drop(self):
        if self.state in ("done", "ack"):
            raise ValueError("%s 已完成或已确认，不许剪" % self.id)
        self.data["state"] = "dropped"


class Tree:
    """An instance: the prompt as its only root, everything else underneath."""

    def __init__(self, path: Path, data: dict):
        self.path = path
        self.data = data

    # ---- loading --------------------------------------------------------
    @classmethod
    def at(cls, directory: Path) -> "Tree":
        f = directory / "tree.json"
        return cls(directory, json.loads(f.read_text(encoding="utf-8")))

    def save(self):
        (self.path / "tree.json").write_text(
            json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- structure ------------------------------------------------------
    @property
    def instance(self) -> str:
        return self.data["instance"]

    @property
    def state(self) -> str:
        return self.data["state"]

    @property
    def prompt(self) -> str:
        return self.data.get("prompt", "")

    @property
    def nodes(self) -> list:
        return self.data["nodes"]

    def node(self, nid: str):
        for n in self.nodes:
            if n["id"] == nid:
                return Node(n)
        return None

    def children(self, nid) -> list:
        return [n for n in self.nodes if (n.get("parent") or None) == nid]

    def counts(self) -> dict:
        out = {"pending": 0, "active": 0, "done": 0, "ack": 0, "dropped": 0}
        for n in self.nodes:
            out[n["state"]] = out.get(n["state"], 0) + 1
        return out

    def bare_root(self) -> bool:
        return any(n.get("root") and not self.children(n["id"]) for n in self.nodes)

    def has_open_descendant(self, nid: str) -> bool:
        for k in self.children(nid):
            if k["state"] in OPEN or self.has_open_descendant(k["id"]):
                return True
        return False

    def deps_done(self, n: dict) -> bool:
        for a in n.get("after") or []:
            x = self.node(a)
            if x is not None and x.state not in ("done", "ack", "dropped"):
                return False
        return True

    def first_open(self):
        """DFS: the first pending leaf whose deps are done; a parent waits for its children."""
        for n in self.nodes:
            if n["state"] != "pending" or not self.deps_done(n):
                continue
            if self.has_open_descendant(n["id"]):
                continue
            if n.get("root") and not self.children(n["id"]):
                continue          # 根还没拆：下一步是拆，不是 start
            return Node(n)
        return None

    def after(self, node: Node) -> list:
        """Siblings still open, in order: what the agent will pick up next."""
        return [n for n in self.children(node.data.get("parent"))
                if n["id"] != node.id and n["state"] in OPEN]


class Store:
    """Where instances live: one directory each, under the rule's own data space."""

    def __init__(self, data: Path):
        self.data = Path(data)

    @property
    def root(self) -> Path:
        return self.data / "plan" / "data" / "instance"

    def instances(self) -> list:
        if not self.root.exists():
            return []
        return [p.parent for p in self.root.glob("*/tree.json")]

    def open_tree(self):
        """The pointer: a not-done instance, newest first; None when nothing is open."""
        live = [p for p in self.instances() if p.exists()]
        if not live:
            return None

        def rank(p: Path):
            try:
                t = json.loads((p / "tree.json").read_text(encoding="utf-8"))
                return (t.get("state") != "done", (p / "tree.json").stat().st_mtime)
            except Exception:
                return (False, 0)

        return Tree.at(max(live, key=rank))

    def sweep_bare(self) -> int:
        """Undecomposed roots are not work: delete them before allocating another."""
        n = 0
        for d in self.instances():
            try:
                t = Tree.at(d)
            except Exception:
                continue
            if len(t.nodes) == 1 and t.bare_root():
                shutil.rmtree(d, ignore_errors=True)
                n += 1
        return n

    def allocate(self, name: str, prompt: str, tools: str = "") -> Tree:
        d = self.root / name
        d.mkdir(parents=True, exist_ok=True)
        head = next((l.strip() for l in prompt.split("\n") if l.strip()), "原话")
        t = Tree(d, {
            "instance": name, "created": now(), "state": "build", "summary": head[:60],
            "prompt": prompt, "tools": tools,
            "nodes": [{"id": "n1", "title": head[:60], "parent": None, "after": [],
                       "context": "原话全文见 tree.json 的 prompt；这一项就是它",
                       "criterion": "这条 prompt 的每条要求都有子节点，且子节点全部 done/ack/dropped",
                       "state": "pending", "note": "", "added": now(), "root": True}],
            "rounds": [{"n": 1, "opened": now()}], "closed": None})
        t.save()
        return t
