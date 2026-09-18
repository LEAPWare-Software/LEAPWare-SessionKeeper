"""Unit tests for scripts/lws_handoff.py. No network; git/gh calls are
monkeypatched out where a test needs cmd_check/cmd_write end to end."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "lws_handoff.py"

_spec = importlib.util.spec_from_file_location("lws_handoff", SCRIPT_PATH)
lws_handoff = importlib.util.module_from_spec(_spec)
sys.modules["lws_handoff"] = lws_handoff
_spec.loader.exec_module(lws_handoff)


def _valid_text(begin: str = lws_handoff.BEGIN_MARKER, end: str = lws_handoff.END_MARKER) -> str:
    return (
        "# HANDOFF\n\n"
        "## Start of session\n- [ ] read this\n\n"
        "## In flight\n1. do the thing\n\n"
        f"{begin}\nGenerated: 2026-09-17 00:00 UTC\nmain SHA: deadbeef\n\nOpen PRs:\n(none)\n\n{end}\n\n"
        "## Re-derive state\n```\ngit status\n```\n\n"
        "## Hard rules\n- stdlib only\n\n"
        "## Traps\n- none yet\n"
    )


def test_valid_text_passes():
    assert lws_handoff._validate(_valid_text()) == []


def test_missing_section_fails():
    text = _valid_text().replace("## Traps\n", "")
    errors = lws_handoff._validate(text)
    assert any("Traps" in e for e in errors)


def test_missing_begin_marker_fails():
    text = _valid_text().replace(lws_handoff.BEGIN_MARKER, "")
    errors = lws_handoff._validate(text)
    assert any("begin" in e.lower() for e in errors)


def test_duplicate_marker_fails():
    text = _valid_text() + f"\n{lws_handoff.BEGIN_MARKER}\n{lws_handoff.END_MARKER}\n"
    errors = lws_handoff._validate(text)
    assert any("exactly one" in e for e in errors)


def test_markers_out_of_order_fails():
    text = _valid_text(begin=lws_handoff.END_MARKER, end=lws_handoff.BEGIN_MARKER)
    errors = lws_handoff._validate(text)
    assert any("before begin" in e for e in errors)


def test_over_size_cap_fails():
    text = _valid_text() + ("x" * (lws_handoff.SIZE_CAP_BYTES + 1))
    errors = lws_handoff._validate(text)
    assert any("bytes" in e and "cap" in e for e in errors)


@pytest.mark.parametrize(
    "needle",
    ["C:\\Users\\someone\\repo", "/Users/someone/repo", "/home/someone/repo"],
)
def test_absolute_path_fails(needle):
    text = _valid_text() + f"\n{needle}\n"
    errors = lws_handoff._validate(text)
    assert any("absolute path" in e for e in errors)


@pytest.mark.parametrize("needle", ["example-private-project", "Example-Private-Project"])
def test_forbidden_substring_fails(needle):
    text = _valid_text() + f"\n{needle}\n"
    errors = lws_handoff._validate(text)
    assert any("forbidden substring" in e for e in errors)


def test_forbidden_substrings_default_only_when_file_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(lws_handoff, "REPO_ROOT", tmp_path)
    assert lws_handoff._forbidden_substrings() == lws_handoff.DEFAULT_FORBIDDEN_SUBSTRINGS


def test_forbidden_substring_from_local_file_fails(tmp_path, monkeypatch):
    (tmp_path / lws_handoff.PRIVATE_NAMES_FILE).write_text("AdoptersSecretProject\n", encoding="utf-8")
    monkeypatch.setattr(lws_handoff, "REPO_ROOT", tmp_path)
    text = _valid_text() + "\nAdoptersSecretProject\n"
    errors = lws_handoff._validate(text)
    assert any("forbidden substring" in e and "adopterssecretproject" in e for e in errors)


def test_cmd_check_missing_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(lws_handoff, "HANDOFF_PATH", tmp_path / "HANDOFF.md")
    assert lws_handoff.cmd_check() == 1
    assert "does not exist" in capsys.readouterr().err


def test_cmd_check_valid_file(tmp_path, monkeypatch, capsys):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text(), encoding="utf-8")
    monkeypatch.setattr(lws_handoff, "HANDOFF_PATH", path)
    assert lws_handoff.cmd_check() == 0
    assert "OK" in capsys.readouterr().out


def test_cmd_check_invalid_file(tmp_path, monkeypatch, capsys):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text().replace("## Traps\n", ""), encoding="utf-8")
    monkeypatch.setattr(lws_handoff, "HANDOFF_PATH", path)
    assert lws_handoff.cmd_check() == 1
    assert "FAIL" in capsys.readouterr().err


def test_cmd_write_regenerates_only_the_block(tmp_path, monkeypatch):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text(), encoding="utf-8")
    monkeypatch.setattr(lws_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lws_handoff, "_run_git", lambda args: "cafef00d")
    monkeypatch.setattr(lws_handoff, "_run_gh_with_status", lambda args: (True, ""))

    before = path.read_text(encoding="utf-8")
    prose_before = before.split(lws_handoff.BEGIN_MARKER)[0]

    assert lws_handoff.cmd_write() == 0

    after = path.read_text(encoding="utf-8")
    prose_after = after.split(lws_handoff.BEGIN_MARKER)[0]
    assert prose_before == prose_after
    assert "cafef00d" in after
    assert after.count(lws_handoff.BEGIN_MARKER) == 1
    assert after.count(lws_handoff.END_MARKER) == 1


def test_cmd_write_requires_existing_markers(tmp_path, monkeypatch, capsys):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text().replace(lws_handoff.BEGIN_MARKER, ""), encoding="utf-8")
    monkeypatch.setattr(lws_handoff, "HANDOFF_PATH", path)
    assert lws_handoff.cmd_write() == 1
    assert "must already contain" in capsys.readouterr().err


def test_cmd_write_records_cli_and_session(tmp_path, monkeypatch):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text(), encoding="utf-8")
    monkeypatch.setattr(lws_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lws_handoff, "PROOF_DIR", tmp_path / "no-such-proof-dir")
    monkeypatch.setattr(lws_handoff, "_run_git", lambda args: "cafef00d")
    monkeypatch.setattr(lws_handoff, "_run_gh_with_status", lambda args: (True, ""))

    assert lws_handoff.cmd_write(cli="claude", session="sess-123") == 0

    after = path.read_text(encoding="utf-8")
    assert "CLI: claude" in after
    assert "Session: sess-123" in after


def test_cmd_write_defaults_cli_and_session_to_unknown(tmp_path, monkeypatch):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text(), encoding="utf-8")
    monkeypatch.setattr(lws_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lws_handoff, "PROOF_DIR", tmp_path / "no-such-proof-dir")
    monkeypatch.setattr(lws_handoff, "_run_git", lambda args: "cafef00d")
    monkeypatch.setattr(lws_handoff, "_run_gh_with_status", lambda args: (True, ""))

    assert lws_handoff.cmd_write() == 0

    after = path.read_text(encoding="utf-8")
    assert "CLI: unknown" in after
    assert "Session: unknown" in after


def test_cmd_write_lists_deliverable_proof_state(tmp_path, monkeypatch):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text(), encoding="utf-8")
    proof_dir = tmp_path / "proof"
    proof_dir.mkdir()
    (proof_dir / "example.json").write_text(
        '{"deliverable": "example", "author": "a", "checked_by": "b", '
        '"commit": "abc1234", "commands": [], "mutations": [], "unproven": []}',
        encoding="utf-8",
    )
    monkeypatch.setattr(lws_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lws_handoff, "PROOF_DIR", proof_dir)
    monkeypatch.setattr(lws_handoff, "_run_git", lambda args: "cafef00d")
    monkeypatch.setattr(lws_handoff, "_run_gh_with_status", lambda args: (True, ""))

    assert lws_handoff.cmd_write() == 0

    after = path.read_text(encoding="utf-8")
    assert "example: PROVEN (commit abc1234)" in after


def test_cmd_write_reports_no_proof_records_yet(tmp_path, monkeypatch):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text(), encoding="utf-8")
    proof_dir = tmp_path / "empty-proof"
    proof_dir.mkdir()
    monkeypatch.setattr(lws_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lws_handoff, "PROOF_DIR", proof_dir)
    monkeypatch.setattr(lws_handoff, "_run_git", lambda args: "cafef00d")
    monkeypatch.setattr(lws_handoff, "_run_gh_with_status", lambda args: (True, ""))

    assert lws_handoff.cmd_write() == 0

    after = path.read_text(encoding="utf-8")
    assert "(none yet)" in after


def test_real_handoff_md_passes_check():
    """The repo's own HANDOFF.md must pass --check (guards drift)."""
    monkeypatch_path = REPO_ROOT / "HANDOFF.md"
    text = monkeypatch_path.read_text(encoding="utf-8")
    assert lws_handoff._validate(text) == []


