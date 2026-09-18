# Owner directives (setup session, 2026-09-17)

Binding. These are the owner's own directives from the setup session that
created this repo, one numbered line each. Where the owner's wording is
known it is quoted; the requirements package in `approach.md` must trace
every functional requirement back to one of these. Source: the owner's
2026-09-17 directives for LWS, plus this setup session's own elaboration
of them; see the memory record `lws-directives-2026-09-17.md` for the
owner's original, unelaborated wording.

## Product mission

LWS is a session runway plugin for AI coding CLIs.

It measures a session's own consumption across three windows — context, the
5-hour rate-limit window and the 7-day rate-limit window — and mechanically
moves the session through wind-down, landing, handoff-only and retired as
consumption climbs. Allow, warn, deny, enforced by hooks, never by trust.

It owns the usage display, showing all three readings with their reset times.
When a window resets it restarts the session unattended, with a
consumed-handoff guard so a handoff already acted on is never replayed.

It ships as both a Claude Code plugin and a Codex plugin, enforcing on both.
It depends on no `CLAUDE.md` or `AGENTS.md` at runtime; all policy lives in
the plugin. Python 3.10+ standard library only. Small, with a size budget as
a requirement.

The numbered directives below are the binding record. Where one has been
amended, the original wording is kept alongside it.

1. Code name LWS; every command, skill, and user-facing entrypoint starts
   with `lws`. Own public repo
   `github.com/LEAPWare-Software/LEAPWare-SessionKeeper`, set up exactly like
   LWH: identity `LEAPWare <leapware@outlook.com>`, rulesets, merge
   queue, squash, hosted CI, handoff protocol, proof records.
2. LWS is a session runway plugin: it watches a CLI session's own
   consumption across **three windows — context, the 5-hour rate-limit
   window, and the 7-day rate-limit window** — and, mechanically
   (allow/warn/deny, never by trust), moves the session through
   wind-down, landing, handoff-only, and retired states as consumption
   climbs — the same shape as a RUNWAY-style gate proven elsewhere, but
   shipped here as its own standalone, reusable plugin.
   **Amended by the owner 2026-09-18: context is a tracked window, not
   just the two rate-limit windows.** Original wording: "LWS is a
   rate-limit runway plugin: it watches a CLI session's own usage (5-hour
   and 7-day rate-limit windows) and, mechanically (allow/warn/deny,
   never by trust), moves the session through wind-down, landing,
   handoff-only, and retired states as usage climbs."
3. The plugin must not depend on any `CLAUDE.md` or `AGENTS.md` (local,
   project, or global) at runtime. All policy lives in the plugin.
4. Both a Claude Code plugin and a Codex plugin, enforcing via hooks on
   both — no reporting-only constraint on either CLI.
5. Lanes: Codex works only on the Codex part, Claude only on the Claude
   part. Shared parts (`core/`, `scripts/`, `.github/`, `docs/`,
   `proof/`, `reviews/`) may be changed by either CLI.
   **Amended by the owner 2026-09-18: the dual CTO/CIO sign-off is
   removed.** The lane split stands and is still enforced by
   `lws-lanes`; the shared-path review records are not. Original wording:
   shared parts "may be changed by either CLI only after the CTO/CIO role
   on **each** CLI adversarially checks and agrees; the owner is not in
   that loop."
6. Status line: LWS owns the usage display and shows all three readings
   with their reset times, in the form
   `ctx 44%  5h 24% (23m)  7d 19% (09/24 1am)` — the 5-hour window as
   time remaining, the 7-day window as the absolute reset date and time.
   The runway state tag (wind-down, landing, handoff-only, retired)
   appears ONLY when the session is past normal. LWS must never overwrite
   an existing status line segment.
   **Amended by the owner 2026-09-18: LWS owns the usage display; it is
   not deferred to LWH.** Original wording: "Status line: shows ONE SHORT
   TAG for the session's runway state (proposed: `LWS ok`, `LWS WIND
   80%`, `LWS LAND 90%`, `LWS HOFF 95%`, `LWS RET` for retired — final
   label text needs owner approval before freeze) and must never
   overwrite an existing status line segment. Usage readings (context %,
   5h %, 7d %) are shared with LWH: LWH owns the usage *display* when it
   is present; LWS reads the same measurements and works alone, still
   showing its own tag, if LWH is absent."
7. Proof of Completion on every deliverable; done = committed AND pushed
   with a proof record and green CI; every proven delivery is announced
   as `LWS - Alert:`.
8. **SACRED**: repo and tooling build, test and deploy
   environment-agnostic for both Codex and Claude, on any laptop
   (Windows, Mac, Linux); the owner builds and tests from different
   laptops/environments; there must NOT be ANY dependence on or tie-in
   to a local environment.
9. All CI runs in GitHub Actions on hosted runners; no local runners.
10. Open source, public: `github.com/LEAPWare-Software/LEAPWare-SessionKeeper`,
    Apache-2.0, commit identity `LEAPWare <leapware@outlook.com>`.
11. Runtime: Python 3.10+ standard library only.
12. Repository rulesets (no bypass), merge queue + auto-merge, squash
    merges only; one GitHub App per CLI (`lws-claude`, `lws-codex`).
13. A full handoff protocol lives in the repo; the next session runs from
    the repo and first builds, in plan mode, the full plan to ship 1.0.0.
14. Lean: LW-Watchtower became bloated; lws must stay small, with a size
    budget as a requirement.
15. Automatic restart after a rate-limit reset is IN SCOPE: build it and
    prove it with a real unattended restart, plus a consumed-handoff
    guard (a handoff already acted on must not be replayed by the
    restart).
16. Out of scope for lws: Proof of Completion CI enforcement for other
    repos (separate product).
    **Amended by the owner 2026-09-18: usage display is now IN scope and
    owned by LWS — see directive 6.** Original wording: "Out of scope for
    lws: usage *display* in the status line when LWH is present (LWH's
    job — see directive 6); Proof of Completion CI enforcement for other
    repos (separate product)."
17. Prove without doubt: a numbered testable requirements list; a test
    per rule proven by breaking it on purpose; a rehearsal with fake
    usage at 80/90/95 and retire (the owner does not watch the
    rehearsal — proof record only); a one-day comparison of LWS's
    readings against the CLI's own real usage display; a real
    unattended restart; an independent proof record.
18. (2026-09-17) Public repos use GitHub-hosted runners only, never
    self-hosted or local; add a CI check that fails on any `runs-on`
    value other than a GitHub-hosted runner, proven by breaking it on
    purpose. This restates **directive 9** and makes it mechanical rather
    than adding a new requirement — this file is an append-only log of
    what the owner said in each session, not a deduplicated spec, so both
    lines stay. `approach.md` should trace 9 and 18 to one functional
    requirement, not two.
19. (2026-09-17) Worktrees live only under `.worktrees/<branch>`, never
    as sibling folders.
