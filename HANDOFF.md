# HANDOFF

One page. Read this before any other file when starting a new session on
this repo. See `docs/handoff-protocol.md` for the full protocol this file
follows.

## Start of session

- [ ] Read this whole file.
- [ ] Run the commands in "Re-derive state" below — trust their output,
      not this file's prose (except the "In flight" narrative, which is
      the current plan of record).
- [ ] Confirm which CLI you are (Claude Code or Codex) and work only in
      your lane: see `CLAUDE.md` / `AGENTS.md`.
- [ ] If nothing below is in flight, ENTER PLAN MODE and pick up the next
      unchecked step.

## In flight

The plan, in order. Do not skip a step; do not start step *n+1* before
step *n* is done and proven.

1. Work from this repo only. Clone fresh on any machine; no dependence on
   the local environment. **SACRED.**
2. DONE — bootstrap PR #1 merged. As of 2026-09-18 the mission rewrite
   (PR #11), the hosted-runner CI check for directive 18 (PR #10), the
   privacy fix removing the owner's private names from `scripts/`
   (PR #8), and the master plan (PR #12) have all landed on `main` too.
   `main` has no open PRs.
3. **BUILD IS ON HARD HOLD.** The owner directed that LWS adopt the
   LEAPWare BuildCraft SDLC, and that no LWS implementation start before
   BuildCraft is ready. BuildCraft today ships only a no-op rule, its
   gate rules are undesigned, and its own directives file is a
   placeholder. Confirmed by the owner 2026-09-18. See
   `docs/requirements/master-plan-1.0.0.md`.
4. The plan of record is `docs/requirements/master-plan-1.0.0.md`. Only
   Phase 0 may start; everything from Phase 1 onward is blocked on step 3.
5. Phase 0 remaining: build the graphify graph for this repo
   (`graphify install --platform claude` first — the installed skill is
   0.8.31 against package 0.9.56 — then index), and write the numbered
   testable requirements list per `docs/requirements/approach.md`.
6. Every deliverable follows `docs/handoff-protocol.md`: proof record,
   pushed, CI green, alert line `LWS - Alert: <id> DONE ...`. Nothing has
   met that bar yet: `proof/` is empty and no alert has been sent.

<!-- lws-handoff:begin -->

Generated: 2026-09-18 19:55 UTC
main SHA: 90e719855ccce31612ca8e38c7d36a390955332f
CLI: claude
Session: fix-handoff-check-verifies-facts

Open PRs:
#15 fix(handoff): make the check verify the block's facts, not just its shape (fix/handoff-check-verifies-facts)

Deliverable proof state (from proof/):
(none yet)

<!-- lws-handoff:end -->

## Re-derive state

```
git fetch origin
git status
git log --oneline -10
gh pr list --state open
gh run list --limit 10
gh api repos/LEAPWare-Software/LEAPWare-SessionKeeper/rulesets
```

`gh` and `git` are the state of record. This file's "In flight" list is
the plan; the commands above are the facts.

## Hard rules

- Python 3.10+ standard library only, everywhere in `core/`, `adapters/`,
  and any shipped plugin script.
- The plugin never reads or depends on `CLAUDE.md` or `AGENTS.md` at
  runtime — those are contributor-only docs.
- Runway state (wind-down/landing/handoff-only/retired) and any restart
  gating are enforced mechanically by the plugin (allow/warn/deny), never
  by trust.
- No repo settings change, no merge, no force-push, no history rewrite
  without the owner.
- One GitHub App per CLI; no shared credential.

## Traps

- `gh pr list --jq` without `--json` exits 1; use `--json` + `--template`
  or `--jq` with `gh api`.
- A linked worktree's `.git` is a file, not a directory.
- `git diff` omits untracked files; check
  `git ls-files --others --exclude-standard` too.
- Squash-merge only happens through the merge queue — never merge locally
  and push to `main`.
- `scripts/lws_handoff.py --write` needs `gh` auth for the PR list; without
  it the block now writes the unmistakable `(UNKNOWN - gh unavailable,
  this block is not trustworthy)` rather than an ambiguous
  "(unavailable)". `--check` only validates shape — it never re-derives
  facts. Use `--check-live` (PR-only in CI, needs `gh` auth) to catch a
  stale SHA or PR list; a bare `--check` passing proves nothing about
  truth, only shape.
- Four more, on the CI checks and on sharing a working tree with
  subagents: see "Traps learned" in `docs/handoff-protocol.md`.
- Delegate-only mode (lw-watchtower) was left ON globally on 2026-09-18.
  It refuses Edit, Write, NotebookEdit, Bash and PowerShell on the main
  thread; all work must go through subagents. It cannot be turned off
  from the main thread. Set `interaction.delegate` to `false` in
  `config.override.json` under the plugin state directory, or have a
  subagent run `/lw-watchtower:delegate off`.
