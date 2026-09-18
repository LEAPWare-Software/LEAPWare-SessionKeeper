# LWS 1.0.0 — Master Plan

## Context

LWS (LEAPWare SessionKeeper) is a session runway plugin for AI coding CLIs. It
measures a session's consumption across three windows — context, 5-hour, 7-day —
moves the session through `wind-down → landing → handoff-only → retired`, enforces
allow/warn/deny via hooks, owns the usage display, and restarts the session
unattended after a window resets.

Today the repo is scaffold only: a pure `lws_core` engine, one no-op
`lws_version` rule, two plugin shells, CI, and governance tooling. **None of the
runway behaviour exists.** This plan takes it to 1.0.0.

A working implementation of the runway already exists and must be lifted from, not
reinvented: `a private sibling repository (path recorded outside this repo)` — `ops/runway/*.py`,
`.claude/hooks/ratelimit-gate.ps1`, `docs/runway.md`. It is proven by 250 tests, a
real Windows Task Scheduler rehearsal, and a 15/15 mutation-kill pass.

### BUILD IS ON HARD HOLD

The owner directed that LWS adopt the **LEAPWare BuildCraft SDLC**
(`leapware-hq\leapware-software\leapware-buildcraft`) and that **no LWS
implementation begins until BuildCraft is ready**. On inspection BuildCraft ships
only a no-op `lwb_version` rule; its stage/role/gate rules are undesigned, its
owner-directives file is a placeholder, every mode is warn-only until its own 1.1,
and there is no documented path to adopt it into an existing repo.

**This document is therefore a plan, not a licence to build.** Phase 0 below is the
release gate for the hold. Everything from Phase 1 onward is blocked.

---

## Architecture

Three layers, matching the existing scaffold:

```
core/lws_core/          pure engine: Event -> Decision. No host knowledge.
  runway.py             the state machine: readings -> tier
  policy/               thresholds + per-state tool denials (JSON, schema'd)
  handoff.py            handoff write + CONSUMED guard
  restart/              scheduler-adapter interface + platform backends
adapters/claude/        Claude Code hook + statusLine I/O
adapters/codex/         Codex equivalents (see Phase 1 spike)
plugins/{claude,codex}/ vendored, installable plugin trees
```

### The measurement constraint — the single most important design fact

`rate_limits` appears in **exactly one place** in the Claude Code binary: the
**statusLine command's stdin**. No hook event carries it. Verified in the reference implementation's gate
header and corroborated in `leapware-watchtower/docs/limitations.md`.

So the data path is necessarily:

```
CLI --stdin JSON--> LWS statusLine --writes--> signal file --read by--> PreToolUse hook
```

Payload fields consumed: `rate_limits.five_hour.{used_percentage,resets_at}`,
`rate_limits.seven_day.{...}`, `context_window.used_percentage`, `session_id`,
`model.display_name`.

Consequences the build must honour:
- LWS **must** ship its own statusLine registration. A hook alone is blind.
- Per-session signal files, not one shared file. The reference implementation measured the shared file being
  clobbered across accounts (`5h 65% → 67% → missing`, seconds apart).
- Readings older than 10 minutes are absent, never stale-but-valid.
- The gate **fails open** on every read problem. A bug must never become the outage
  it exists to prevent.

### Locked decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Readings come from statusLine stdin via a per-session signal file | Only source that exists |
| 2 | LWS ships its own statusLine that **composes** — renders its segment, passes through others | Directive 6: never overwrite an existing segment |
| 3 | Restart via **scheduler adapters per platform** — Task Scheduler / launchd / cron behind one interface | Lifts the reference implementation's proven Windows path; directive 8 demands all three |
| 4 | Thresholds **configurable**, defaults 80/90/95 | Owner decision |
| 5 | Gate **dispatch-only** (`Agent`, `SendMessage`), **policy-driven** per state | Gating Edit/Write/Bash blocks the exit path — the session needs them to write and push the handoff |
| 6 | Tier = **max** of present windows; a missing window is not in the max | the reference implementation's proven rule |
| 7 | `HANDOFF-PATH:` marker is the escape hatch. `ORDER-PATH` (the reference implementation's trading concept) dropped | Generalise, don't inherit domain |
| 8 | 1.0.0 includes all four capabilities: states+enforcement, display, handoff+guard, unattended restart | Owner decision; directive 15 |

---

## SDLC

Stages per BuildCraft decision D2: `design → qa → review → security → delivery →
release → operations`. Each phase below names its stage, its artifact, and the gate
that closes it. Until BuildCraft ships real gate rules, gates are enforced by this
repo's own CI plus a proof record per directive 7.

---

## Phase 0 — unblock (the only phase that may start now)

**Stage:** design. **Gate:** all four open PRs merged; BuildCraft hold resolved.

- [ ] Land the open PRs in order: **#11** (mission), **#9** ✅ merged, **#10**
      (hosted-runner check — needs rebase onto `main` + **squash**, its
      `lws-env-leak-history` step scans every commit), **#8** (privacy fix — owner's
      private names are public on `main` until it lands), **#7** (HANDOFF).
