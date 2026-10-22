#!/usr/bin/env python3
"""
huggingface - per-agent token store and a zero-dependency file downloader.

Output contract (same as crossref / arxiv):
  stdout  the result only, one line, tab separated
  stderr  progress, warnings, failures
"""
import argparse
import json
import os
import sys

import requests

# Path Resolution
_env_skill = os.environ.get("AGENT_IDE_SKILL_DIR", "").strip()
if _env_skill:
    SKILL_DIR = os.path.realpath(_env_skill)
elif getattr(sys, "frozen", False):
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    SKILL_DIR = next(
        (
            p
            for p in (
                os.path.abspath(os.path.join(exe_dir, "..", ".agent-ide", "skills", "huggingface")),
                os.path.abspath(os.path.join(exe_dir, "..", ".cursor", "skills", "huggingface")),
            )
            if os.path.isdir(p)
        ),
        os.path.abspath(os.path.join(exe_dir, "..", ".agent-ide", "skills", "huggingface")),
    )
else:
    # main.py lives in src/, so the skill root is one level up; the archived copy
    # had it at the root and wrote credentials into src/data.
    SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AGENT_ID = None
for i, arg in enumerate(sys.argv):
    if arg == "--id" and i + 1 < len(sys.argv):
        AGENT_ID = sys.argv[i + 1]
        sys.argv = sys.argv[:i] + sys.argv[i + 2 :]
        break


def _log(msg):
    print(msg, file=sys.stderr)


if not AGENT_ID or AGENT_ID == "default":
    _log(
        "[hf] missing --id <agent_id>\n"
        "  usage: huggingface --id <agent_id> config --token <tok> | get | download ..."
    )
    sys.exit(1)

DATA_DIR = os.path.join(SKILL_DIR, "data", "accounts", AGENT_ID)
os.makedirs(DATA_DIR, exist_ok=True)
LOCAL_CONFIG_FILE = os.path.join(DATA_DIR, "config.json")


def load_config():
    if os.path.exists(LOCAL_CONFIG_FILE):
        try:
            with open(LOCAL_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {}


def save_config(config):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LOCAL_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    os.chmod(LOCAL_CONFIG_FILE, 0o600)


def _human(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 ** 2:.2f} MB"


def cmd_download(args):
    token = load_config().get("token")
    repo, filename = args.repo, args.file
    revision = args.revision or "main"
    out_dir = os.path.expanduser(args.dir or ".")
    os.makedirs(out_dir, exist_ok=True)

    url = f"https://huggingface.co/{repo}/resolve/{revision}/{filename}"
    dest_path = os.path.abspath(os.path.join(out_dir, os.path.basename(filename)))

    headers = {"User-Agent": "HuggingFaceTool/1.0 (mailto:contact@cursor.ai; Academic Helper)"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    total = 0
    downloaded = 0
    _log(f"[hf] {repo}/{filename} @{revision}")
    try:
        with requests.get(url, headers=headers, stream=True, timeout=60) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length") or 0)
            if total:
                _log(f"[hf] {_human(total)} -> {dest_path}")

            with open(dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total and sys.stderr.isatty():
                        pct = downloaded * 100 / total
                        sys.stderr.write(f"\r[hf] {pct:5.1f}%  {_human(downloaded)}")
                        sys.stderr.flush()

        if total and sys.stderr.isatty():
            sys.stderr.write("\r" + " " * 40 + "\r")
            sys.stderr.flush()
        if total and downloaded != total:
            _log(f"[hf] size mismatch: got {downloaded}, expected {total}")
            sys.exit(1)
        _log(f"[hf] ok {_human(downloaded)}")
    except requests.HTTPError as e:
        code = e.response.status_code
        _log(f"[hf] HTTP {code}: {(e.response.text or '')[:200].strip()}")
        sys.exit(1)
    except requests.RequestException as e:
        _log(f"[hf] request failed: {e}")
        sys.exit(1)

    # the only thing worth parsing: where it landed and how big it is
    print(f"{dest_path}\t{downloaded}")


def main():
    parser = argparse.ArgumentParser(description="Hugging Face token store and file downloader")
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config", help="store the access token for this agent")
    config_parser.add_argument("--token", type=str, required=True)

    subparsers.add_parser("get", help="print the stored token")

    download_parser = subparsers.add_parser("download", help="download one file from a repo")
    download_parser.add_argument("--repo", required=True, help="e.g. gpt2")
    download_parser.add_argument("--file", required=True, help="e.g. config.json")
    download_parser.add_argument("--revision", default="main")
    download_parser.add_argument("--dir", "-d", help="output directory (default: .)")

    args = parser.parse_args()
    if args.command == "config":
        config = load_config()
        config["token"] = args.token
        save_config(config)
        print(LOCAL_CONFIG_FILE)
    elif args.command == "get":
        config = load_config()
        if not config.get("token"):
            _log(f"[hf] no token for '{AGENT_ID}'; set it with: huggingface --id {AGENT_ID} config --token <tok>")
            sys.exit(1)
        print(config["token"])
    elif args.command == "download":
        cmd_download(args)


if __name__ == "__main__":
    main()
