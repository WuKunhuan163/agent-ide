#!/bin/bash
# Bootstrap agent-ide itself: needs nothing but a system python3 and this file.
# Works when .agent-tools/ is absent or its launcher is broken.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

pick_python() {
    for candidate in ${PYTHON_CMD:-} python3.12 python3.11 python3.10 python3; do
        command -v "$candidate" >/dev/null 2>&1 || continue
        if "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' 2>/dev/null; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

PYTHON="$(pick_python)" || {
    echo "agent-ide: python >= 3.10 not found (set PYTHON_CMD to point at one)" >&2
    exit 1
}
exec "$PYTHON" "$SKILL_DIR/agent-ide.py" install agent-ide