- [ ] Build the graphify graph for this repo (`graphify install --platform claude`
      first — installed skill is 0.8.31 against package 0.9.56 — then index).
- [ ] Write the **numbered testable requirements list** per
      `docs/requirements/approach.md`, tracing every requirement to a directive.
      This is the design-stage artifact and the input to every later phase.
- [ ] **Decide the BuildCraft hold.** Options, for the owner: (a) BuildCraft's
      requirements package becomes Phase 0.5 and LWS is its first consumer;
      (b) adopt the stage vocabulary only and drop the hard dependency; (c) keep
      holding. On current evidence (c) is open-ended.

---

## Phase 1 — Codex feasibility spike

**Stage:** design. **Gate:** a written answer, not code.

The reference implementation is Claude Code only. There is **no Codex signal source, no Codex launch path,
no Codex transcript format** — for Codex this is a from-scratch build informed by
the shape of the Claude solution.

- [ ] Does Codex expose usage readings at all, by any mechanism?
- [ ] Can a Codex session be launched headlessly with a prompt, as
      `claude.exe "<prompt>"` is?
- [ ] Is there a Codex equivalent of transcript-mtime liveness detection?
- [ ] **Output:** a recommendation on directive 4 parity. If Codex cannot restart
      unattended, the owner decides: full parity blocks the release, or Codex ships
      degraded. Do not guess — this is the owner's call, informed by the spike.

---

## Phase 2 — measurement + display

**Stage:** design → qa. **Gate:** readings proven against the CLI's own display for
one day (directive 17).

- [ ] `adapters/claude/statusline.py` — read stdin JSON, render the segment,
      **compose** with any existing segment, write a per-session signal file.
      Format: `ctx 44%  5h 24% (23m)  7d 19% (09/24 1am)` — 5h as duration
      remaining, 7d as absolute stamp. State tag appears **only when past normal**.
- [ ] Reset-time formatting: lift the shape of the reference implementation's `ResetTime`/`Duration`/`Stamp`
      (`ops/runway/global/statusline.ps1`), reimplemented in Python.
- [ ] Signal schema, versioned, per-session, atomic write.
- [ ] Staleness: >10 minutes = absent.
- [ ] **Proof:** one-day comparison of LWS's readings against the CLI's own display.

---

## Phase 3 — the runway state machine

**Stage:** design → qa → review. **Gate:** a test per rule, each proven by breaking
it on purpose.

- [ ] `core/lws_core/runway.py` — pure function: readings + policy → tier. No I/O.
- [ ] Tier table, thresholds from policy (defaults 80/90/95), tier = max of present
      windows.
- [ ] Sticky first-crossing-of-95 per window per reset cycle.
- [ ] RETIRED is one-way within a process, and **independent of the signal**.
- [ ] Fail open on absent/stale/malformed readings, always.
- [ ] Policy schema extension in `core/policy/` for thresholds and per-state tool
      denials.

---

## Phase 4 — enforcement

**Stage:** qa → review → security. **Gate:** mutation pass — remove each guard,
confirm a test dies.

- [ ] `PreToolUse` hook on `Agent|SendMessage`, both CLIs.
- [ ] Deny emitted as `hookSpecificOutput.permissionDecision`, **exit code always
      0**. A non-zero exit is itself a block and would turn any bug into an outage.
- [ ] Per-state denials from policy; `HANDOFF-PATH:` marker escape hatch;
      read-only recon subagent types exempt at landing, **not** at handoff-only.