# --- --check-live: re-derives the generated block's facts against git/gh ---


def _live_text(main_sha: str, open_prs: str) -> str:
    return (
        "# HANDOFF\n\n"
        "## Start of session\n- [ ] read this\n\n"
        "## In flight\n1. do the thing\n\n"
        f"{lws_handoff.BEGIN_MARKER}\nGenerated: 2026-09-17 00:00 UTC\n"
        f"main SHA: {main_sha}\n\nOpen PRs:\n{open_prs}\n\n{lws_handoff.END_MARKER}\n\n"
        "## Re-derive state\n```\ngit status\n```\n\n"
        "## Hard rules\n- stdlib only\n\n"
        "## Traps\n- none yet\n"
    )


def test_extract_main_sha():
    text = _live_text("deadbeef", "(none open)")
    assert lws_handoff._extract_main_sha(text) == "deadbeef"


def test_extract_pr_numbers():
    section = "#11 some title (branch)\n#12 another (branch2)"
    assert lws_handoff._extract_pr_numbers(section) == {11, 12}


def test_check_sha_live_tip_passes(monkeypatch):
    monkeypatch.setattr(lws_handoff, "_run_git_strict", lambda args: "tip-sha")
    assert lws_handoff._check_sha_live("tip-sha") == []


def test_check_sha_live_one_commit_behind_passes(monkeypatch):
    monkeypatch.setattr(lws_handoff, "_run_git_strict", lambda args: "tip-sha")
    monkeypatch.setattr(lws_handoff, "_git_is_ancestor", lambda candidate, ref: True)
    monkeypatch.setattr(lws_handoff, "_git_distance", lambda candidate, ref: 1)
    errors = lws_handoff._check_sha_live("parent-sha")
    assert errors == []


