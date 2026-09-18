#!/usr/bin/env python3
"""Validate and regenerate the "In flight" block of HANDOFF.md.

HANDOFF.md is the repo's own re-derivable state file (see
docs/handoff-protocol.md). This script is the ONLY thing that writes the
generated block; everything else in HANDOFF.md is prose a human/agent
wrote by hand and this script never touches.

Usage:
    python scripts/lws_handoff.py --check                      # validate HANDOFF.md, exit 1 on failure
    python scripts/lws_handoff.py --check-live
        # --check, plus re-derive the generated block's own facts (main SHA,
        # open PR list) from live git/gh and fail loudly on mismatch or on
        # git/gh being unavailable. PR-only in CI: needs `gh` auth and a
        # meaningful origin/main to diff against.
    python scripts/lws_handoff.py --write [--cli NAME] [--session ID]
        # regenerate the generated block in place. --cli and --session
        # record which CLI/session wrote this handoff and its own id, so a
        # reader can tell which session last re-derived state; both are
        # free-form strings and optional (default "unknown" / an
        # auto-generated timestamp-based id) -- this script does not
        # validate them against any external identity source.

Stdlib only. Cross-platform (no shell strings, argv lists to subprocess).
No network calls other than what `gh` itself performs; --check never
shells out at all, so it is safe to run offline / in CI without `gh` auth
for read-only validation of the file shape.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HANDOFF_PATH = REPO_ROOT / "HANDOFF.md"
PROOF_DIR = REPO_ROOT / "proof"

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

SIZE_CAP_BYTES = 6000

HANDOFF_PROTOCOL_PATH = REPO_ROOT / "docs" / "handoff-protocol.md"
# Generous on purpose: this is the designated overflow target when
# HANDOFF.md itself hits its own (tighter) cap, so it needs headroom -- the
# point of this cap is only to stop unbounded growth going unnoticed, not
# to force trimming at the same size as HANDOFF.md.
HANDOFF_PROTOCOL_CAP_BYTES = 12000

BEGIN_MARKER = "<!-- lws-handoff:begin -->"
END_MARKER = "<!-- lws-handoff:end -->"

# Two textually unmistakable forms for the "Open PRs:" section -- see
# _generate_block(). Never write anything else there for the zero/unknown
# cases; --check-live matches on these exact strings.
NONE_OPEN_MARKER = "(none open)"
UNKNOWN_PR_MARKER = "(UNKNOWN - gh unavailable, this block is not trustworthy)"

# A block generated immediately before its own commit can only ever name
# the commit's *parent* as "main SHA" -- _generate_block() runs, then the
# result is committed, so the commit that ships the block is necessarily
# one commit ahead of what the block itself could have observed. Exact
# equality between the committed SHA and origin/main's live tip would
# therefore fail on every single legitimate PR. MAX_SHA_LAG bounds how far
# behind is still "current when generated" rather than "stale": an ancestor
# within this many commits of the tip passes, anything further behind (or
# not an ancestor at all -- a rewritten/force-pushed history) fails.
MAX_SHA_LAG = 5

_MAIN_SHA_RE = re.compile(r"^main SHA:\s*(\S+)\s*$", re.MULTILINE)
_PR_NUMBER_RE = re.compile(r"#(\d+)")

REQUIRED_SECTIONS = [
    "# HANDOFF",
    "## Start of session",
    "## In flight",
    "## Re-derive state",
    "## Hard rules",
    "## Traps",
]

# Patterns that must never appear in a committed HANDOFF.md: an absolute
# path (POSIX or a Windows drive letter) or a forbidden substring (see
# _forbidden_substrings() below). This keeps the file honest about SACRED
# (no local-environment dependence) and keeps a private identity out of a
# machine-read file.
FORBIDDEN_PATTERNS = [
    re.compile(r"[A-Za-z]:\\"),  # Windows drive letter, e.g. C:\
    re.compile(r"(?<!\w)/(?:Users|home)/\w+"),  # POSIX home directory
]

# Generic default: nothing here names a real project or person. An adopter
# who forks/installs this repo supplies their own needles via a local,
# gitignored file (PRIVATE_NAMES_FILE, shared with scripts/lws_check_env_leak.py)
# rather than committing them here -- committing them would recreate the
# exact leak this check exists to catch.
DEFAULT_FORBIDDEN_SUBSTRINGS = ["example-private-project"]

PRIVATE_NAMES_FILE = ".private-names"


def _forbidden_substrings() -> list[str]:
    """DEFAULT_FORBIDDEN_SUBSTRINGS plus any needles from a local,
    gitignored `.private-names` file at REPO_ROOT (one per line, blank
    lines and `#`-comments ignored). Absent file: default only.
    """
    names = list(DEFAULT_FORBIDDEN_SUBSTRINGS)
    try:
        text = (REPO_ROOT / PRIVATE_NAMES_FILE).read_text(encoding="utf-8")
    except OSError:
        return names
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            names.append(stripped.lower())
    return names


class ValidationError(Exception):
    """Raised by _validate() with a human-readable reason."""


class LiveCheckError(Exception):
    """Raised by --check-live's strict git/gh helpers when authoritative
    state cannot be obtained at all (git/gh missing, gh unauthenticated,
    gh timed out, unparseable output). --check-live must fail loudly on
    this, never degrade to "unavailable" -- silently degrading is the
    exact defect this mode exists to catch.
    """


def _run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def _run_gh_with_status(args: list[str]) -> tuple[bool, str]:
    """(ok, stdout). ok is False for "gh missing/timed out/nonzero exit" --
    the only way to tell that apart from "gh ran fine and printed nothing",
    which _run_gh() below collapses to the same "" and which is exactly the
    ambiguity FIX 2 removes from the committed block."""
    try:
        result = subprocess.run(
            ["gh", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, ""
    if result.returncode != 0:
        return False, ""
    return True, result.stdout.strip()


def _run_gh(args: list[str]) -> str:
    _ok, stdout = _run_gh_with_status(args)
    return stdout


def _run_git_strict(args: list[str]) -> str:
    """Like _run_git, but raises LiveCheckError instead of degrading. Only
    used by --check-live, which must fail loudly rather than silently
    passing on missing/broken git."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise LiveCheckError(f"git is not available: {exc}") from exc
    if result.returncode != 0:
        raise LiveCheckError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _run_gh_strict(args: list[str]) -> str:
    """Like _run_gh, but raises LiveCheckError instead of degrading. Only
    used by --check-live, which must fail loudly rather than silently
    passing on missing/unauthenticated gh."""
    try:
        result = subprocess.run(
            ["gh", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise LiveCheckError(f"gh is not available or timed out: {exc}") from exc
    if result.returncode != 0:
        raise LiveCheckError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _git_is_ancestor(candidate: str, ref: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", candidate, ref],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise LiveCheckError(f"git is not available: {exc}") from exc
    return result.returncode == 0


def _git_distance(candidate: str, ref: str) -> int:
    """Number of commits ref has that candidate does not -- how far behind
    candidate is. Raises LiveCheckError if git or its output is unusable."""
    raw = _run_git_strict(["rev-list", "--count", f"{candidate}..{ref}"])
    try:
        return int(raw)
    except ValueError as exc:
        raise LiveCheckError(f"could not parse commit distance from 'git rev-list --count': {raw!r}") from exc


def _extract_main_sha(text: str) -> str | None:
    match = _MAIN_SHA_RE.search(text)
    return match.group(1) if match else None


def _extract_open_pr_section(text: str) -> str:
    """The text of the "Open PRs:" section: from that heading up to the
    next blank line (the block always writes one blank line before the
    following section -- see _generate_block())."""
    marker = "Open PRs:"
    idx = text.index(marker)
    rest = text[idx + len(marker):]
    end = rest.index("\n\n") if "\n\n" in rest else len(rest)
    return rest[:end].strip()


def _extract_pr_numbers(section: str) -> set[int]:
    return {int(m) for m in _PR_NUMBER_RE.findall(section)}


def _check_sha_live(committed_sha: str) -> list[str]:
    """Re-derive origin/main's tip and compare it against the SHA committed
    in HANDOFF.md's generated block. See MAX_SHA_LAG for why exact equality
    is wrong."""
    tip = _run_git_strict(["rev-parse", "origin/main"])
    if committed_sha == tip:
        return []
    if not _git_is_ancestor(committed_sha, tip):
        return [
            f"committed main SHA {committed_sha!r} is not origin/main's tip {tip!r}, "
            "and not an ancestor of it either (rewritten history, or the wrong SHA entirely) "
            "-- HANDOFF.md's generated block is wrong"
        ]
    distance = _git_distance(committed_sha, tip)
    if distance > MAX_SHA_LAG:
        return [
            f"committed main SHA {committed_sha!r} is {distance} commits behind origin/main's tip {tip!r}, "
            f"more than the {MAX_SHA_LAG}-commit structural lag allowance -- the block is stale"
        ]
    return []


def _check_prs_live(section_text: str) -> list[str]:
    """Re-derive the live set of open PR numbers and compare it against
    the numbers named in HANDOFF.md's "Open PRs:" section."""
    if UNKNOWN_PR_MARKER in section_text:
        return [
            "HANDOFF.md's Open PRs section is the UNKNOWN/gh-unavailable form -- "
            "it says itself it is not trustworthy, so --check-live treats it as a failure"
        ]
    committed = _extract_pr_numbers(section_text)
    raw = _run_gh_strict(["pr", "list", "--state", "open", "--json", "number"])
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LiveCheckError(f"could not parse 'gh pr list' JSON output: {exc}") from exc
    live = {int(item["number"]) for item in parsed}
    extra = sorted(committed - live)
    missing = sorted(live - committed)
    if extra or missing:
        return [
            "HANDOFF.md's Open PRs section does not match origin's actual open PRs -- "
            f"extra (committed but not actually open): {extra}, missing (open but not committed): {missing}"
        ]
    return []


def _check_protocol_cap() -> list[str]:
    if not HANDOFF_PROTOCOL_PATH.exists():
        return []
    size = len(HANDOFF_PROTOCOL_PATH.read_bytes())
    if size > HANDOFF_PROTOCOL_CAP_BYTES:
        return [f"{HANDOFF_PROTOCOL_PATH} is {size} bytes, over the {HANDOFF_PROTOCOL_CAP_BYTES}-byte cap"]
    return []


def _utc_now_iso() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _proof_state_lines() -> list[str]:
    """One line per proof/*.json deliverable: id and PROVEN/INVALID/reason.

    Reuses scripts/lws_check_proof.py's own record validator so this never
    drifts from what the `lws-proof` CI job itself enforces. An empty
    proof/ directory (the common case today -- see proof/README.md) is not
    an error; it just means the list is "(none yet)".
    """
    import lws_check_proof  # local import: only --write needs this, --check must not

    if not PROOF_DIR.is_dir():
        return ["(none yet)"]

    records = sorted(p for p in PROOF_DIR.glob("*.json") if p.name != "schema.json")
    if not records:
        return ["(none yet)"]

    lines: list[str] = []
    for path in records:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            lines.append(f"- {path.name}: INVALID (bad JSON: {exc})")
            continue
        errors = lws_check_proof._validate_record(path, data)
        deliverable = data.get("deliverable", path.stem) if isinstance(data, dict) else path.stem
        if errors:
            lines.append(f"- {deliverable}: INVALID ({errors[0]})")
        else:
            lines.append(f"- {deliverable}: PROVEN (commit {data.get('commit')})")
    return lines


def _generate_block(cli: str = "unknown", session: str = "unknown") -> str:
    """Build the text between BEGIN_MARKER and END_MARKER from git/gh state.

    Every value here is re-derived live; nothing is carried over from a
    previous run. gh calls degrade to "unavailable" rather than failing
    the whole regeneration, since --write may run without gh auth. `cli`
    and `session` are supplied by the caller (`--cli`/`--session`), not
    derived -- see the module docstring for why.
    """
    main_sha = _run_git(["rev-parse", "origin/main"]) or _run_git(["rev-parse", "main"]) or "unknown"
    generated_at = _utc_now_iso()

    ok, pr_list = _run_gh_with_status(
        [
            "pr",
            "list",
            "--state",
            "open",
            "--json",
            "number,title,headRefName,statusCheckRollup",
            "--template",
            "{{range .}}#{{.number}} {{.title}} ({{.headRefName}})\n{{end}}",
        ]
    )
    # Two textually unmistakable outcomes -- never the old ambiguous
    # "(unavailable: ... or no open PRs)", which cannot be told apart from
    # a genuinely empty list and caused a stale block to pass unnoticed.
    if not ok:
        pr_section = UNKNOWN_PR_MARKER
    elif pr_list.strip():
        pr_section = pr_list.strip()
    else:
        pr_section = NONE_OPEN_MARKER

    lines = [
        BEGIN_MARKER,
        "",
        f"Generated: {generated_at}",
        f"main SHA: {main_sha}",
        f"CLI: {cli}",
        f"Session: {session}",
        "",
        "Open PRs:",
        pr_section,
        "",
        "Deliverable proof state (from proof/):",
        *_proof_state_lines(),
        "",
        END_MARKER,
    ]
    return "\n".join(lines) + "\n"


def _validate(text: str) -> list[str]:
    errors: list[str] = []

    size = len(text.encode("utf-8"))
    if size > SIZE_CAP_BYTES:
        errors.append(f"HANDOFF.md is {size} bytes, over the {SIZE_CAP_BYTES}-byte cap")

    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"missing required section heading: {section!r}")

    begin_count = text.count(BEGIN_MARKER)
    end_count = text.count(END_MARKER)
    if begin_count != 1:
        errors.append(f"expected exactly one {BEGIN_MARKER!r}, found {begin_count}")
    if end_count != 1:
        errors.append(f"expected exactly one {END_MARKER!r}, found {end_count}")
    if begin_count == 1 and end_count == 1:
        begin_idx = text.index(BEGIN_MARKER)
        end_idx = text.index(END_MARKER)
        if end_idx < begin_idx:
            errors.append("end marker appears before begin marker")

    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            errors.append(f"forbidden pattern found (absolute path): {pattern.pattern!r}")

    lowered = text.lower()
    for needle in _forbidden_substrings():
        if needle in lowered:
            errors.append(f"forbidden substring found: {needle!r}")

    return errors


def cmd_check() -> int:
    if not HANDOFF_PATH.exists():
        print(f"FAIL: {HANDOFF_PATH} does not exist", file=sys.stderr)
        return 1
    text = HANDOFF_PATH.read_text(encoding="utf-8")
    errors = _validate(text)
    errors.extend(_check_protocol_cap())
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"OK: {HANDOFF_PATH} passes all checks ({len(text.encode('utf-8'))} bytes)")
    return 0


def cmd_check_live() -> int:
    """Everything --check does, plus re-deriving the generated block's own
    facts (main SHA, open PR list) from live git/gh state and failing on
    mismatch. Unlike --check, this must fail loudly rather than degrade
    when git/gh are unavailable -- see LiveCheckError."""
    base_rc = cmd_check()
    if base_rc != 0:
        return base_rc

    text = HANDOFF_PATH.read_text(encoding="utf-8")
    errors: list[str] = []
    try:
        main_sha = _extract_main_sha(text)
        if main_sha is None:
            errors.append("could not find a 'main SHA:' line in HANDOFF.md's generated block")
        else:
            errors.extend(_check_sha_live(main_sha))

        pr_section = _extract_open_pr_section(text)
        errors.extend(_check_prs_live(pr_section))
    except LiveCheckError as exc:
        print(f"FAIL: --check-live could not get authoritative state: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("OK: HANDOFF.md's generated block matches live git/gh state")
    return 0


def cmd_write(cli: str = "unknown", session: str = "unknown") -> int:
    if not HANDOFF_PATH.exists():
        print(f"FAIL: {HANDOFF_PATH} does not exist; cannot regenerate a block into nothing", file=sys.stderr)
        return 1
    text = HANDOFF_PATH.read_text(encoding="utf-8")
    if text.count(BEGIN_MARKER) != 1 or text.count(END_MARKER) != 1:
        print("FAIL: HANDOFF.md must already contain exactly one begin/end marker pair to regenerate", file=sys.stderr)
        return 1
    begin_idx = text.index(BEGIN_MARKER)
    end_idx = text.index(END_MARKER) + len(END_MARKER)
    new_block = _generate_block(cli=cli, session=session).rstrip("\n")
    new_text = text[:begin_idx] + new_block + text[end_idx:]
    HANDOFF_PATH.write_text(new_text, encoding="utf-8", newline="\n")
    errors = _validate(new_text)
    if errors:
        for error in errors:
            print(f"WARN after write: {error}", file=sys.stderr)
        return 1
    print(f"OK: wrote regenerated block to {HANDOFF_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="validate HANDOFF.md, exit 1 on failure")
    group.add_argument(
        "--check-live",
        action="store_true",
        help="--check, plus re-derive the block's main SHA and open-PR list from git/gh and fail on mismatch",
    )
    group.add_argument("--write", action="store_true", help="regenerate the generated block in place")
    parser.add_argument(
        "--cli", default="unknown", help="which CLI is writing this handoff, e.g. claude or codex"
    )
    parser.add_argument(
        "--session", default="unknown", help="this session's own id, for the generated block"
    )
    args = parser.parse_args(argv)

    if args.check:
        return cmd_check()
    if args.check_live:
        return cmd_check_live()
    return cmd_write(cli=args.cli, session=args.session)


if __name__ == "__main__":
    sys.exit(main())
