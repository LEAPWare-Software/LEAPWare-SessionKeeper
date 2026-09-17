# Changelog

All notable changes to this project are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning
follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Initial scaffold: `lwr_core` pure engine (`Event` -> `Decision`), the
  `lwr_version` walking-skeleton rule (a safe no-op: allows every event,
  reports the plugin version, never denies — CTO decision 2026-09-17;
  replaces an earlier `budget_line` rule copied from LWH, which would
  have double-enforced next to LWH and isn't a runway rule), the Claude
  Code adapter and plugin (enforcing `PreToolUse` hook), the Codex
  adapter and plugin (enforcing `PreToolUse` hook — see
  `docs/install-codex.md`), `scripts/lwr_build.py` (vendoring), both
  plugin validators, and the unit / adapter / conformance test suite.
- Codex plugin hook: `plugins/codex/lwr/hooks/hooks.json` +
  `bin/lwr_hook.py`, `adapters/codex/hook_io.render_decision`, superseding
  the earlier reporting-only decision now that the plugin-bundled-hooks
  manifest shape is confirmed documented (`docs/install-codex.md`).
