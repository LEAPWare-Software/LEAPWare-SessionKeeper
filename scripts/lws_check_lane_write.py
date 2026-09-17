#!/usr/bin/env python3
"""In-repo session lane hook: deny a write outside the calling CLI's lane.

This is a PreToolUse hook wired into THIS repo's own `.claude/settings.json`
and `.codex/hooks.json` (see those files), separate from the lws PRODUCT's
own `lws_version` policy hook — this one enforces owner directive 5 ("Codex
works only on the Codex part, Claude only on the Claude part...") on
whoever is editing THIS repo, using the same lane classification
`scripts/lws_lanes.py` uses for the commit-level `lws-lanes` CI check. The
CI check is the check of record (it looks at what was actually committed);
this hook is a same-session nudge that stops an out-of-lane edit before it
happens, so a contributor finds out immediately rather than at PR review.

Reads one JSON event from stdin:
  - Claude Code `PreToolUse` shape: `tool_name` in {Edit, Write, MultiEdit,
    NotebookEdit}, with a `file_path` or `notebook_path` in `tool_input`.
  - Codex `PreToolUse` shape: `tool_name` "apply_patch" (Codex's one
    file-editing tool, the documented equivalent of Claude's four — see
    docs/install-codex.md), with the patch text carrying one or more
    `*** (Add|Update|Delete) File: <path>` header lines, the apply_patch
    patch format's documented way of naming the file(s) a patch touches.

What this hook is NOT. It sees only the editing tools listed above, because
that is all its matcher subscribes to. A write performed through a shell --
`python -c "open(...)"`, a redirect, a patch piped into `git apply` -- never
reaches it at all. So it is a same-session nudge and must not be read as a
security boundary: it catches the mistake, not the determined evader. The
`lws-lanes` CI check is the enforcement of record, and it works on what was
actually committed, which no spelling of a path can disguise. Two adversarial
reviews of this file found path-aliasing evasions (`\\\\?\\`, `//?/`, UNC
admin shares) and all are closed below, but the shell-shaped hole is
structural and stays open by design.

If no file path can be determined from the event shape, this hook does
NOT deny — silently allowing an edit it can't parse is the safe failure
direction for a same-session nudge that is not itself the enforcement of
record (see module docstring); the `lws-lanes` CI check still catches an
out-of-lane commit regardless of what this hook did or didn't catch.

Usage:
    python scripts/lws_check_lane_write.py --agent claude
    python scripts/lws_check_lane_write.py --agent codex

Stdlib only. Always exits 0 (both hosts read the decision from the JSON
body, not the exit code — see docs/install-claude.md / docs/install-codex.md).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lws_lanes import REPO_ROOT, classify_path  # noqa: E402

CLAUDE_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
CODEX_EDIT_TOOLS = {"apply_patch"}

APPLY_PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)


def _extract_paths(agent: str, raw: dict) -> list[str]:
    tool_name = raw.get("tool_name")
    tool_input = raw.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    if agent == "claude" and tool_name in CLAUDE_EDIT_TOOLS:
        for key in ("file_path", "notebook_path"):
            value = tool_input.get(key)
            if isinstance(value, str) and value:
                return [value]
        return []

    if agent == "codex" and tool_name in CODEX_EDIT_TOOLS:
        for key in ("input", "patch", "command"):
            value = tool_input.get(key)
            if isinstance(value, str):
                matches = APPLY_PATCH_FILE_RE.findall(value)
                if matches:
                    return matches
        value = tool_input.get("file_path")
        if isinstance(value, str) and value:
            return [value]
        return []

    return []


WORKTREE_DIR = ".worktrees"
_MAX_ANCESTOR_WALK = 64


def _strip_extended_prefix(path_str: str) -> str:
    """Drop a Windows extended-length prefix, however it is spelled.

    `Path.resolve()` preserves this prefix, so a path that is genuinely inside
    the repo still fails `relative_to(REPO_ROOT)` with it attached. Normalising
    it away is what stops `\\\\?\\<repo>\\plugins\\codex\\x.py` from reading as
    "somewhere else entirely".

    Both separator spellings count. Windows accepts `//?/C:/...` as the same
    extended-length form and resolves it straight back to `\\\\?\\C:\\...`, so
    matching only the literal backslashes leaves the identical evasion open
    one keystroke away.
    """
    head = path_str[:8].replace("/", "\\")
    if not head.startswith("\\\\?\\"):
        return path_str
    rest = path_str[4:]
    if rest[:4].replace("/", "\\").upper() == "UNC\\":
        return "\\\\" + rest[4:]
    return rest


def _repo_relative_by_identity(target: Path) -> Optional[str]:
    """Repo-relative form of `target` found by filesystem identity, or None.

    A lexical comparison cannot see through path aliasing: `\\\\host\\C$\\...`,
    a `subst`ed drive and a junction all name the same file as `C:\\...` while
    sharing no common prefix with it. Walking up from the target to the first
    ancestor whose (st_dev, st_ino) matches the repo root answers the question
    the string comparison cannot.

    The target itself usually does not exist -- a Write creating a new file is
    the normal case -- so a failed stat keeps walking rather than giving up.
    """
    try:
        root_stat = REPO_ROOT.resolve().stat()
    except OSError:
        return None
    root_key = (root_stat.st_dev, root_stat.st_ino)

    tail: list[str] = []
    current = target
    for _ in range(_MAX_ANCESTOR_WALK):
        try:
            st = current.stat()
        except (OSError, ValueError):
            st = None
        if st is not None and (st.st_dev, st.st_ino) == root_key:
            return "/".join(reversed(tail))
        parent = current.parent
        if parent == current:
            return None
        tail.append(current.name)
        current = parent
    return None


def _strip_worktree_prefix(rel: str) -> str:
    """Map `.worktrees/<branch>/<path>` to `<path>`.

    A linked worktree is another checkout of this repo, not source sitting in
    it. Directive 19 and CLAUDE.md put every worktree exactly under
    `.worktrees/<branch>`, so classifying by the literal path makes every file
    in a worktree "other" -- and the guard then denies every edit made in one,
    including the edits needed to fix the guard.
    """
    parts = rel.split("/")
    if len(parts) > 2 and parts[0] == WORKTREE_DIR:
        return "/".join(parts[2:])
    return rel


def _relativize(path_str: str) -> Optional[str]:
    """Repo-relative form of `path_str`, or None when it is KNOWN to be outside.

    None means "not this repo's business" -- a scratch file, a temp directory,
    another project elsewhere on the machine. The lane rules classify paths
    *within* this repo, and denying everything else would turn a repo lane
    guard into a machine-wide write block for any session that has this repo
    as its project directory.

    None must never mean "could not tell". A path this function cannot resolve
    is handed back as-is, which classifies "other" and denies: an unreadable
    path is not evidence of innocence. None is earned only by a clean
    resolution that lands outside the repo both lexically AND by filesystem
    identity.
    """
    candidate = _strip_extended_prefix(path_str)
    try:
        p = Path(candidate)
        if not p.is_absolute():
            return _strip_worktree_prefix(candidate.replace("\\", "/"))
        resolved = p.resolve()
        root = REPO_ROOT.resolve()
    except (OSError, ValueError):
        return path_str.replace("\\", "/")  # undeterminable -> fail closed

    try:
        # PurePath.relative_to is case-insensitive on Windows, which is what
        # makes a differently-cased in-repo path still compare as in-repo.
        rel = str(resolved.relative_to(root)).replace("\\", "/")
    except ValueError:
        rel = _repo_relative_by_identity(resolved)
        if rel is None:
            return None  # outside lexically and by identity: genuinely elsewhere

    return _strip_worktree_prefix(rel)


def evaluate(agent: str, raw: dict) -> dict:
    paths = _extract_paths(agent, raw)
    offenders = []
    for path_str in paths:
        rel = _relativize(path_str)
        if rel is None:
            continue  # outside this repo -- see _relativize
        cls = classify_path(rel)
        if cls not in (agent, "shared"):
            offenders.append(rel)

    if offenders:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"lws lane guard: {agent} may not write outside its lane or shared "
                    f"paths: {', '.join(offenders)} (see docs/architecture.md, owner directive 5)"
                ),
            }
        }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True, choices=["claude", "codex"])
    args = parser.parse_args()

    raw_input = sys.stdin.read()
    try:
        raw_event = json.loads(raw_input) if raw_input.strip() else {}
    except json.JSONDecodeError:
        raw_event = {}

    print(json.dumps(evaluate(args.agent, raw_event)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
