# Installing runway on Claude Code

## From this local checkout (development)

1. In Claude Code, add this repository as a marketplace source pointing at
   `.claude-plugin/marketplace.json` (root of this repo), or add
   `plugins/claude/lwr` directly as a local plugin path, per Claude Code's
   own plugin-development docs.
2. Before installing, run `python scripts/lwr_build.py` from the repo root so
   `plugins/claude/lwr/vendor/` contains a current copy of `lwr_core` and
   `adapters/claude` — the plugin cannot import from outside its own
   directory once installed.
3. Enable the `runway` plugin.

## What it registers

One hook, in `plugins/claude/lwr/hooks/hooks.json`:

```json
{
  "matcher": "Agent",
  "hooks": [
    {
      "type": "command",
      "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/bin/lwr_hook.py\" || python \"${CLAUDE_PLUGIN_ROOT}/bin/lwr_hook.py\""
    }
  ]
}
```

on `PreToolUse`. `${CLAUDE_PLUGIN_ROOT}` is the variable name Claude Code's
own hooks documentation and LW-WATCHTOWER's `hooks/hooks.json` (this
project's sibling plugin) both use for a plugin's own install directory;
confirmed by reading the sibling LW-WATCHTOWER plugin's own
`lw-watchtower/hooks/hooks.json` during this project's recon, where every
one of its fifteen hook registrations uses the same variable. The
`python3 ... || python ...` form is this project's own portable
dual-interpreter launch — see `docs/architecture.md#the-hook-launch-method`
for why it is safe (this hook always exits `0` and signals its decision on
stdout, never via exit code) and for the official docs consulted.

## What it does on each dispatch

`plugins/claude/lwr/bin/lwr_hook.py` reads the `PreToolUse` JSON from
stdin, evaluates it against the active policy (see `docs/policy.md`), and
writes a JSON decision to stdout:

- A `deny`-mode finding produces
  `hookSpecificOutput.permissionDecision: "deny"` with
  `permissionDecisionReason` set — Claude Code blocks the dispatch and
  shows the reason.
- Otherwise, `permissionDecision: "allow"`, with `permissionDecisionReason`
  carrying any `warn`-mode findings (visible, non-blocking).

Every evaluated event is also appended as one JSON line to a ledger file —
see `docs/rules/budget-line.md` and `lwr-report`'s `SKILL.md` for how to
read it.

## Hook event JSON shapes referenced

`docs/rules/budget-line.md` and `adapters/claude/hook_io.py` were written
against:

- Claude Code hooks reference:
  `https://docs.claude.com/en/docs/claude-code/hooks` — `PreToolUse` input
  fields (`hook_event_name`, `tool_name`, `tool_input`, `session_id`,
  `transcript_path`) and the `hookSpecificOutput.permissionDecision` /
  `permissionDecisionReason` output shape for `PreToolUse`.
- Cross-checked against LW-WATCHTOWER's own hook scripts and
  `hooks/hooks.json` in the sibling repository named above, for the
  `${CLAUDE_PLUGIN_ROOT}` variable name and the `SubagentStop`/`Stop` event
  names used in this project's fixtures
  (`tests/adapters/fixtures/claude/subagent_stop.json`,
  `tests/adapters/fixtures/claude/stop.json`).

Sanitized fixtures built from these shapes live under
`tests/adapters/fixtures/claude/`; every value in them is placeholder text,
not data from any real session.
