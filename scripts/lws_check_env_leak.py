#!/usr/bin/env python3
"""CI check `lws-env-leak`: no local-environment or private-project leak.

SACRED (owner directive 8): this repo's build/test/deploy must not depend
on, or leak, anything about the machine or private projects it was built
on. Scans every git-tracked, non-binary file for:

  - a Windows drive letter (`C:\\...`)
  - a POSIX home directory (`/Users/<name>` or `/home/<name>`)
  - a hard-coded interpreter invocation: `py -3`, `py -3.NN`, or an
    absolute path to a `python`/`python3`/`python.exe` binary
  - a private-project name leak: a generic placeholder needle
    (`example-private-project`) by default, case-insensitive, plus any
    adopter-supplied needles listed one per line in a gitignored local
    file (`.private-names` at the repo root); absent that file, the check
    still runs with the generic default alone

Allow-listed: this script's own pattern data (it necessarily names the
patterns it looks for) and files under `tests/**/fixtures/**` whose
filename or path makes clear they are synthetic (contain `fixture`).

A working-tree scan alone misses a leak that was committed and then
removed again -- it is still sitting in the branch's history, and a
`git clone` (or a marketplace pull) carries every commit, not just the
final tree. `--range <base>..<head>` additionally scans the ADDED lines
of every commit in that range (via `git log -p --unified=0`), so a leak
that was committed then reverted within the same PR is still caught, not
just the leaks visible in the final diff.

Usage:
    python scripts/lws_check_env_leak.py
    python scripts/lws_check_env_leak.py --range <base-sha>..<head-sha>

Stdlib only. Exits 0 and prints "lws-env-leak check passed" on success;
otherwise prints every finding (file:line, or commit:file for a
history-only finding) and exits 1.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent
SELF_PATH = Path(__file__).resolve()

DRIVE_LETTER = re.compile(r"\b[A-Za-z]:\\[\w][\w.\- ]")
POSIX_HOME = re.compile(r"(?<!\w)/(?:Users|home)/[\w.\-]+")
PY_DASH3 = re.compile(r"\bpy\s+-3(\.\d+)?\b")
HARDCODED_INTERPRETER = re.compile(
    r"(?:[A-Za-z]:\\|/)(?:[\w.\-]+[\\/])*python3?(?:\.exe)?(?=[\s\"'`]|$)"
)

# Generic default: nothing here names a real project or person. An adopter
# who forks/installs this repo supplies their own needles via a local,
# gitignored file (PRIVATE_NAMES_FILE) rather than committing them here --
# committing them would recreate the exact leak this check exists to catch.
DEFAULT_PRIVATE_NAME_SUBSTRINGS = ["example-private-project"]

PRIVATE_NAMES_FILE = ".private-names"


def _private_name_substrings() -> list[str]:
    """DEFAULT_PRIVATE_NAME_SUBSTRINGS plus any needles from a local,
    gitignored `.private-names` file at REPO_ROOT (one per line, blank
    lines and `#`-comments ignored). Absent file: default only. Read
    fresh on every call so a caller that reassigns REPO_ROOT (as the test
    suite does, to point at a throwaway fixture repo) picks up that
    repo's own file, not this one's.
    """
    names = list(DEFAULT_PRIVATE_NAME_SUBSTRINGS)
    try:
        text = (REPO_ROOT / PRIVATE_NAMES_FILE).read_text(encoding="utf-8")
    except OSError:
        return names
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            names.append(stripped.lower())
    return names


_BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".pyc"}


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line]


# Files that necessarily carry this scanner's own pattern data (or, for a
# test file, synthetic needles that exercise it) rather than a real leak.
# The lwr_* aliases below are pre-rename paths (LEAPWare-Runway -> LEAPWare-
# SessionKeeper, lwr -> lws): `--range` walks every historical commit's own
# diff by its own path, so a commit added before the rename still shows the
# old name and must stay exempt too.
_PATTERN_DATA_EXEMPT = {
    "scripts/lws_check_env_leak.py",
    "scripts/lws_handoff.py",
    "tests/core/test_lws_handoff.py",
    "tests/test_lws_check_env_leak.py",
    "scripts/lwr_check_env_leak.py",
    "scripts/lwr_handoff.py",
    "tests/core/test_lwr_handoff.py",
    "tests/test_lwr_check_env_leak.py",
}


def _is_exempt_posix(posix: str) -> bool:
    if posix in _PATTERN_DATA_EXEMPT:
        return True
    return "fixture" in posix.lower()


def _is_exempt(path: Path) -> bool:
    if path == SELF_PATH:
        return True
    return _is_exempt_posix(path.relative_to(REPO_ROOT).as_posix())


def _findings_for_line(rel: str, lineno: int, line: str) -> list[str]:
    findings: list[str] = []
    if DRIVE_LETTER.search(line):
        findings.append(f"{rel}:{lineno}: Windows drive letter")
    if POSIX_HOME.search(line):
        findings.append(f"{rel}:{lineno}: POSIX home directory path")
    if PY_DASH3.search(line):
        findings.append(f"{rel}:{lineno}: hard-coded 'py -3' interpreter launch")
    if HARDCODED_INTERPRETER.search(line):
        findings.append(f"{rel}:{lineno}: absolute path to a python interpreter")
    lowered = line.lower()
    for needle in _private_name_substrings():
        if needle in lowered:
            findings.append(f"{rel}:{lineno}: private-project name leak ('{needle}')")
    return findings


def check() -> list[str]:
    findings: list[str] = []
    for path in _tracked_files():
        if not path.is_file() or path.suffix.lower() in _BINARY_SUFFIXES:
            continue
        if _is_exempt(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        for lineno, line in enumerate(text.splitlines(), start=1):
            findings.extend(_findings_for_line(rel, lineno, line))
    return findings


# `git log -p` commit boundary; captures the full 40-hex sha.
_COMMIT_RE = re.compile(r"^commit ([0-9a-f]{40})")
# `+++ b/<path>` names the file a hunk's added lines belong to; `/dev/null`
# means the file was deleted in this commit (nothing was added to it).
_NEW_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")
# `@@ -<old-start>[,<old-count>] +<new-start>[,<new-count>] @@`
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def check_range(rev_range: str) -> list[str]:
    """Scan the ADDED lines of every commit in `rev_range` (base..head).

    Uses `git log -p --unified=0` so each hunk contains only changed lines
    (no surrounding context to mis-scan) and walks it by hand: a commit
    that added a leak and a later commit in the same range that removed it
    again is still caught, because every commit's own diff is scanned, not
    just the net base..head diff.
    """
    result = subprocess.run(
        ["git", "log", "-p", "--unified=0", "--no-color", "--no-textconv", rev_range],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    findings: list[str] = []
    commit_sha = "?"
    rel = None
    next_new_line = None

    for raw_line in result.stdout.splitlines():
        commit_match = _COMMIT_RE.match(raw_line)
        if commit_match:
            commit_sha = commit_match.group(1)[:12]
            rel = None
            next_new_line = None
            continue

        new_file_match = _NEW_FILE_RE.match(raw_line)
        if new_file_match:
            candidate = new_file_match.group(1)
            rel = None if candidate == "dev/null" else PurePosixPath(candidate).as_posix()
            next_new_line = None
            continue

        hunk_match = _HUNK_RE.match(raw_line)
        if hunk_match:
            next_new_line = int(hunk_match.group(1))
            continue

        if rel is None or next_new_line is None or _is_exempt_posix(rel):
            continue

        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            content = raw_line[1:]
            for f in _findings_for_line(rel, next_new_line, content):
                findings.append(f"{commit_sha} {f}")
            next_new_line += 1
        # Removed ("-") lines don't advance the new-file line counter, and
        # unified=0 emits no context lines, so nothing else to track here.

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--range",
        dest="rev_range",
        default=None,
        help="also scan added lines of every commit in base..head (e.g. origin/main..HEAD)",
    )
    args = parser.parse_args()

    findings = check()
    if args.rev_range:
        findings.extend(check_range(args.rev_range))
    if findings:
        for f in findings:
            print(f"FAIL: {f}")
        return 1
    print("lws-env-leak check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
