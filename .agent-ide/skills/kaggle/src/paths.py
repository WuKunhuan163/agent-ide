from __future__ import annotations
import os, sys
from dataclasses import dataclass
from src.exit_codes import INPUT_MISSING_ID

ctx: "Paths | None" = None

@dataclass(frozen = True)
class Paths:
    skill_dir: str
    agent_id: str
    data_dir: str
    accounts_dir: str
    agent_dir: str
    config_file: str
    state_file: str
    notebooks_dir: str
    runtime_dir: str
    runtime_deploy_dir: str
    runtime_output_dir: str
    runtime_logs_dir: str
    event_log_file: str

def bootstrap(argv: list[str]) -> list[str]:
    """Resolve `--id` and the paths under `data/`; create nothing.

    `data/` is runtime state, not package content, so it appears only when
    something is actually written: `save_config`, the runtime store and the
    token pool each make their own directory. A read-only command, or a typo in
    `--id`, must not leave an empty agent directory behind.
    """
    global ctx
    agent_id: str | None = None
    rest: list[str] = []
    i = 0
    while (i < len(argv)):
        if argv[i] == "--id" and i + 1 < len(argv):
            agent_id = argv[i + 1]
            i += 2
            continue
        rest.append(argv[i])
        i += 1
    if not agent_id:
        print("Error: --id <agent_id> is required. ", file=sys.stderr)
        raise SystemExit(INPUT_MISSING_ID)

    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(skill_dir, "data")
    agent_dir = os.path.join(data_dir, "agents", agent_id)
    runtime_dir = os.path.join(agent_dir, "runtime")
    ctx = Paths(
        skill_dir=skill_dir,
        agent_id=agent_id,
        data_dir=data_dir,
        accounts_dir=os.path.join(data_dir, "accounts"),
        agent_dir=agent_dir,
        config_file=os.path.join(agent_dir, "config.json"),
        state_file=os.path.join(agent_dir, "state.json"),
        notebooks_dir=os.path.join(agent_dir, "notebooks"),
        runtime_dir=runtime_dir,
        runtime_deploy_dir=os.path.join(runtime_dir, "deploy"),
        runtime_output_dir=os.path.join(runtime_dir, "output"),
        runtime_logs_dir=os.path.join(runtime_dir, "logs"),
        event_log_file=os.path.join(agent_dir, "event_log.json"),
    )
    return rest

def resolve_arg(raw) -> str:
    """A path typed on a command line: relative to the project root, never cwd.

    `--dir notebooks/x` means the same directory no matter where the shell
    stands.  Absolute paths pass through untouched; without a project root
    (a package run outside any project) cwd is the only remaining answer.
    """
    path = os.path.expanduser(str(raw))
    if os.path.isabs(path):
        return path
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    while True:
        if os.path.isdir(os.path.join(here, ".agent-tools")):
            return os.path.join(here, path)
        parent = os.path.dirname(here)
        if parent == here:
            return os.path.abspath(path)
        here = parent


def require_ctx() -> Paths:
    if ctx is None:
        raise RuntimeError("thin entry: python3 .agent-ide/skills/kaggle/kaggle.py --id <agent_id> <cmd>")
    return ctx
