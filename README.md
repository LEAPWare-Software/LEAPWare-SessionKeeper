# LEAPWare Runway

**New session? Read [HANDOFF.md](HANDOFF.md) first.**

Runway makes an AI coding session's spend rules **mechanical**: hooks that
allow, warn, or deny an action, instead of a rule stated in a prompt and
hoped for.

Shipped as two plugins sharing one policy engine:

| Host | Package | What it does |
|---|---|---|
| Claude Code | `plugins/claude/lwr/` | Registers an enforcing `PreToolUse` hook. |
| Codex CLI | `plugins/codex/lwr/` | Registers an enforcing `PreToolUse` hook, same engine as Claude Code. See [docs/install-codex.md](docs/install-codex.md). |

Runtime dependency policy: **Python 3.10+ standard library only.** No
third-party package is imported by `core/`, `adapters/`, or any shipped
plugin script. `pytest` is a dev-only dependency for running the test suite.

License: [Apache-2.0](LICENSE).

## The walking skeleton

One rule ships today, `lwr_version` (see
[docs/rules/lwr-version.md](docs/rules/lwr-version.md)): a safe no-op that
fires on every event, reports this build's `lwr_core.__version__`, and
never denies — even a policy file that (incorrectly) configures it to
`deny` still allows. It exists to prove the whole pipeline end to end —
event in, pure decision, decision out — without shipping any real
enforcement yet: LWR's actual runway rules (wind-down / landing /
handoff-only / retire) are designed and built in a later session, and this
rule must not double-enforce anything LWH already enforces in the
meantime.

## How it fits together

```
core/lwr_core/          pure engine: (Event, Policy) -> Decision. No I/O.
core/policy/              policy JSON schema + bundled default policy.
adapters/claude/          Claude Code hook JSON <-> neutral Event/Decision.
adapters/codex/           Codex event shape <-> neutral Event; enforcing hook.
plugins/claude/lwr/      the installable Claude Code plugin (vendors core+adapter).
plugins/codex/lwr/       the installable Codex plugin (vendors core+adapter).
scripts/lwr_build.py          copies core/ + the matching adapter into each plugin's vendor/.
```

See [docs/architecture.md](docs/architecture.md) for the full data flow and
[docs/policy.md](docs/policy.md) for the policy file format and the
fail-open contract.

## Installing

- Claude Code: [docs/install-claude.md](docs/install-claude.md).
- Codex CLI: [docs/install-codex.md](docs/install-codex.md).

## Developing

```
python -m pytest -q                    # unit + adapter + conformance tests
python scripts/lwr_build.py                # refresh both plugins' vendor/ trees
python scripts/lwr_build.py --check        # fail if vendor/ has drifted from source
python scripts/lwr_validate_claude_plugin.py
python scripts/lwr_validate_codex_plugin.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow and
[SECURITY.md](SECURITY.md) for how to report a vulnerability.

## Status

Early scaffold: one rule, two adapters, a pure engine, and the tests and CI
that keep them honest. Not yet published to GitHub or a package index —
this README describes the local tree.
