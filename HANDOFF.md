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
2. DONE — bootstrap PR #1 (branch `lws-bootstrap`, everything but the
   meta-files-only initial commit: core, adapters, plugins, scripts,
   tests, docs, `.github/`) merged through the merge queue, sha
   `29d8dd96459e4c08df49810c7dc16fc64791b659`. The repo is now worked
   from its own Claude session opened in its own folder.
3. Implement the hosted-runner-only CI check (directive a in
   `docs/requirements/owner-directives.md`): a CI check that fails on any
   `runs-on` value other than a GitHub-hosted runner, proven by breaking
   it on purpose.
4. Create the two GitHub Apps (`lws-claude`, `lws-codex`) from the
   committed manifests in `.github/apps/`, using a browser-enabled
   session. Install each on this repo only. Store each private key in the
   owner's secrets manager, never in the repo. Record App ids in
   `docs/maintainers/github-apps.md` via PR.
5. ENTER PLAN MODE (each CLI in its own lane) and build the full plan to
   ship lws 1.0.0, starting with the complete requirements package per
   `docs/requirements/approach.md`, seeded by
   `docs/requirements/owner-directives.md`. Present the plan to the owner
   for approval before building.
6. Every deliverable follows `docs/handoff-protocol.md`: proof record,
   pushed, CI green, alert line `LWS - Alert: <id> DONE ...`.

<!-- lws-handoff:begin -->

Generated: 2026-09-17 15:25 UTC
main SHA: 01be6fddcec33f90e2c7e5bd519827c583fd818b
CLI: claude
Session: bootstrap-2026-09-17-pr1

Open PRs:
#1 Bootstrap LWS repository setup (lws-bootstrap)

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
- `scripts/lws_handoff.py --write` requires `gh` auth for the PR list; it
  degrades to "(unavailable)" rather than failing when `gh` is missing or
  unauthenticated, so a green `--check` does not by itself prove the PR
  list is current — re-read the "Generated" timestamp.