def test_check_sha_live_six_behind_fails(monkeypatch):
    monkeypatch.setattr(lws_handoff, "_run_git_strict", lambda args: "tip-sha")
    monkeypatch.setattr(lws_handoff, "_git_is_ancestor", lambda candidate, ref: True)
    monkeypatch.setattr(lws_handoff, "_git_distance", lambda candidate, ref: 6)
    errors = lws_handoff._check_sha_live("stale-sha")
    assert any("stale" in e or "behind" in e for e in errors)


def test_check_sha_live_not_an_ancestor_fails(monkeypatch):
    monkeypatch.setattr(lws_handoff, "_run_git_strict", lambda args: "tip-sha")
    monkeypatch.setattr(lws_handoff, "_git_is_ancestor", lambda candidate, ref: False)
    errors = lws_handoff._check_sha_live("unrelated-sha")
    assert any("ancestor" in e for e in errors)


def test_check_prs_live_missing_open_pr_fails(monkeypatch):
    monkeypatch.setattr(lws_handoff, "_run_gh_strict", lambda args: '[{"number": 11}, {"number": 12}]')
    errors = lws_handoff._check_prs_live("#11 title (branch)")
    assert any("missing" in e and "12" in e for e in errors)


def test_check_prs_live_extra_closed_pr_fails(monkeypatch):
    monkeypatch.setattr(lws_handoff, "_run_gh_strict", lambda args: '[{"number": 11}]')
    errors = lws_handoff._check_prs_live("#11 title (branch)\n#99 stale (branch2)")
    assert any("extra" in e and "99" in e for e in errors)


def test_check_prs_live_excludes_own_pr_number(monkeypatch):
    """A block committed before its own PR exists cannot have listed it --
    exclude_pr / --pr-number excuses exactly that number, not any other."""
    monkeypatch.setattr(lws_handoff, "_run_gh_strict", lambda args: '[{"number": 15}]')
    errors = lws_handoff._check_prs_live(lws_handoff.NONE_OPEN_MARKER, exclude_pr=15)
    assert errors == []


def test_check_prs_live_excludes_own_pr_number_even_if_committed_names_it(monkeypatch):
    """A later --write run in the same PR sees gh already reporting the PR
    as open and may commit its own number -- that must not be flagged as
    "extra" either."""
    monkeypatch.setattr(lws_handoff, "_run_gh_strict", lambda args: '[{"number": 15}]')
    errors = lws_handoff._check_prs_live("#15 title (branch)", exclude_pr=15)
    assert errors == []


def test_check_prs_live_excluding_own_pr_still_catches_other_missing(monkeypatch):
    monkeypatch.setattr(lws_handoff, "_run_gh_strict", lambda args: '[{"number": 15}, {"number": 20}]')
    errors = lws_handoff._check_prs_live(lws_handoff.NONE_OPEN_MARKER, exclude_pr=15)
    assert any("missing" in e and "20" in e for e in errors)


def test_check_prs_live_none_open_matches_passes(monkeypatch):
    monkeypatch.setattr(lws_handoff, "_run_gh_strict", lambda args: "[]")
    errors = lws_handoff._check_prs_live(lws_handoff.NONE_OPEN_MARKER)
    assert errors == []


