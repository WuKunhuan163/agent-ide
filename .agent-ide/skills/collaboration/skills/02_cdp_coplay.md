This booklet is the executable rule set for driving a browser **together with the user** through CDP: one visible Chrome, two connection lifetimes, a textual result contract the agent must parse, and the floating panels that let a human inspect state without reloading. Read it before adding any browser-driving script, dev panel, or viewport logic to a project. Every concrete value below (sizes, ports, endpoint names, preset ids) is a placeholder — take the mechanism, replace the numbers.

# 1. When this applies

- The target is a **local HTTP app** whose state lives on the server and whose UI the user must watch while the agent drives it.
- The agent otherwise launches a headless or throwaway browser per step, and the user is reduced to describing what the screen looks like.

Do not adopt it for: pure API backends; suites that must run headless-only in CI (use a separate Playwright profile there); responsive mobile-first sites, where locking a viewport actively lies about layout.

# 2. One Chrome owner, two lifetimes

- **Long-lived process** owns the browser: persistent Profile directory, `--remote-debugging-port`, and the only `launch()` in the system. It stays up for the whole session.
- **Short-lived sessions** are what the agent uses: `connect_over_cdp`, do one action, detach. Never call `browser.close()` — that can take the user's window down with it. Never start a second browser for routine work; a second browser means the user is watching the wrong screen.
- Pick the page by host match, scanning tabs in reverse and skipping `devtools://` ones. Do not assume the first tab is the app.
- On recent Chrome builds, pass `--remote-allow-origins=*` when attaching, or Playwright refuses with a context-management error.

# 3. Port discovery is a file, not a convention

- Bind the CDP port to `127.0.0.1:0` and let the OS choose; write `cdp_port`, `cdp_url`, pid into a keepalive JSON at a fixed path.
- Every CLI, script and agent reads that file to find the port. A hard-coded port collides with whatever else the user is running and turns into a debugging session of its own.
- Keep the HTTP port and the CDP port separate concerns: the app port is explicit, the CDP port is discovered.
- Keep a second small JSON for probe state (`current_url`, session id, active screen) so a resumed agent lands on the same step instead of the top of the flow.

# 4. The result contract

Every browser subcommand prints a first line the agent can branch on, and structured evidence under it:

```
OK <action>      → url=… | auth=…
FAIL <action>: <ExceptionType>: <message>
  screenshot: <file>
  visible_inputs: <selectors actually on screen>
WARN console: <error or warning>
WARN fill mismatch: expected … got …
ALERT dialog[confirm]: <text>
```

- Agents **parse the text**, never the exit code. Wrappers commonly return 0 on failure.
- On `FAIL`, capture a screenshot and list visible inputs, so the next attempt has evidence instead of a guessed selector.
- `WARN` means “carried on, already dirty”: investigate before the next action.
- `ALERT` means the dialog was auto-accepted and the user never saw it. Log it; the user's mental model is now wrong.
- One action per invocation. Do not chain `goto && click && fill`: a single blocking confirm hangs the whole chain, and the user cannot intervene mid-script. This is a hard rule, not style.

# 5. Three-way check, and stated blind spots

After any navigation, compare three things: the URL, the server's read-only state endpoint for that session id, and what is visibly on screen. Disagreement is a bug — do not click again.

Expose one read-only snapshot endpoint (`GET /api/state?sid=…`, name is yours) returning at minimum the session id, the screen/state key, and the mode. It is the only reliable answer to “where are we”, because path routes are not state.

CDP does **not** catch, by itself: silent logic errors with no console output; CSS broken but still clickable; a stale or wrong session id; `fill` that never fired `change`; mid-animation frames. Cover these with explicit `--evaluate` assertions on business invariants plus the user's eyes. Do not claim a step verified on the strength of “it did not throw”.

# 6. Panels

Mount every panel on `document.body`, outside the app stage, so no overflow rule can clip it. Panels are for the **human**; the agent uses the CLI.

- **Checkpoint float** — a collapsible `<details>` with a draggable title bar (no edge clamping: it must be allowed to leave the viewport, e.g. during recording), keyboard toggles for show/hide and collapse, and a title naming the current role and step. Switching identity or step posts to the server and re-renders in place: **no URL change, no reload**. Do not paint a persistent “active” highlight on the list — server state is the truth, and a frontend highlight will drift from it.
- **Device / viewport / scale** — a fixed side panel that is never scaled, a stage that is, and a device registry as **data** (preset id → width, height, orientation) so adding a device is one record, not a new branch.
- **Visual feedback** — before clicking, inject an ephemeral high-contrast ripple at the element center; on focus, a glow; on fill, typewriter timing. All with `pointer-events: none`, removed after a few hundred milliseconds. Without this the user cannot see where the agent acted, and “co-play” is theatre.
- **Test / studio split** — persist the mode in the session and render it server-side; treat `?mode=…` as a one-shot entry that redirects to a clean URL. Test mode locks the viewport and registers no panels; studio mode unlocks it and shows them. The point is that a demo and a regression run must not share a mode.
- **SSE mirror** — only when the tab the user watches is not the tab the agent attaches to: publish click events to an in-process pub/sub, let the wall page consume them over `EventSource` and `postMessage` the coordinates into the matching iframe. Debounce identical events, and never auto-reload on a session reset.

# 7. What to replace when copying

Sizes, CDP window dimensions, app port, endpoint paths and field names, preset ids, panel labels, checkpoint names. If a value in your draft can only be explained by “that is how the last project did it”, it is a leftover, not a mechanism.

# 8. Done criteria

- The user's window is the one the agent drove, and the click was visible.
- The last command printed `OK`; no unresolved `WARN` or `ALERT` from this step.
- URL, state endpoint and screen agree.
- A restart of the dev server did not lose the session id.
- Any panel the user needed was reachable without a reload.
