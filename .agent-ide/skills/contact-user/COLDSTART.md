# Cold start

Work through this order once per new session. `<local>` is the project root (the
directory holding `.agent-tools/`); `<id>` is the agent id.

## 1. Bootstrap — only when the probes say so

Bootstrap rewrites local skill copies, so check before running anything:

```bash
ls -d <local>/.agent-tools/agent-ide <local>/.agent-tools/contact-user <local>/.agent-ide/skills/contact-user
```

| Probe result | Branch |
|---|---|
| all three exist | equipped: skip to §2. Do not run `install`/`inject` "to be safe" |
| `.agent-tools/agent-ide` missing | bootstrap: locate the global project, then `init-project` |
| nothing anywhere (no global project, no `.agent-ide/skills`) | clone the publish repo as the global project, then `init-project` |
| only `.agent-tools/contact-user` missing | repair: `agent-ide install contact-user` |
| the IDE link is missing | repair: `agent-ide inject <IDE domain> add-skill contact-user` |

```bash
git clone <publish repo> <global> && bash <global>/.agent-ide/skills/agent-ide/install.command   # no ecosystem yet
<global>/.agent-tools/agent-ide init-project <local>      # bootstrap
<local>/.agent-tools/agent-ide install contact-user       # launcher only
<local>/.agent-tools/agent-ide inject <domain> add-skill contact-user
```

On a machine with nothing installed, `install.command` needs only a system `python3` (≥3.10) and this file: it writes the launcher and, when the package declares no requirements, points it at that interpreter. A bundled runtime is optional; `install` reports which interpreter it chose.

`<global>` is normally named in the user's prompt; if not, probe
`~/agent_ide_global_project` before searching. `<domain>` is the directory of the
IDE the user actually works in — probe the project (`.cursor`, `.codebuddy`,
`.vscode`, `.claude`, …) rather than assuming one; `inject` creates the directory
when it is missing. A non-zero `init-project` means the bootstrap did not
happen: report it instead of continuing.

The `agent-ide` skill's `## Cold start` section is the authority; this section is
its branch selector, not a replacement.

## 2. Global project — report, do not edit

Read `<local>/.agent-ide/skills/agent-ide/data/config.json` → `paths.global_home`
and report the resolved path.

- Valid when it contains `.agent-ide/skills`. It may name another project or this
  one ("this project is its own global project" — a legitimate shape, its
  `push` is a no-op).
- Missing, invalid, or naming a project that is not installed: a defect. Do not
  hand-edit `config.json`; repair by re-bootstrapping from the expected global
  project. Defer that repair until after §5 unless the user's prompt is itself a
  push/publish — nothing before §6 needs the field.
- A valid pointer to a *different* global project is a fact to confirm with the
  user, not a defect.

## 3. Resolve the agent id

The id is user-chosen; it often differs from the folder name. First match wins:

1. an id in the current user message;
2. an id in the session context;
3. an id already archived under `data/contact_msg/` or `data/user_response/` —
   prefer an existing one; if several exist and (1)/(2) do not decide, ask;
4. otherwise `contact-user resolve` (project basename).

Pass `--id` explicitly on every invocation. `--recent` under a wrong id reports
an empty history rather than an error, so an empty history in a project that
should have one means: re-check the id.

## 4. Git

The round finalizer runs `git init` itself, so only confirm:

```bash
test -d <local>/.git
```

Do not use `git rev-parse --show-toplevel`: it answers about the current
directory, while the checkpoint commits `<local>`. A linked worktree or submodule
(`.git` is a file) is outside what the checkpoint supports.

## 5. Load context

```bash
<local>/.agent-tools/contact-user --id <id> --recent 20
```

Read at least 20 rounds; raise the number until the user's current goal is one
sentence you can state (the `rounds=` / `selected=` header tells you whether more
exist). **# latest directive** is the binding cue — answer that, use earlier
rounds for reference only. If the history is empty, this is a new project: write
the two input files and contact.

Then pin and read the session store, which is what a later report must be based
on:

```bash
<local>/.agent-tools/contact-user --detect-history-root
<local>/.agent-tools/contact-user --set-history-root <abs path>
<local>/.agent-tools/contact-user --id <id> --session-status
```

Also read `<local>/.agent-ide/skills/collaboration/SKILL.md` and the booklets it
names (notably `skills/01_contact_patch_rules.md`).

## 6. Contact loop

1. `--id <id> --ide-context` — read the session; only this stdout form unlocks
   the round (`--out` exports a copy without unlocking, `--conversation` narrows
   the scope and also keeps it locked).
2. Write `data/input/contact_msg_<id>.txt` and `commit_msg_<id>.txt`.
3. `--id <id>` — as its own command; it blocks until the user submits.
4. Act on the reply in the same turn, then go to 1.

Never end the turn on an IDE chat message, and never treat the chat panel as the
user channel. `SKILL.md` has the data layout, the read flags and the exit-code
table.
