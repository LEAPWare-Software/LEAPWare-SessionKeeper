"""Mutation-style test: proves the rule registry is load-bearing.

This does not edit rules/__init__.py on disk. Instead it monkeypatches
`lwr_core.engine.RULES` to an empty list — the same effect as removing
`budget_line` from the registry — and asserts the walking-skeleton deny
disappears. If someone ever made `evaluate()` deny unconditionally (e.g.
hardcoded, ignoring the registry), this test would still pass with the real
registry but FAIL here, since an empty registry would then still deny.
"""

import lwr_core.engine as engine_module
from lwr_core.config import Policy, RuleConfig, RuleMode
from lwr_core.events import Event


def _denying_dispatch_event() -> Event:
    return Event(
        hook_event="PreToolUse",
        tool_name="Agent",
        tool_input={"prompt": "Fix the bug"},
        prompt="Fix the bug",
    )


def test_real_registry_denies_the_walking_skeleton_case():
    policy = Policy(rules={"budget_line": RuleConfig(mode=RuleMode.DENY)})
    decision = engine_module.evaluate(_denying_dispatch_event(), policy)
    assert decision.permit is False


def test_removing_the_rule_from_the_registry_removes_the_deny(monkeypatch):
    monkeypatch.setattr(engine_module, "RULES", [])
    policy = Policy(rules={"budget_line": RuleConfig(mode=RuleMode.DENY)})
    decision = engine_module.evaluate(_denying_dispatch_event(), policy)
    assert decision.permit is True
    assert decision.findings == []
