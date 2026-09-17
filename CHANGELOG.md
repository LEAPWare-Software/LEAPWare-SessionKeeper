# Changelog

All notable changes to this project are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning
follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `scripts/lws_check_hosted_runner.py` + the `lws-hosted-runner` CI step
  (owner directive 18): fails on any `runs-on` that is not a known
  GitHub-hosted runner. Resolves `${{ matrix.<key> }}` against the job's own
  matrix and is fail-closed — a runner group, an unresolvable expression, or
  an unrecognised label is an error, not a skip. Stdlib only, so it carries a
  small targeted YAML subset reader rather than PyYAML. Proven by breaking
  the repo's real `ci.yml` on purpose in
  `tests/test_lws_check_hosted_runner.py`.

- Initial scaffold: `lws_core` pure engine (`Event` -> `Decision`), the
  `lws_version` walking-skeleton rule (a safe no-op: allows every event,
  reports the plugin version, never denies — CTO decision 2026-09-17;
  replaces an earlier `budget_line` rule copied from LWH, which would
  have double-enforced next to LWH and isn't a runway rule), the Claude
  Code adapter and plugin (enforcing `PreToolUse` hook), the Codex
  adapter and plugin (enforcing `PreToolUse` hook — see
  `docs/install-codex.md`), `scripts/lws_build.py` (vendoring), both
  plugin validators, and the unit / adapter / conformance test suite.
- Codex plugin hook: `plugins/codex/lws/hooks/hooks.json` +
  `bin/lws_hook.py`, `adapters/codex/hook_io.render_decision`, superseding
  the earlier reporting-only decision now that the plugin-bundled-hooks
  manifest shape is confirmed documented (`docs/install-codex.md`).
