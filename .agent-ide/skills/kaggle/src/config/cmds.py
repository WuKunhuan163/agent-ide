"""``config`` group: parse registration + command body."""
from __future__ import annotations

import argparse
import json
import os
import sys

from src import identity, kaggle_exec
from src.config.config import (
    gpu_interlock_enabled,
    load_config,
    save_config,
    set_gpu_interlock,
)
from src.exit_codes import AUTH_TOKEN_MISSING, OK
from src.paths import require_ctx


def sync_replicas() -> None:
    """Ask agent-ide to copy the token pool into the shard it manages.

    Best effort: a failed copy must never undo a successful registration.
    """
    skill_dir = require_ctx().skill_dir
    project = os.path.dirname(os.path.dirname(os.path.dirname(skill_dir)))
    sys.path.insert(0, os.path.join(project, ".agent-ide", "skills", "agent-ide"))
    try:
        from replicas import ReplicaError, Replicator
    except ImportError as exc:
        print(f"kaggle: replica sync skipped: {exc}", file=sys.stderr)
        return
    try:
        Replicator.for_skill(skill_dir).sync_quietly()
    except ReplicaError as exc:
        print(f"kaggle: replica sync skipped: {exc}", file=sys.stderr)


def register_config(groups) -> None:
    config = groups.add_parser(
        "config", help="inspect or change this agent's account binding"
    )
    config.add_argument(
        "--status", action="store_true", help="show the bound account and available accounts"
    )
    config.add_argument(
        "--username",
        metavar="<kaggle_user>",
        help="record the Kaggle username for this agent (no token check)",
    )
    config.add_argument(
        "--switch-user",
        dest="switch_user",
        metavar="<kaggle_user>",
        help="bind this agent to an account that already has a token",
    )
    config.add_argument(
        "--token-file",
        dest="token_file",
        metavar="<path>",
        help="register a downloaded kaggle.json into the shared token pool",
    )
    config.add_argument(
        "--verify", action="store_true", help="probe the Kaggle API with this agent's token"
    )
    config.add_argument(
        "--gpu-interlock",
        dest="gpu_interlock",
        choices=["on", "off"],
        help=(
            "on (default): API push stays enable_gpu=false and a human picks the accelerator; "
            "off: push with enable_gpu=true so Kaggle starts the run unattended"
        ),
    )


def cmd_config(args: argparse.Namespace) -> int:
    ctx = require_ctx()

    if args.gpu_interlock is not None:
        set_gpu_interlock(args.gpu_interlock == "on")
        state = "on" if gpu_interlock_enabled() else "off"
        print(f"GPU interlock: {state}")
        if state == "off":
            print(
                "  Pushes now send enable_gpu=true, so Kaggle starts the run itself on its "
                "default accelerator (observed: T4 x2) and monitor may poll it. No human step."
            )
        else:
            print(
                "  Pushes send enable_gpu=false (anti-P100) and the human selects the "
                "accelerator, then Run All."
            )
        return OK

    if args.status:
        config = load_config()
        available = identity.list_accounts()
        bound = config.get("username")
        select_from = ", ".join(available) or "(none)"
        print(f"agent_id:   {ctx.agent_id}")
        print(f"account:    {bound or '(unbound)'}  select from: {select_from}")
        print(f"token:      {'ok' if bound and identity.has_token(bound) else 'missing'}")
        print(f"interlock:  {'on' if gpu_interlock_enabled() else 'off'}")
        return OK

    if args.verify:
        username, token = identity.credentials()
        kaggle_exec.verify_credentials(username, token)
        print(f"Credentials for '{username}' accepted by the Kaggle API.")
        return OK

    if args.switch_user:
        if not identity.has_token(args.switch_user):
            raise identity.IdentityError(
                AUTH_TOKEN_MISSING, identity.token_missing_message(args.switch_user)
            )
        identity.bind(args.switch_user)
        print(f"Bound agent '{ctx.agent_id}' to Kaggle account '{args.switch_user}'.")
        return OK

    if args.username:
        config = load_config()
        config["username"] = args.username
        save_config(config)
        print(f"Recorded username: {args.username}")
        if not identity.has_token(args.username):
            print(
                f"Note: no token registered for '{args.username}' yet — "
                "commands using it will fail until you run config --token-file <kaggle.json>.",
                file=sys.stderr,
            )
        return OK

    if args.token_file:
        username = identity.register_token(args.token_file)
        identity.bind(username)
        print(f"Registered token for '{username}' -> {identity.token_path(username)}")
        sync_replicas()
        print(f"Bound agent '{ctx.agent_id}' to '{username}'.")
        print(
            "Note: live verification against the Kaggle API happens on first "
            "command that calls it (no network call here)."
        )
        return OK

    print(f"agent_id: {ctx.agent_id}")
    config = load_config()
    print(json.dumps(config, indent=4, ensure_ascii=False))
    bound = config.get("username")
    if bound and identity.has_token(bound):
        print(f"account:  {bound} ({identity.token_path(bound)})")
    else:
        print("account:  (unbound)  -> config --token-file <kaggle.json>")
    return OK
