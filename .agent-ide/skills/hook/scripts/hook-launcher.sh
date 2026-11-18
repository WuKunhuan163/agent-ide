#!/usr/bin/env bash
# agent-ide hook launcher (project-agnostic): runs the hook of the project the prompt
# was typed in, so each project reads its own rules; falls back to the global skill.
set -uo pipefail

_GLOBAL="${AGENT_IDE_GLOBAL:-$HOME/agent_ide_global_project}"
_BIN="$_GLOBAL/.agent-ide/runtime/standalone/python/darwin-arm64/python3.11/bin/python3.11"

# 1) project skill: walk up from the working directory
_find_project() {
  local d="$PWD"
  while [ "$d" != "/" ]; do
    if [ -f "$d/.agent-ide/skills/hook/hook.py" ]; then printf '%s\n' "$d"; return 0; fi
    d="$(dirname "$d")"
  done
  return 1
}

_ENTRY=""
if _PROJ="$(_find_project)"; then
  _ENTRY="$_PROJ/.agent-ide/skills/hook/hook.py"
else
  _ENTRY="$_GLOBAL/.agent-ide/skills/hook/hook.py"
fi

if [ ! -x "$_BIN" ]; then
  echo "agent-ide: interpreter missing: $_BIN" >&2
  exit 0
fi
if [ ! -f "$_ENTRY" ]; then
  exit 0          # no hook skill anywhere: stay silent rather than fail the prompt
fi
exec "$_BIN" "$_ENTRY" "$@"