def test_check_prs_live_unknown_marker_always_fails(monkeypatch):
    monkeypatch.setattr(
        lws_handoff, "_run_gh_strict", lambda args: (_ for _ in ()).throw(AssertionError("gh must not be called"))
    )
    errors = lws_handoff._check_prs_live(lws_handoff.UNKNOWN_PR_MARKER)
    assert any("UNKNOWN" in e or "not trustworthy" in e for e in errors)


def test_run_git_strict_raises_when_git_missing(monkeypatch):
    def _boom(*args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(lws_handoff.subprocess, "run", _boom)
    with pytest.raises(lws_handoff.LiveCheckError):
        lws_handoff._run_git_strict(["rev-parse", "origin/main"])


def test_run_gh_strict_raises_on_nonzero_exit(monkeypatch):
    class _Result:
        returncode = 1
        stdout = ""
        stderr = "not authenticated"

    monkeypatch.setattr(lws_handoff.subprocess, "run", lambda *a, **k: _Result())
    with pytest.raises(lws_handoff.LiveCheckError):
        lws_handoff._run_gh_strict(["pr", "list"])


def test_cmd_check_live_passes_end_to_end(tmp_path, monkeypatch, capsys):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_live_text("tip-sha", "(none open)"), encoding="utf-8")
    protocol_path = tmp_path / "handoff-protocol.md"
    protocol_path.write_text("short", encoding="utf-8")
    monkeypatch.setattr(lws_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lws_handoff, "HANDOFF_PROTOCOL_PATH", protocol_path)
    monkeypatch.setattr(lws_handoff, "_run_git_strict", lambda args: "tip-sha")
    monkeypatch.setattr(lws_handoff, "_run_gh_strict", lambda args: "[]")

    assert lws_handoff.cmd_check_live() == 0
    assert "OK" in capsys.readouterr().out


def test_cmd_check_live_fails_on_sha_mismatch(tmp_path, monkeypatch, capsys):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_live_text("very-stale-sha", "(none open)"), encoding="utf-8")
    protocol_path = tmp_path / "handoff-protocol.md"
    protocol_path.write_text("short", encoding="utf-8")
    monkeypatch.setattr(lws_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lws_handoff, "HANDOFF_PROTOCOL_PATH", protocol_path)
    monkeypatch.setattr(lws_handoff, "_run_git_strict", lambda args: "tip-sha")
    monkeypatch.setattr(lws_handoff, "_git_is_ancestor", lambda candidate, ref: False)
    monkeypatch.setattr(lws_handoff, "_run_gh_strict", lambda args: "[]")

    assert lws_handoff.cmd_check_live() == 1
    err = capsys.readouterr().err
    assert "very-stale-sha" in err and "tip-sha" in err


def test_cmd_check_live_fails_loudly_when_gh_unavailable(tmp_path, monkeypatch, capsys):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_live_text("tip-sha", "(none open)"), encoding="utf-8")
    protocol_path = tmp_path / "handoff-protocol.md"
    protocol_path.write_text("short", encoding="utf-8")
    monkeypatch.setattr(lws_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lws_handoff, "HANDOFF_PROTOCOL_PATH", protocol_path)
    monkeypatch.setattr(lws_handoff, "_run_git_strict", lambda args: "tip-sha")

    def _boom(args):
        raise lws_handoff.LiveCheckError("gh not authenticated")

    monkeypatch.setattr(lws_handoff, "_run_gh_strict", _boom)

    assert lws_handoff.cmd_check_live() == 1
    assert "could not get authoritative state" in capsys.readouterr().err


# --- Fix 4: docs/handoff-protocol.md size cap ---


def test_handoff_protocol_over_cap_fails(tmp_path, monkeypatch, capsys):
    path = tmp_path / "HANDOFF.md"
    path.write_text(_valid_text(), encoding="utf-8")
    protocol_path = tmp_path / "handoff-protocol.md"
    protocol_path.write_text("x" * (lws_handoff.HANDOFF_PROTOCOL_CAP_BYTES + 1), encoding="utf-8")
    monkeypatch.setattr(lws_handoff, "HANDOFF_PATH", path)
    monkeypatch.setattr(lws_handoff, "HANDOFF_PROTOCOL_PATH", protocol_path)

    assert lws_handoff.cmd_check() == 1
    assert "handoff-protocol.md" in capsys.readouterr().err


def test_real_handoff_protocol_under_cap():
    text = (REPO_ROOT / "docs" / "handoff-protocol.md").read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) <= lws_handoff.HANDOFF_PROTOCOL_CAP_BYTES
