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
3. **BLOCKER on everything below.** No open PR can go green: every one
   touches a shared path, so `lws-lanes` requires BOTH
   `reviews/<pr>/claude-cto.json` and `reviews/<pr>/codex-cto.json`. The
   codex record can only be written by a **Codex session** — a Claude
   session must never author it. Run Codex in its own lane and have its
   CTO role review PRs #7, #8, #9, #10.
4. IN FLIGHT — PR #9, lane-classifier fix. Root files, generic `tests/`
   paths, `.claude/`, `.codex/` and `.worktrees/` all classified "other",
   which no agent may touch: a rule no commit could satisfy. It blocks
   PR #8 and any new test file. Land this first.
5. IN FLIGHT — PR #10, the hosted-runner-only CI check (**directive 18**,
   which makes directive 9 mechanical): fails on any `runs-on` that is not
   a GitHub-hosted runner, proven by breaking the repo's own `ci.yml`.
   Stacked on PR #9 — retarget to `main` and rebase once #9 lands. Its
   branch must be **squashed before it can ever pass**: the
   `lws-env-leak-history` step scans every commit a PR adds, and three of
   its commits carry a string the leak check misreads (see Traps).
6. BLOCKED on step 3 — PR #8, which removes the owner's private names
   from `scripts/`. They are public on `main` until it merges.
7. Create the two GitHub Apps (`lws-claude`, `lws-codex`) from the
   committed manifests in `.github/apps/`, using a browser-enabled
   session. Install each on this repo only. Store each private key in the
   owner's secrets manager, never in the repo. Record App ids in
   `docs/maintainers/github-apps.md` via PR.
8. ENTER PLAN MODE (each CLI in its own lane) and build the full plan to
   ship lws 1.0.0, starting with the complete requirements package per
   `docs/requirements/approach.md`, seeded by
   `docs/requirements/owner-directives.md`. Present the plan to the owner
   for approval before building.
9. Every deliverable follows `docs/handoff-protocol.md`: proof record,
   pushed, CI green, alert line `LWS - Alert: <id> DONE ...`. Nothing has
   met that bar yet: `proof/` is empty and no alert has been sent.

<!-- lws-handoff:begin -->

Generated: 2026-09-18 19:15 UTC
main SHA: dae28b0bf671e7597f009ea310d456d52fd67921
CLI: unknown
Session: unknown

Open PRs:
#12 docs(requirements): master plan for shipping lws 1.0.0 (docs/master-plan-1.0.0)
#10 feat(ci): lws-hosted-runner check - GitHub-hosted runners only (directive 18) (feat/hosted-runner-only-check)
#7 docs(handoff): bootstrap DONE, hosted-runner-only + worktree-location directives (docs/session-handoff)

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
- `scripts/lws_handoff.py --write` needs `gh` auth for the PR list and
  degrades to "(unavailable)" instead of failing, so a green `--check`
  does not prove the list is current — re-read "Generated".
- Four more, on the CI checks and on sharing a working tree with
  subagents: see "Traps learned" in `docs/handoff-protocol.md`.
