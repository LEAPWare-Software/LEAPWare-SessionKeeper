"""Unit tests for the budget_line rule and its engine wiring."""

from lwr_core.config import RuleConfig, RuleMode
from lwr_core.engine import evaluate
from lwr_core.events import Event
from lwr_core.rules import budget_line


def _agent_event(prompt: str) -> Event:
    return Event(
        hook_event="PreToolUse",
        tool_name="Agent",
        tool_input={"prompt": prompt},
        prompt=prompt,
    )


def test_missing_budget_line_denies_under_deny_mode():
    event = _agent_event("Please go fix the bug in foo.py")
    config = RuleConfig(mode=RuleMode.DENY)
    finding = budget_line.evaluate(event, config)
    assert finding is not None
    assert finding.mode is RuleMode.DENY
    assert "BUDGET" in finding.reason


def test_present_budget_line_allows():
    event = _agent_event("BUDGET: 40k\nPlease go fix the bug in foo.py")
    config = RuleConfig(mode=RuleMode.DENY)
    finding = budget_line.evaluate(event, config)
    assert finding is None


def test_budget_line_must_be_at_start_of_a_line():
    event = _agent_event("not a BUDGET: 40k line since it's mid-sentence")
    config = RuleConfig(mode=RuleMode.DENY)
    finding = budget_line.evaluate(event, config)
    assert finding is not None


def test_rule_has_no_opinion_on_non_agent_tools():
    event = Event(hook_event="PreToolUse", tool_name="Read", tool_input={})
    config = RuleConfig(mode=RuleMode.DENY)
    assert budget_line.evaluate(event, config) is None


def test_rule_has_no_opinion_on_non_pretooluse_events():
    event = Event(hook_event="Stop", tool_name="Agent", tool_input={"prompt": "no budget"})
    config = RuleConfig(mode=RuleMode.DENY)
    assert budget_line.evaluate(event, config) is None


def test_engine_denies_walking_skeleton_dispatch():
    """The full walking-skeleton path: engine.evaluate denies a dispatch
    missing a BUDGET line when budget_line is configured to deny."""
    from lwr_core.config import Policy

    event = _agent_event("Fix the bug")
    policy = Policy(rules={"budget_line": RuleConfig(mode=RuleMode.DENY)})
    decision = evaluate(event, policy)
    assert decision.permit is False
    assert "BUDGET" in decision.deny_reason


def test_engine_allows_walking_skeleton_dispatch_with_budget_line():
    from lwr_core.config import Policy

    event = _agent_event("BUDGET: 20k\nFix the bug")
    policy = Policy(rules={"budget_line": RuleConfig(mode=RuleMode.DENY)})
    decision = evaluate(event, policy)
    assert decision.permit is True


def test_warn_mode_never_blocks():
    from lwr_core.config import Policy

    event = _agent_event("Fix the bug, no budget line")
    policy = Policy(rules={"budget_line": RuleConfig(mode=RuleMode.WARN)})
    decision = evaluate(event, policy)
    assert decision.permit is True
    assert decision.warnings, "expected a warning to be recorded"


def test_off_mode_produces_no_finding():
    from lwr_core.config import Policy

    event = _agent_event("Fix the bug, no budget line")
    policy = Policy(rules={"budget_line": RuleConfig(mode=RuleMode.OFF)})
    decision = evaluate(event, policy)
    assert decision.permit is True
    assert decision.findings == []
