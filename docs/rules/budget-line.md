# Rule: `budget_line`

**Status:** shipped, the walking-skeleton rule. Source:
`core/lwr_core/rules/budget_line.py`. Default mode: `deny` (see
`core/policy/default.json`) — owner directive 2 requires mechanical
enforcement, so a dispatch with no BUDGET line is blocked by default, not
merely recorded.

## What it checks

Fires only on a `PreToolUse` event whose `tool_name` is `"Agent"` — i.e. a
subagent dispatch. For every other event (including other `PreToolUse`
tools, and every non-`PreToolUse` hook event) it returns no finding,
regardless of its configured mode.

When it fires, it checks the dispatch prompt for a line matching:

```
^BUDGET:\s*\d+k\s*$
```

(multiline mode: start-of-line anchor matches any line within the prompt,
not just the first). `BUDGET: 40k` matches; `budget: 40k` does not (case
matters); `BUDGET 40k` does not (the colon is required); `some text BUDGET:
40k` does not (must be the whole line, only leading/trailing whitespace
allowed).

If no line matches, the rule produces a finding at the policy's configured
mode for `budget_line`.

## Options

None. `options` is accepted by the schema but currently ignored by this
rule.

## Modes

| Mode | Behavior |
|---|---|
| `off` | No check runs. |
| `warn` | A missing BUDGET line is recorded (ledger, `permissionDecisionReason` on Claude Code) but the dispatch proceeds. |
| `deny` | A missing BUDGET line blocks the dispatch. |

## Why this rule, first

It is deliberately small: one regex, one trigger condition, no external
state. It exists to prove the full pipeline — hook fires, adapter parses,
engine evaluates, adapter renders, host acts on the render — works
end-to-end before any more elaborate rule is built on top of the same
scaffolding. See `tests/core/test_budget_line.py`,
`tests/adapters/test_claude_hook_io.py`,
`tests/adapters/test_codex_hook_io.py`, and
`tests/conformance/test_same_decision_both_adapters.py` for the tests that
exercise it at every layer.
