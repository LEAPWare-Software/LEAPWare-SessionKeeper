# Owner directives (setup session, 2026-09-17)

Binding. These are the owner's own directives from the setup session that
created this repo, one numbered line each. Where the owner's wording is
known it is quoted; the requirements package in `approach.md` must trace
every functional requirement back to one of these. Source: the owner's
2026-09-17 directives for LWS, plus this setup session's own elaboration
of them; see the memory record `lws-directives-2026-09-17.md` for the
owner's original, unelaborated wording.

1. Code name LWS; every command, skill, and user-facing entrypoint starts
   with `lws`. Own public repo
   `github.com/LEAPWare-Software/LEAPWare-SessionKeeper`, set up exactly like
   LWH: identity `LEAPWare <leapware@outlook.com>`, rulesets, merge
   queue, squash, hosted CI, handoff protocol, proof records.
2. LWS is a rate-limit runway plugin: it watches a CLI session's own
   usage (5-hour and 7-day rate-limit windows) and, mechanically
   (allow/warn/deny, never by trust), moves the session through
   wind-down, landing, handoff-only, and retired states as usage climbs
   — the same shape as a RUNWAY-style gate proven elsewhere, but shipped
   here as its own standalone, reusable plugin.
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
6. Status line: shows ONE SHORT TAG for the session's runway state
   (proposed: `LWS ok`, `LWS WIND 80%`, `LWS LAND 90%`, `LWS HOFF 95%`,
   `LWS RET` for retired — final label text needs owner approval before
   freeze) and must never overwrite an existing status line segment.
   Usage readings (context %, 5h %, 7d %) are shared with LWH: LWH owns
   the usage *display* when it is present; LWS reads the same
   measurements and works alone, still showing its own tag, if LWH is
   absent.
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
16. Out of scope for lws: usage *display* in the status line when LWH is
    present (LWH's job — see directive 6); Proof of Completion CI
    enforcement for other repos (separate product).
17. Prove without doubt: a numbered testable requirements list; a test
    per rule proven by breaking it on purpose; a rehearsal with fake
    usage at 80/90/95 and retire (the owner does not watch the
    rehearsal — proof record only); a one-day comparison of LWS's
    readings against the CLI's own real usage display; a real
    unattended restart; an independent proof record.
