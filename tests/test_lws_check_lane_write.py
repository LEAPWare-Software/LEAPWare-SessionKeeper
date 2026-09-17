"""Tests for scripts/lws_check_lane_write.py's `evaluate` against fixtures.

Covers both hosts' event shape: Claude's Edit/Write/MultiEdit/NotebookEdit
`file_path`, and Codex's `apply_patch` patch-text `*** Update File:` header.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lws_check_lane_write import evaluate  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "lane_write"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_claude_edit_in_lane_allowed():
    out = evaluate("claude", _load("claude_edit_in_lane.json"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_claude_edit_shared_allowed():
    out = evaluate("claude", _load("claude_edit_shared.json"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_claude_edit_out_of_lane_denied():
    out = evaluate("claude", _load("claude_edit_out_of_lane.json"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "plugins/codex/lws/bin/lws_hook.py" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_codex_apply_patch_in_lane_allowed():
    out = evaluate("codex", _load("codex_apply_patch_in_lane.json"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_codex_apply_patch_out_of_lane_denied():
    out = evaluate("codex", _load("codex_apply_patch_out_of_lane.json"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "plugins/claude/lws/bin/lws_hook.py" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_unparseable_event_fails_open():
    out = evaluate("claude", {"hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": {}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_write_outside_the_repo_is_allowed(tmp_path):
    # The lane rules classify paths *within* this repo. A scratch file or
    # another project elsewhere on the machine is outside them entirely;
    # denying it would make a repo lane guard a machine-wide write block for
    # any session that has this repo as its project directory.
    outside = tmp_path / "notes.md"
    out = evaluate("claude", {"hook_event_name": "PreToolUse", "tool_name": "Write",
                              "tool_input": {"file_path": str(outside)}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_absolute_path_inside_the_repo_is_still_classified():
    # The out-of-repo allowance must not swallow absolute in-repo paths.
    inside = REPO_ROOT / "plugins" / "codex" / "lws" / "bin" / "lws_hook.py"
    out = evaluate("claude", {"hook_event_name": "PreToolUse", "tool_name": "Write",
                              "tool_input": {"file_path": str(inside)}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_extended_length_path_into_the_other_lane_is_denied():
    """A `\\\\?\\`-prefixed path must not evade the guard.

    `Path.resolve()` keeps the `\\\\?\\` prefix, so `relative_to(REPO_ROOT)`
    raises ValueError for a path that is genuinely *inside* the repo. Treating
    that ValueError as "outside the repo" would let any agent write into the
    other CLI's lane just by spelling the path differently.
    """
    inside = REPO_ROOT.resolve() / "plugins" / "codex" / "lws" / "bin" / "lws_hook.py"
    extended = "\\\\?\\" + str(inside)
    out = evaluate("claude", {"tool_name": "Write", "tool_input": {"file_path": extended}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.skipif(os.name != "nt", reason="Windows path casing is case-insensitive; POSIX's is not")
def test_case_differing_absolute_path_into_the_other_lane_is_denied():
    # A file that does not exist yet cannot be case-normalised by resolve(),
    # so the comparison against REPO_ROOT has to be case-insensitive on Windows.
    inside = REPO_ROOT.resolve() / "plugins" / "codex" / "does_not_exist_yet.py"
    shouted = str(inside).upper()
    out = evaluate("claude", {"tool_name": "Write", "tool_input": {"file_path": shouted}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_unresolvable_path_fails_closed():
    # None from _relativize means "known to be outside the repo". A path the
    # OS refuses to resolve is not known to be anything, so it must deny.
    nul = "\x00bad" + os.sep + "plugins" + os.sep + "codex" + os.sep + "x.py"
    out = evaluate("claude", {"tool_name": "Write", "tool_input": {"file_path": nul}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_non_edit_tool_is_ignored():
    out = evaluate("claude", {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": "plugins/codex/lws/bin/lws_hook.py"}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
