#!/usr/bin/env python3
"""aliyunpan — a resumable transfer channel to Aliyun Drive.

The command surface is deliberately small, one verb per intent:

    login                    authorize this agent id (opens a browser)
    who                      show account, backup drive and token expiry
    ls <path>                list one remote folder
    upload <local...> <dir>  upload files or folders, never overwriting
    download <remote> <dir>  download one file
    mkdir <path>             create a folder, and its parents
    rm <path>                delete one file or folder
    mv <path> <dir>          move into an existing folder

Everything except `login` is non-interactive and prints either a table or one
JSON object; diagnostics go to stderr, so a caller can pipe stdout safely.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src import remote, scheduler, transfer
from src.errors import NotFound, PanError, UsageError
from src.login import login
from src.paths import pretty, resolve_arg
from src.session import Session


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    try:
        return _run(args)
    except PanError as exc:
        print(f"aliyunpan: {exc.message}", file=sys.stderr)
        return exc.code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aliyunpan", description=__doc__.splitlines()[0])
    parser.add_argument("--id", dest="agent_id", required=True, help="agent id; owns the login and resume state")
    parser.add_argument("--json", dest="as_json", action="store_true", help="one JSON object on stdout")
    sub = parser.add_subparsers(dest="command")

    p_login = sub.add_parser("login", help="authorize and store credentials")
    p_login.add_argument("--terminal", action="store_true",
                         help="ask in the terminal instead of opening the login window")
    sub.add_parser("who", help="show the stored account and drive")

    p_ls = sub.add_parser("ls", help="list a remote folder")
    p_ls.add_argument("path", nargs="?", default="/")

    p_up = sub.add_parser("upload", help="upload files or folders")
    p_up.add_argument("sources", nargs="+", help="local paths, then the remote directory")
    p_up.add_argument("--bs", type=int, default=0,
                      help="chunk size in KB; 0 follows the measured speed")
    p_up.add_argument("-p", "--parallel", type=int, default=10,
                      help="concurrent chunks across files (default 10)")

    p_down = sub.add_parser("download", help="download one file")
    p_down.add_argument("source", help="remote file path")
    p_down.add_argument("dest", help="local directory")
    p_down.add_argument("--force", action="store_true", help="replace an existing local file")

    p_mkdir = sub.add_parser("mkdir", help="create a folder and its parents")
    p_mkdir.add_argument("path")

    p_rm = sub.add_parser("rm", help="delete a file or folder")
    p_rm.add_argument("path")

    p_mv = sub.add_parser("mv", help="move into a folder")
    p_mv.add_argument("path")
    p_mv.add_argument("dest")
    return parser


def _run(args) -> int:
    if args.command == "login":
        result = login(args.agent_id, terminal=args.terminal)
        print(json.dumps(result, ensure_ascii=False) if args.as_json else f"OK login {args.agent_id}")
        return 0

    session = Session(args.agent_id)
    if args.command == "who":
        return _who(args, session)
    if args.command == "ls":
        return _ls(args, session)
    if args.command == "upload":
        return _upload(args, session)
    if args.command == "download":
        result = transfer.download(session, args.source, args.dest, force=args.force)
        return _emit(args, result, f"OK download {result['file']} ({pretty(result['bytes'])})")
    if args.command == "mkdir":
        body = remote.mkdir(session, args.path)
        return _emit(args, {"created": args.path, "file_id": body.get("file_id")}, f"OK mkdir {args.path}")
    if args.command == "rm":
        remote.delete(session, args.path)
        return _emit(args, {"deleted": args.path}, f"OK rm {args.path}")
    if args.command == "mv":
        body = remote.move(session, args.path, args.dest)
        return _emit(args, {"moved": args.path, "to": args.dest, "file_id": body.get("file_id")},
                     f"OK mv {args.path} -> {args.dest}")
    raise UsageError(f"unknown command {args.command!r}")


def _who(args, session: Session) -> int:
    payload = {"id": session.agent_id, "drive": session.drive_id, "token": session.token[:6] + "…"}
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"id      {payload['id']}")
        print(f"drive   {payload['drive']}")
        print(f"token   {payload['token']}")
    return 0


def _ls(args, session: Session) -> int:
    folder = remote.stat(session, args.path)
    if folder.get("type") != "folder":
        print(f"{pretty(int(folder.get('size') or 0))}\t{folder.get('name')}")
        return 0
    items = remote.children_of(session, folder)
    if args.as_json:
        print(json.dumps([_item_row(i) for i in items], ensure_ascii=False, indent=2))
        return 0
    for item in sorted(items, key=lambda i: (i.get("type") != "folder", str(i.get("name")))):
        kind = "DIR " if item.get("type") == "folder" else "FILE"
        size = "-" if item.get("type") == "folder" else pretty(int(item.get("size") or 0))
        print(f"{kind}\t{size:>10}\t{item.get('name')}")
    if not items:
        print("(empty)")
    return 0


def _upload(args, session: Session) -> int:
    sources = [resolve_arg(s) for s in args.sources]
    if len(sources) < 2:
        raise UsageError("usage: upload <local...> <remote_dir>")
    destination = str(sources[-1])
    locals_ = sources[:-1]
    if destination.startswith(("/", "~")) is False and not locals_[0].exists():
        raise UsageError("the last argument is the remote directory")
    for path in locals_:
        if not path.exists():
            raise NotFound(f"no such local path: {path}")

    pairs: list[tuple[Path, str]] = []
    for local in locals_:
        if local.is_dir():
            for file in sorted(p for p in local.rglob("*") if p.is_file()):
                relative = file.relative_to(local).parent.as_posix()
                target = destination.rstrip("/") + (f"/{relative}" if relative and relative != "." else "")
                pairs.append((file, target))
        else:
            pairs.append((local, destination))

    # Folders are created once, in order: two workers creating the same path race
    # into a NameTaken that is not a real conflict.
    for _, target in pairs:
        remote.resolve(session, target, create=True)

    # One pool over all files: each thread claims a chunk, and a file never has
    # two chunks in flight, so the threads stay on different files.
    options = scheduler.TransferOptions(
        target_chunk=args.bs * 1024 if args.bs else 0,
        max_threads=max(1, args.parallel),
    )
    uploaded = transfer.upload_many(session, session.agent_id, pairs, options=options)

    total = sum(item["bytes"] for item in uploaded)
    summary = {"uploaded": len(uploaded), "bytes": total, "files": [i["file"] for i in uploaded]}
    return _emit(args, summary, f"OK upload {len(uploaded)} file(s) {pretty(total)} -> {destination}")


def _item_row(item: dict) -> dict:
    return {
        "name": item.get("name"),
        "type": item.get("type"),
        "size": int(item.get("size") or 0),
        "file_id": item.get("file_id"),
        "updated_at": item.get("updated_at"),
    }


def _emit(args, payload: dict, line: str) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.as_json else line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
