# Handoff protocol

`HANDOFF.md`, at the repo root, is the single re-derivable state file a
new session reads first. This document is the protocol that keeps it
true. It has no runtime role — the lws plugin never reads it.

## When to write a handoff

Write (or update) `HANDOFF.md` at each of these points:

1. Before ending any session, whatever the reason.
2. At any rate-limit or context warning from the host CLI.
3. After each deliverable lands (its own Proof of Completion, see below,
   plus an updated "next step" in the "In flight" section).

A handoff is cheap and mechanical (`scripts/lws_handoff.py --write`); the
cost of skipping one is a session that starts from guesswork instead of
fact.

## What the generated block contains

Between `<!-- lws-handoff:begin -->` and `<!-- lws-handoff:end -->` in
`HANDOFF.md`, `scripts/lws_handoff.py --write` regenerates:

- UTC timestamp of generation.
- CLI name and session id (when the caller supplies them; omitted rather
  than guessed otherwise).
- `main`'s current SHA.
- Open PRs with their CI state.
- Deliverables in flight with their proof state.
- The next step to take.

## Only the block is regenerated

Everything in `HANDOFF.md` outside the begin/end markers — the "In
flight" narrative, "Hard rules", "Traps", the checklist — is prose a
session wrote by hand. `--write` never touches it. If the narrative plan
changes (a step finishes, a new one starts), edit that prose by hand in
the same commit that regenerates the block.

## Size cap

`HANDOFF.md` must stay at or under **6000 bytes**. This is not a soft
target — `scripts/lws_handoff.py --check` fails the build over it. A
one-page handoff that nobody reads in full is worse than no handoff;
trim prose before growing the cap.

## This file's own size cap

This file is the designated overflow target when `HANDOFF.md` hits its own
6000-byte cap, so it needs headroom — but it is not unbounded either.
`scripts/lws_handoff.py --check` fails the build if this file exceeds
**12000 bytes**. Trim it before it gets there; move stale "Traps learned"
entries out or condense them rather than letting this file grow forever.

## Done means committed and pushed

A handoff is DONE only when it is committed to the branch and pushed to
`origin`. A regenerated `HANDOFF.md` sitting only in a working tree is not
a handoff — the next session (possibly on a different machine) cannot see
it.

## The next session re-derives state, never trusts prose

Every session, CLI, or machine starts by running the commands in
`HANDOFF.md`'s "Re-derive state" section — `git`, `gh` — and treats their
output as fact. The "In flight" narrative is the *plan*; the command
output is the *state*. Where they disagree, the commands win, and the
narrative gets corrected in the same session.

## Proof of Completion

A deliverable is DONE only when: committed, pushed, CI is green on that
push, and a proof record exists (what changed, why, how it was verified —
commit message and/or PR description is sufficient; no separate proof
file is required). Every proven delivery is announced with a line
starting `LWS - Alert: <id> DONE ...` so it is grep-able across a long
session.

## Traps learned

Moved here from `HANDOFF.md` when that file hit its own size cap. A cap
reached means content moves out, never that meaning gets trimmed.

- `lws_check_env_leak.py`'s drive-letter rule reads a one-letter key
  followed by an escaped newline inside a Python string as a Windows path,
  so a fixture written as a one-letter YAML key trips the leak check. Use
  multi-letter keys. The same rule scans `HANDOFF.md` and this file, so do
  not quote that regex in either.
- `lws-env-leak-history` scans **every commit a pull request adds**, not
  the final tree. A fix-forward commit cannot clear a leak already in the
  branch's history — the branch has to be squashed first, and a force-push
  needs the owner.
- `scripts/lws_handoff.py --write` writes PR titles as mojibake when a
  title contains a non-ASCII character. Keep pull request titles ASCII.
- Background agents share one working tree. A `git checkout` while a
  subagent is reading files silently hands it another branch's content,
  and its findings will be about code you did not ask it to review. Tell
  reviewers to copy what they need into a scratch directory, and do not
  switch branches while one is live.
