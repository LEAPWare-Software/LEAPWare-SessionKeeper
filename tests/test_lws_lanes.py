"""Tests for scripts/lws_lanes.py: path classification, trailer parsing,
the bootstrap exception, and the review-record cross-check."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lws_lanes  # noqa: E402


def test_classify_claude_prefixes():
    assert lws_lanes.classify_path("plugins/claude/lws/bin/lws_hook.py") == "claude"
    assert lws_lanes.classify_path("adapters/claude/hook_io.py") == "claude"


def test_classify_codex_prefixes():
    assert lws_lanes.classify_path("plugins/codex/lws/bin/lws_hook.py") == "codex"
    assert lws_lanes.classify_path("adapters/codex/hook_io.py") == "codex"


def test_classify_shared_prefixes_and_files():
    for path in ("core/lws_core/engine.py", "scripts/lws_lanes.py", ".github/workflows/ci.yml",
                 "docs/architecture.md", "proof/schema.json", "reviews/README.md",
                 "HANDOFF.md", "AGENTS.md", "CLAUDE.md", "README.md"):
        assert lws_lanes.classify_path(path) == "shared", path


def test_classify_tests_subdirectory():
    assert lws_lanes.classify_path("tests/adapters/fixtures/claude/pretooluse_read.json") == "claude"
    assert lws_lanes.classify_path("tests/adapters/fixtures/codex/pretooluse_read.json") == "codex"


def test_classify_named_test_module_extension():
    assert lws_lanes.classify_path("tests/adapters/test_claude_hook_io.py") == "claude"
    assert lws_lanes.classify_path("tests/adapters/test_codex_hook_io.py") == "codex"


def test_classify_repo_root_files_are_shared():
    # No file at the repo root belongs to one CLI's lane: build config, ignore
    # rules, the changelog and the licence are repo-wide by construction.
    # CLAUDE.md and AGENTS.md already call "root config" shared; before this,
    # classify_path did not, so no agent could touch .gitignore at all.
    for path in (".gitignore", "pyproject.toml", "CHANGELOG.md", "LICENSE",
                 ".editorconfig", "SECURITY.md"):
        assert lws_lanes.classify_path(path) == "shared", path


def test_classify_generic_test_modules_are_shared():
    # A test naming neither CLI exercises shared code, so it is shared -- not
    # "other", which no agent may touch at all. Changing a shared script and
    # its own test in one commit has to be possible.
    for path in ("tests/test_lws_check_env_leak.py", "tests/core/test_lws_handoff.py",
                 "tests/conftest.py", "tests/conformance/test_policy_shape.py"):
        assert lws_lanes.classify_path(path) == "shared", path


def test_classify_lane_tests_win_over_shared_tests():
    # Precedence guard: the lane rules for tests/ are evaluated before the
    # shared-tests fallback. Reverse them and every lane fixture silently
    # becomes shared, firing the cross-CLI review gate on lane-only work.
    assert lws_lanes.classify_path("tests/adapters/fixtures/claude/pretooluse_read.json") == "claude"
    assert lws_lanes.classify_path("tests/adapters/test_codex_hook_io.py") == "codex"


def test_classify_cli_config_dirs_are_shared_not_owned():
    # `.claude/` and `.codex/` hold each CLI's own enforcement wiring -- the
    # PreToolUse hook that applies the lane rules to that CLI. Giving a CLI its
    # own lane over that directory would let it switch off its own guard with
    # no cross-CLI review, so both are shared. Before this they classified
    # "other", which no agent could touch at all.
    assert lws_lanes.classify_path(".claude/settings.json") == "shared"
    assert lws_lanes.classify_path(".codex/hooks.json") == "shared"


def test_classify_dot_segments_are_not_root_files():
    # "." and ".." have no "/" in them, so the repo-root rule called them
    # shared -- which reads as "any agent may write here". Neither names a
    # file at all, so neither is a root file.
    for path in (".", "..", ""):
        assert lws_lanes.classify_path(path) == "other", path


def test_classify_other_for_unrelated_path():
    assert lws_lanes.classify_path("examples/policies/example-routing.json") == "other"


def test_bootstrap_exception_skips_pr_4():
    # rev_range irrelevant since pr_number gate short-circuits before any git call
    assert lws_lanes.check_lanes("HEAD~1..HEAD", 4) == []
    assert lws_lanes.check_lanes("HEAD~1..HEAD", 1) == []


def test_commit_agent_parses_trailer(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "f.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "msg\n\nLWS-Agent: claude"],
        cwd=repo,
        check=True,
    )
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    original_root = lws_lanes.REPO_ROOT
    try:
        lws_lanes.REPO_ROOT = repo
        assert lws_lanes.commit_agent(sha) == "claude"
        assert lws_lanes.commit_files(sha) == ["f.txt"]
    finally:
        lws_lanes.REPO_ROOT = original_root
