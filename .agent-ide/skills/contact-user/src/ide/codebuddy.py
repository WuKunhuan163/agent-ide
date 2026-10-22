"""CodeBuddy's transcript store.

    <history>/                                   <- the pinned root
      <workspace-bucket>/<conversation-id>/
        index.json
        messages/<message-id>.json

A message file is `{"role", "createdAt", "message"}`, where `message` is itself
a JSON *string* holding `content` blocks: `text`, `reasoning`, `tool-call`,
`tool-result`. Unknown block types are ignored, never fatal.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

from .base import Message, SessionStore, ToolCall, ToolResult, parse_ts

BLOCK_KEYS = {
    "text": "text",
    "reasoning": "reasoning",
}


class CodeBuddyStore(SessionStore):
    ide_id = "codebuddy"
    display_name = "CodeBuddy"

    # ----------------------------------------------------------------- layout

    def conversations(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        found: list[Path] = []
        for child in self.root.iterdir():
            if not child.is_dir():
                continue
            if (child / "messages").is_dir():
                found.append(child)
                continue
            try:
                found.extend(
                    grand for grand in child.iterdir()
                    if grand.is_dir() and (grand / "messages").is_dir()
                )
            except OSError:
                continue
        return sorted(found, key=self.last_write_time)

    def message_files(self, conv: Path) -> list[Path]:
        folder = conv / "messages"
        return list(folder.glob("*.json")) if folder.is_dir() else []

    # ---------------------------------------------------------------- parsing

    def parse_file(self, path: Path) -> Message | None:
        try:
            doc = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(doc, dict):
            return None

        body = _decode(doc.get("message"))
        texts: list[str] = []
        thoughts: list[str] = []
        calls: list[ToolCall] = []
        results: list[ToolResult] = []

        for block in body.get("content") or []:
            if isinstance(block, str):
                texts.append(block)
                continue
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind in BLOCK_KEYS:
                (thoughts if kind == "reasoning" else texts).append(str(block.get("text") or ""))
            elif kind == "tool-call":
                args = block.get("args")
                calls.append(
                    ToolCall(
                        name=str(block.get("toolName") or "tool"),
                        args=args if isinstance(args, dict) else {"value": args},
                    )
                )
            elif kind == "tool-result":
                status, text = _result(block.get("result"))
                results.append(
                    ToolResult(
                        name=str(block.get("toolName") or "tool"),
                        is_error=bool(block.get("isError")),
                        status=status,
                        text=text,
                    )
                )

        return Message(
            mid=str(doc.get("id") or path.stem),
            role=str(doc.get("role") or body.get("role") or ""),
            at=parse_ts(doc.get("createdAt")),
            text="\n".join(part for part in texts if part).strip(),
            reasoning="\n".join(part for part in thoughts if part).strip(),
            calls=tuple(calls),
            results=tuple(results),
        )

    # -------------------------------------------------------------- discovery

    @classmethod
    def discover(cls) -> list[Path]:
        roots = [
            Path.home() / "Library" / "Application Support" / "CodeBuddyExtension" / "Data",
            Path.home() / ".config" / "CodeBuddyExtension" / "Data",
            Path.home() / ".local" / "share" / "CodeBuddyExtension" / "Data",
        ]
        if os.environ.get("APPDATA"):
            roots.append(Path(os.environ["APPDATA"]) / "CodeBuddyExtension" / "Data")

        found: list[Path] = []
        for base in roots:
            if not base.is_dir():
                continue
            for history in base.glob("*/CodeBuddyIDE/*/history"):
                if history not in found and cls.validate_root(history):
                    found.append(history)
        return found

    @classmethod
    def setup_hint(cls) -> str:
        return (
            "CodeBuddy keeps one message per file under\n"
            "  <app-data>/CodeBuddyExtension/Data/<install>/CodeBuddyIDE/<install>/history/\n"
            "  history/<workspace-bucket>/<conversation-id>/messages/<message-id>.json\n"
            "Pin the `history` directory itself.\n"
            "Find it with: contact-user --detect-history-root\n"
            "If that finds nothing, the IDE log prints it on every transcript access:\n"
            "  grep 'HistoryService] getTranscriptPathSync result' \\\n"
            "    ~/Library/Application\\ Support/CodeBuddy/logs/*/window*/exthost/*/*.log | tail -1\n"
            "(Linux: ~/.config/CodeBuddy/logs, Windows: %APPDATA%\\CodeBuddy\\logs.)"
        )


def _decode(raw) -> dict:
    """`message` is a JSON string on disk, sometimes already a dict."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {"content": [raw]}
        return decoded if isinstance(decoded, dict) else {"content": [decoded]}
    return {}


def _result(result) -> tuple[str, str]:
    """(status, full text) of a tool-result payload."""
    if isinstance(result, dict):
        status = str(result.get("status") or ("success" if result.get("success") else "?"))
        for key in ("stdout", "output", "text", "message", "error"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return status, value
        inner = result.get("result")
        if isinstance(inner, (dict, list)):
            return status, json.dumps(inner, ensure_ascii=False)
        return status, ""
    if isinstance(result, (list, tuple)):
        return "?", json.dumps(result, ensure_ascii=False)
    return "?", "" if result is None else str(result)
