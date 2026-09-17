---
name: lws-config
description: Read or edit lws's token-policy configuration (which rules are off/warn/deny) for this session or project. Use when the user asks to change a lws rule's mode, add a rule, or explain what the current policy will do.
---

# lws-config

lws's policy is one JSON file matching `core/policy/schema.json`: a
`"rules"` object keyed by rule id, each entry an `off` / `warn` / `deny`
mode plus optional rule-specific `options`. The bundled default lives at
`core/policy/default.json` and ships `lws_version` in `warn` mode (a
no-op that reports the plugin version and never denies).

## Reading the active policy

1. Check `LWS_POLICY_PATH` in the environment; if set, that file is active.
2. Otherwise the plugin's vendored `core/policy/default.json` is active.
3. Report every configured rule's mode plainly — do not summarize "mostly
   off" or similar; list each rule id and mode.

## Changing a rule's mode

1. Locate or create the policy file (project convention: `.lws/policy.json`
   at the project root, if this project has adopted one — check before
   assuming).
2. Edit only the `mode` (and `options`, if the rule takes any) for the named
   rule; do not touch entries for other rules.
3. Validate the result is valid JSON and matches `core/policy/schema.json`
   before telling the user the change is live.
4. State plainly what changed: "lws_version: warn -> off" — not "tightened
   the policy".

## The fail-open contract

If the policy file is missing or malformed, every rule resolves to `off`.
This is deliberate (see `core/lws_core/config.py`), not a bug to route
around — never suggest "fixing" fail-open by making a broken policy deny
instead.
