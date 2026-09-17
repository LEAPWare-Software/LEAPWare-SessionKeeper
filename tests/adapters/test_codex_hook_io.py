"""Tests for adapters/codex/hook_io.py against fixtures."""

import json
from pathlib import Path

from adapters.codex.hook_io import parse_event, render_decision, render_report
from lwr_core.config import Policy, RuleConfig, RuleMode
from lwr_core.engine import evaluate

FIXTURES = Path(__file__).parent / "fixtures" / "codex"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_event_extracts_prompt():
    event = parse_event(_load("pretooluse_agent_no_budget.json"))
    assert event.tool_name == "Agent"
    assert event.prompt and "example_module" in event.prompt


def test_parse_event_non_agent_tool_has_no_prompt():
    event = parse_event(_load("pretooluse_read.json"))
    assert event.tool_name == "Read"
    assert event.prompt is None


def test_render_report_states_would_deny():
    policy = Policy(rules={"budget_line": RuleConfig(mode=RuleMode.DENY)})
    event = parse_event(_load("pretooluse_agent_no_budget.json"))
    decision = evaluate(event, policy)
    report = render_report(decision)
    assert "would DENY" in report
    assert "BUDGET" in report


def test_render_report_states_would_allow_with_budget_line():
    policy = Policy(rules={"budget_line": RuleConfig(mode=RuleMode.DENY)})
    event = parse_event(_load("pretooluse_agent_with_budget.json"))
    decision = evaluate(event, policy)
    report = render_report(decision)
    assert "would ALLOW" in report


def test_render_decision_deny_shape():
    policy = Policy(rules={"budget_line": RuleConfig(mode=RuleMode.DENY)})
    event = parse_event(_load("pretooluse_agent_no_budget.json"))
    decision = evaluate(event, policy)
    output = render_decision(decision)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "BUDGET" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_render_decision_allow_shape_with_budget_line():
    policy = Policy(rules={"budget_line": RuleConfig(mode=RuleMode.DENY)})
    event = parse_event(_load("pretooluse_agent_with_budget.json"))
    decision = evaluate(event, policy)
    output = render_decision(decision)
    assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "permissionDecisionReason" not in output["hookSpecificOutput"]


def test_render_decision_allow_with_warning_reason():
    policy = Policy(rules={"budget_line": RuleConfig(mode=RuleMode.WARN)})
    event = parse_event(_load("pretooluse_agent_no_budget.json"))
    decision = evaluate(event, policy)
    output = render_decision(decision)
    assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "BUDGET" in output["hookSpecificOutput"]["permissionDecisionReason"]
