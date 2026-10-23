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
| `.agent-tools/agent-ide` missing | bootstrap: get `<global>` (ask the user for the path), then import |
| nothing anywhere (no global project anywhere) | clone the publish repo as `<global>`, then import |
| only `.agent-tools/contact-user` missing | repair: `agent-ide install contact-user` |
| the IDE link is missing | repair: `agent-ide inject <IDE domain> add-skill contact-user` |

```bash
<global>/.agent-tools/agent-ide push --from-global --global <global> --project <local> \
    agent-ide contact-user collaboration                   # import
<global>/.agent-tools/agent-ide install --project <local> agent-ide contact-user collaboration
<local>/.agent-tools/agent-ide install contact-user        # launcher only
<local>/.agent-tools/agent-ide inject <domain> add-skill contact-user
```

Bootstrap is the ordinary `push --from-global` / `install` pair; there is no
separate bootstrap command. The one thing you have to know is `<global>`: the
user's prompt usually names it, otherwise probe `~/agent_ide_global_project`.

`<global>` must already exist. Only when the machine has no global project at all
do you clone the publish repo into it, and only after the user confirms the URL:
`git clone <publish repo> <global> && bash <global>/.agent-ide/skills/agent-ide/install.command`.
`install.command` needs just a system `python3` (≥3.10) and this file: it writes
the launcher and, when the package declares no requirements, points it at that
interpreter. A bundled runtime is optional; `install` reports which interpreter
it chose.

`<domain>` is the directory of the IDE the user actually works in — probe the
project (`.cursor`, `.codebuddy`, `.vscode`, `.claude`, …) rather than assuming
one; `inject` creates the directory when it is missing. A non-zero
`push --from-global` means the import did not happen: report it instead of
continuing.

The `agent-ide` skill's `## Cold start` section is the authority; this section is
its branch selector, not a replacement.

## 2. Global project — report, do not edit

Read `<local>/.agent-ide/skills/agent-ide/data/config.json` → `paths.global_home`
and report the resolved path.

- Valid when it contains `.agent-ide/skills`. It may name another project or this
  one ("this project is its own global project" — a legitimate shape, its
  `push` is a no-op).
- Missing, invalid, or naming a project that is not installed: a defect. Do not
  hand-edit `config.json`; repair it with
  `agent-ide push --from-global --global <expected global> <skill>...`, which
  records the path it is given. Defer that repair until after §5 unless the
  user's prompt is itself a push/publish — nothing before §6 needs the field.
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

Once the session is identified, register the pair so later reads need no
`--conversation`:

```bash
<local>/.agent-tools/contact-user --id <id> --bind-conversation <conv>
<local>/.agent-tools/contact-user --bindings
```

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

Then pin the session store. `--ide-context` is the read a report must be based
on; it prints the last 100 rounds by default, counted in rounds rather than time,
and takes a larger number (`--ide-context 250`) when the work spans more:

```bash
<local>/.agent-tools/contact-user --detect-history-root
<local>/.agent-tools/contact-user --set-history-root <abs path>
<local>/.agent-tools/contact-user --id <id> --ide-context
```

Also read `<local>/.agent-ide/skills/collaboration/SKILL.md`. It names its
booklets and the condition each one applies under; do not open a booklet whose
condition is not met (advisor mode, for instance, is entered only when the user
holds the keyboard and will apply the edits themselves).

## 6. Contact loop

1. `--id <id> --ide-context` — read the session; only this stdout form unlocks
   the round (`--out` exports a copy without unlocking, `--conversation` narrows
   the scope and also keeps it locked). Its last line is this round's anchor.
2. Run `contact-user --id <id> --input-path` and write at the two absolute
   paths it prints (`.../data/input/<id>/contact_msg.txt` and `commit_msg.txt`).
   Never build a `data/...` path by hand. The contact
   file must contain the anchor line verbatim (`report anchor: <digest8> · <n>
   msgs`); without it `--id` refuses to open the window.
3. `--id <id>` — as its own command; it blocks until the user submits.
4. Act on the reply in the same turn, then go to 1.

Never end the turn on an IDE chat message, and never treat the chat panel as the
user channel. `SKILL.md` has the data layout, the read flags and the exit-code
table.
