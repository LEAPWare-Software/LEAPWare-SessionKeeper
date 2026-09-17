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


def _unc_alias_of(path: Path) -> str:
    """The `\\\\localhost\\C$\\...` spelling of a local absolute path."""
    s = str(path)
    return "\\\\localhost\\" + s[0] + "$" + s[2:]


def _unc_admin_share_available() -> bool:
    if os.name != "nt":
        return False
    try:
        os.stat(_unc_alias_of(REPO_ROOT.resolve()))
        return True
    except OSError:
        return False


def test_forward_slash_extended_prefix_into_the_other_lane_is_denied():
    """`//?/C:/...` is the extended-length form spelled with slashes.

    Windows' path resolution accepts it and hands back `\\\\?\\C:\\...`, so
    matching only the literal backslash spelling left the identical evasion
    open one keystroke away.
    """
    inside = REPO_ROOT.resolve() / "plugins" / "codex" / "lws" / "bin" / "lws_hook.py"
    spelled = "//?/" + str(inside).replace("\\", "/")
    out = evaluate("claude", {"tool_name": "Write", "tool_input": {"file_path": spelled}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.skipif(not _unc_admin_share_available(),
                    reason="no reachable \\\\localhost\\C$ admin share on this host")
def test_unc_alias_of_the_repo_into_the_other_lane_is_denied():
    # `\\localhost\C$\...` addresses the identical file as `C:\...` but is
    # lexically unrelated to it, so relative_to() reports "not a subpath" and
    # the path can only be recognised by filesystem identity.
    inside = REPO_ROOT.resolve() / "plugins" / "codex" / "lws" / "bin" / "lws_hook.py"
    out = evaluate("claude", {"tool_name": "Write",
                              "tool_input": {"file_path": _unc_alias_of(inside)}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_identity_fallback_maps_an_alias_back_to_a_repo_relative_path(tmp_path):
    # The fallback has to rebuild the tail, not merely answer yes/no, and it
    # has to work for a file that does not exist yet -- a Write creating a new
    # file is the normal case.
    from lws_check_lane_write import _repo_relative_by_identity

    inside = REPO_ROOT.resolve() / "plugins" / "codex" / "not_created_yet.py"
    assert _repo_relative_by_identity(inside) == "plugins/codex/not_created_yet.py"
    assert _repo_relative_by_identity(tmp_path / "elsewhere.txt") is None


def test_write_inside_a_linked_worktree_is_classified_by_its_inner_path():
    """`.worktrees/<branch>/` is a checkout of this repo, not source in it.

    Directive 19 puts every worktree exactly there, and CLAUDE.md requires it.
    Classifying `.worktrees/x/tests/foo.py` by its literal path makes it
    "other", so the guard denies every write in a worktree -- including the
    ones needed to fix the guard. It must classify by the path *within* the
    worktree instead.
    """
    inner = REPO_ROOT.resolve() / ".worktrees" / "some-branch" / "tests" / "test_x.py"
    out = evaluate("claude", {"tool_name": "Write", "tool_input": {"file_path": str(inner)}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"

    other_lane = REPO_ROOT.resolve() / ".worktrees" / "some-branch" / "plugins" / "codex" / "x.py"
    out = evaluate("claude", {"tool_name": "Write", "tool_input": {"file_path": str(other_lane)}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_relative_dotdot_into_the_other_lane_is_denied():
    """`plugins/codex/../../plugins/claude/evil.py` really targets claude.

    classify_path does plain prefix matching, so an unresolved `..` lets a
    path advertise one lane and land in another. This needs no Windows trick
    at all, and a relative path is codex's only transport: apply_patch names
    files with repo-relative `*** Update File:` headers.
    """
    patch = "*** Update File: plugins/codex/../../plugins/claude/evil.py\n"
    out = evaluate("codex", {"tool_name": "apply_patch", "tool_input": {"input": patch}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    out = evaluate("claude", {"tool_name": "Write",
                              "tool_input": {"file_path": "plugins/claude/../codex/evil.py"}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_relative_dotdot_climbing_out_of_the_repo_fails_closed():
    # A relative path that escapes the repo cannot be shown to be outside it
    # -- it is resolved against whatever the process's working directory
    # happens to be -- so it denies rather than being waved through.
    out = evaluate("claude", {"tool_name": "Write",
                              "tool_input": {"file_path": "../../elsewhere/evil.py"}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_relative_dotdot_that_stays_in_lane_is_still_allowed():
    out = evaluate("claude", {"tool_name": "Write",
                              "tool_input": {"file_path": "tests/../plugins/claude/ok.py"}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_worktree_prefix_is_found_for_a_branch_name_containing_a_slash(tmp_path,
                                                                      monkeypatch):
    """Branch names have slashes, so a worktree is not always one level deep.

    `.worktrees/fix/lane-classify/...` is the shape this repo's own branch
    names produce. Stripping exactly two segments leaves `lane-classify/...`,
    which classifies "other" and denies everything in that worktree -- the
    very bug the worktree mapping exists to fix.
    """
    import lws_check_lane_write as mod

    fake_root = tmp_path / "repo"
    wt = fake_root / mod.WORKTREE_DIR / "fix" / "lane-classify"
    (wt / "plugins" / "codex").mkdir(parents=True)
    (wt / ".git").write_text("gitdir: ../../.git/worktrees/x\n", encoding="utf-8")

    monkeypatch.setattr(mod, "REPO_ROOT", fake_root)
    assert mod._strip_worktree_prefix(
        ".worktrees/fix/lane-classify/tests/test_x.py") == "tests/test_x.py"
    assert mod._strip_worktree_prefix(
        ".worktrees/fix/lane-classify/plugins/codex/x.py") == "plugins/codex/x.py"


def test_unresolvable_path_fails_closed():
    # None from _relativize means "known to be outside the repo". A path the
    # OS refuses to resolve is not known to be anything, so it must deny.
    nul = "\x00bad" + os.sep + "plugins" + os.sep + "codex" + os.sep + "x.py"
    out = evaluate("claude", {"tool_name": "Write", "tool_input": {"file_path": nul}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_non_edit_tool_is_ignored():
    out = evaluate("claude", {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": "plugins/codex/lws/bin/lws_hook.py"}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
