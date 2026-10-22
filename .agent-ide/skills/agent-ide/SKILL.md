---
name: agent-ide
description: >-
  Skill package transfer for the agent-ide ecosystem: project <-> global project <-> GitHub, plus launchers and IDE injection.
---

# agent-ide

One engine for four directions:

| Direction | Command |
|---|---|
| project → global | `push <skill> ...` |
| global → project | `push --from-global <skill> ...` |
| global → GitHub | `publish <skill> ...` |
| GitHub → global | `publish --from-github <skill> ...` |

Plus `install` (write launchers) and `inject` (make a package visible to an IDE).

## What a package is

```
.agent-ide/skills/<name>/
├── SKILL.md          always transferred
├── skill.json        always transferred — the whitelist
├── <name>.py         transferred when install.kind is `python`
├── …                 only paths listed in files / directories
└── data/             local state from real use; never declared, never listed
```

`skill.json`:

```json
{"install": {"kind": "python"},
 "python": {"runtime": {"version": "3.11.9"}, "requirements": [], "stdlib": ["tkinter"]},
 "files": ["install.command"],
 "directories": ["src", "tests"]}
```

`replicas` — the disaster-recovery copy of `data/`, declared by the skill that owns the data:

```json
"replicas": {"root": "~/.agent-ide/replicas", "mode": "append_only",
             "include": ["data/contact_msg/**"], "exclude": ["data/**/runtime/**"]}
```

`root` is required and must lie **outside the project**: inside it the copies would be committed to git (leaking replies and tokens) and would be lost with the project. Layout is `<root>/<project>-<hash>/<skill>/<relative path>`; the hash keeps two projects with the same directory name apart. `sync` only ever adds files — an existing copy is never overwritten, and a differing copy is reported as a conflict instead.

`replicas.py` is the public interface, and agent-ide owns the whole mechanism (shard, filters, permissions, append-only rule). A skill only says *when* a copy is due:

```python
sys.path.insert(0, str(project / ".agent-ide" / "skills" / "agent-ide"))
from replicas import Replicator

Replicator.for_skill(pkg_dir).sync_quietly()   # one line, never raises
```

`sync_quietly` prints one stderr line and returns None on failure, so a broken copy cannot undo the work that triggered it. `Replicator.for_skill(pkg).status()` reports the gap without writing; the CLI is a thin wrapper over the same class.

Two rules that cause most failures:

- **A declared path must exist.** `files`/`directories` are checked before every transfer, so a stale entry fails the command instead of shipping a broken package. An empty directory cannot be declared: git does not carry it, so `publish` then `--from-github` would fail on the far side.
- **`data/` is local state, so it cannot be whitelisted.** It is what a skill accumulates while being used — archives, caches, credentials — and it differs per machine and per run, so it can never be enumerated in advance. The whitelist lists what a package *is*; `data/` is what it *has done*. Writers create their own directories when they first write; a read-only command creates nothing.

## Commands

```bash
agent-ide install <skill> ...                    # .agent-tools/<skill> for local packages
agent-ide init-project <path> [skills...]        # pull defaults from global, then install
agent-ide push <skill> ... [--from-global]
agent-ide publish <skill> ... [--from-github]
agent-ide inject <domain> add-skill|remove-skill [skills...]
agent-ide replicas status|sync [skill...]         # append-only copies of data/
```

- `install` reads each package's manifest and writes a launcher. It never fetches packages: `push --from-global` (or `init-project`) first.
- `init-project` pulls `agent-ide`, `contact-user` and `collaboration` as far as the global project has them, then installs and seeds `.gitignore` (only when absent). It does not run `git init`.
- `inject` symlinks `<domain>/skills/<skill>/SKILL.md` → the canonical file, and `remove-skill` deletes only links it owns. `<domain>` is a path inside the project, e.g. `.cursor` or `.codebuddy/skills`; it is created if missing.
- `publish` needs `github.publish_repo` in `.agent-ide/skills/agent-ide/data/config.json` — `owner/repo` (SSH) or any git URL or path. The project's config wins, then the global project's.

## Python runtime contract

`python.runtime.version` picks the interpreter:
`<global>/.agent-ide/runtime/standalone/python/<platform>/python<X.Y>/`, where `<platform>` is e.g. `darwin-arm64` (see `src/paths.py`). If only `<X.Y>.gz` is present, `install` unpacks it there first.

- `requirements` are pip specs. Missing ones are installed into that interpreter and recorded in `.agent-ide-records.json` beside it, so a reinstall is free. No interpreter → exit 54; the system `python3` is never substituted.
- `stdlib` are modules that must import. They cannot be installed, so a miss is a warning.

## Launcher

`install` writes `.agent-tools/<skill>`:

```bash
_TOOLS="$(cd "$(dirname "$(_resolve)")" && pwd)"   # symlink-safe
_ROOT="$(cd "$_TOOLS/.." && pwd)"
exec '<absolute interpreter>' "$_ROOT/.agent-ide/skills/<name>/<name>.py" "$@"
```

The interpreter path is **baked in**: the launcher never parses JSON, and a project move is free. If the global project moves, reinstall — `install` rewrites every launcher, and `install.command` is the entry that works even when no launcher does.

## First start and repair

`install.command` installs agent-ide itself with a system `python3` (≥3.10); it works before `.agent-tools/` exists and needs nothing else:

```bash
bash <project>/.agent-ide/skills/agent-ide/install.command
```

With no ecosystem on the machine, the package itself comes from the publish repo — clone it as the global project, then bootstrap:

```bash
git clone <publish repo> <global>
bash <global>/.agent-ide/skills/agent-ide/install.command
<global>/.agent-tools/agent-ide init-project <project>
```

A bundled runtime under `<global>/.agent-ide/runtime/` is optional: when a package declares no `requirements`, `install` falls back to the interpreter running it and says which one in one stderr line. Packages with requirements still need the runtime archive.

The full cold-start order (bootstrap branch, global project pointer, agent id, contact loop) lives in `contact-user/COLDSTART.md`; do not duplicate it here.

`paths.global_home` semantics: valid when the path holds `.agent-ide/skills`. Absent means this project is its own global project — a normal shape, not a defect. `init-project` inherits the launcher's value and replaces only an absent, invalid or self-referential one.

## Exit codes

| Code | Meaning |
|---|---|
| 2 | argparse: unknown command / missing argument |
| 10 | no `.agent-ide/skills` above the script |
| 20 | `paths.global_home` missing or invalid |
| 40 | package problem: missing manifest, declared path, or skill directory |
| 50 | install failure (unsupported `install.kind`, missing entry) |
| 51 | `install` called without skill names |
| 52 | inject failure (bad domain, unknown skill) |
| 54 | python dependency failure (no interpreter, pip failed, unpack failed) |
| 55 | publish failure (no repo, clone/commit/push failed) |

Errors print one line: `agent-ide: <what failed>`.

## Tests

```bash
cd .agent-ide/skills/agent-ide && python3 -m unittest discover -s tests -t tests
```

Hermetic: temporary projects, a shell shim as the runtime, and a local bare repository standing in for GitHub.
