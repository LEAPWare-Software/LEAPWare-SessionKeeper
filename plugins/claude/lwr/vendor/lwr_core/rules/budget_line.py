"""budget_line: the walking-skeleton rule.

Requires a dispatch prompt to carry a line matching `^BUDGET:\\s*\\d+k` (start
of line, case-sensitive "BUDGET:", one or more digits, literal "k"). This is
the rule end-to-end tests are built around; see docs/rules/budget-line.md
for the policy-author-facing description.

Scope: this rule only has an opinion on a "PreToolUse" event whose
`tool_name` is "Agent" (a subagent dispatch). Every other event: no opinion
(returns None), regardless of configured mode — a rule that can't recognize
its own trigger condition must stay silent, not deny.
"""

from __future__ import annotations

import re
from typing import Optional

from ..config import RuleConfig, RuleMode
from ..events import Event

rule_id = "budget_line"

_BUDGET_LINE = re.compile(r"^BUDGET:\s*\d+k\s*$", re.MULTILINE)


def evaluate(event: Event, config: RuleConfig):
    """Return a Finding at `config.mode` if `event`'s prompt lacks a BUDGET line.

    `config.mode` is already guaranteed non-OFF by the engine (it skips OFF
    rules before calling this). Returning None here means "not applicable",
    distinct from the engine's own OFF short-circuit.
    """
    from ..engine import Finding  # local import: engine imports this module.

    if event.hook_event != "PreToolUse" or event.tool_name != "Agent":
        return None

    prompt = event.prompt
    if prompt is None:
        prompt = event.tool_input.get("prompt") if isinstance(event.tool_input, dict) else None
    if prompt is None:
        prompt = ""

    if _BUDGET_LINE.search(prompt):
        return None

    return Finding(
        rule_id=rule_id,
        mode=config.mode,
        reason=(
            "dispatch prompt has no line matching '^BUDGET:\\s*\\d+k' "
            "(e.g. 'BUDGET: 40k') — every subagent dispatch must state a token budget"
        ),
    )