- [ ] Exactly one JSON document per call.

---

## Phase 5 — handoff + consumed guard

**Stage:** qa → review → security. **Gate:** replay attempt provably refused.

- [ ] Generic, project-agnostic handoff schema. **Do not** inherit the reference implementation's
      `**In flight` Markdown contract, its `gh pr list`/`git worktree`/KEEL facts
      block, or its 8000-byte cap.
- [ ] CONSUMED guard — lift the reference implementation's `consume()` hard-link exclusivity verbatim in
      shape: write temp, `os.link` to `consumed-<commit>.json`, `FileExistsError`
      means someone else won. Verify a POSIX equivalent holds.
- [ ] Window claim guard (`claim_window`) — closes the two-sessions-retire-in-one-
      window race that a reviewer caught in the reference implementation.
- [ ] Decide what "durable handoff" means with no git remote. The reference implementation assumes push to
      `main`; LWS must not.
- [ ] **Forbidden:** the reference implementation's `lint_problems()` reads `CLAUDE.md` at runtime. Directive
      3 bans this. It must not be ported.

---

## Phase 6 — unattended restart

**Stage:** delivery. **Gate:** a real unattended restart (directive 17).

- [ ] Scheduler-adapter interface + three backends: Task Scheduler (lift the reference implementation's
      `register_task`/`task_spec` nearly as-is), launchd, cron.
- [ ] Launch: detached, new console, breakaway from job. Handoff passed as
      **plain-text prompt in argv** — the reference implementation uses no `--resume`/`--continue`.
- [ ] Pre-launch guards, all of them: package record + retired marker exist,
      commit on `origin/main`, **no other active non-retired session** in the repo,
      package not already CONSUMED.
- [ ] Margin after reset (the reference implementation uses 2 minutes).
- [ ] **Known gap inherited from the reference implementation:** a genuine rate-limit exhaustion → restart
      has never fired, only a fabricated-package rehearsal. LWS needs its own live
      validation. Behaviour when the machine is asleep or logged off is unrehearsed.

---

## Phase 7 — release + operations

**Stage:** release → operations.

- [ ] Rehearsal at fake 80/90/95 and retire, proof record only, owner does not watch.
- [ ] Size budget check (directive 14) — a hard number, enforced in CI.
- [ ] Independent proof record; `LWS - Alert: <id> DONE` announcement.
- [ ] Tag 1.0.0; GitHub Apps (`lws-claude`, `lws-codex`) created and recorded.

---

## Lift directly from the reference implementation

- `ops/runway/restart.py` — CONSUMED hard-link guard, window claim, Task Scheduler
  registration, `active_sessions()` transcript-mtime liveness, `launch_session()`.
  Stdlib-only, Claude-shaped but not shaped like the reference implementation, fully unit-tested.
- The RUNWAY tier ladder in `ratelimit-gate.ps1` (~lines 712-787) — reimplemented in
  Python, minus `ORDER-PATH`.
- The per-session signal write pattern and its atomic-write discipline.
- The hard-link "claim exactly once" primitive.
- `build_global_copy.py`'s region-marker + `--check` drift pattern.

## Must be rebuilt

- All of it in **Python** — the reference implementation's gate is PowerShell 5.1.
- **Mac and Linux scheduler backends** — do not exist.
- **All Codex support** — does not exist in any form.
- The whole measurement layer without depending on `lw-watchtower`'s plugin-data
  directory or its signal schema.
- A generic handoff contract, replacing the reference implementation's domain-specific one.
- LWS-namespaced state paths.

## Risks

1. **BuildCraft hold is open-ended.** Highest risk to the whole plan.
2. **Codex parity may be impossible** for restart. Phase 1 exists to find out.
3. **Mac/Linux restart is unproven** anywhere. Two of three backends are new.
4. **Live restart proof** has never been obtained, even in the reference implementation.
5. **statusLine composition contract does not exist.** Getting it wrong blanks the
   operator's status row — the reference implementation refused its own registration for exactly this reason.

## Verification (directive 17)

Numbered testable requirements list · a test per rule proven by breaking it on
purpose · mutation pass over every guard · rehearsal at 80/90/95 and retire ·
one-day reading comparison against the CLI's own display · a real unattended
restart · an independent proof record.
