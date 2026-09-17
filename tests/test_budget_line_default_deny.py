"""Owner directive 2: enforcement is mechanical (deny), not advisory (warn).

`core/policy/default.json` is the policy every real install ships with
unless a project or user overrides it. This test proves that shipped
default actually denies a no-BUDGET dispatch, by running both real hook
entry points (`plugins/claude/lwr/bin/lwr_hook.py`,
`plugins/codex/lwr/bin/lwr_hook.py`) as subprocesses with NO
`LWR_POLICY_PATH` override -- so each hook falls back to its own vendored
`vendor/policy/default.json`, exactly as a real install would -- against a
no-BUDGET fixture, and asserts both deny.

Mutation: set `core/policy/default.json`'s `budget_line.mode` back to
`"warn"` and re-run `python scripts/lwr_build.py` to sync the vendor
trees -- `test_both_hooks_deny_under_the_shipped_default_policy` FAILS
(the decision becomes "allow", not "deny").
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (plugin dir under plugins/, no-BUDGET fixture for that host's event shape)
HOOK_TARGETS = [
    (
        REPO_ROOT / "plugins" / "claude" / "lwr",
        REPO_ROOT / "tests" / "adapters" / "fixtures" / "claude" / "pretooluse_agent_no_budget.json",
    ),
    (
        REPO_ROOT / "plugins" / "codex" / "lwr",
        REPO_ROOT / "tests" / "adapters" / "fixtures" / "codex" / "pretooluse_agent_no_budget.json",
    ),
]


def test_both_hooks_deny_under_the_shipped_default_policy(tmp_path):
    for plugin_dir, fixture in HOOK_TARGETS:
        hook_script = plugin_dir / "bin" / "lwr_hook.py"
        ledger_path = tmp_path / f"{plugin_dir.parent.name}-ledger.jsonl"

        env = {
            # Deliberately NO LWR_POLICY_PATH: the hook must fall back to
            # its own vendored policy/default.json, the file a real
            # install ships and never overrides.
            "LWR_LEDGER_PATH": str(ledger_path),
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        }

        result = subprocess.run(
            [sys.executable, str(hook_script)],
            cwd=str(tmp_path),
            input=fixture.read_text(encoding="utf-8"),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny", (
            f"{plugin_dir}: shipped default policy did not deny a no-BUDGET "
            f"dispatch: {payload}"
        )
        assert "BUDGET" in payload["hookSpecificOutput"]["permissionDecisionReason"]
