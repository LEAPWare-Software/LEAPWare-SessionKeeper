"""lwr_version: the walking-skeleton rule -- a safe no-op.

Fires on every event, unconditionally, and reports this build's
`lwr_core.__version__` as a WARN-shaped finding. It never denies: even if
a policy file configures it to `"deny"`, this rule reports at WARN anyway
-- the no-op guarantee is enforced here, in the rule itself, not merely by
the shipped default. That is deliberate: LWR sits next to LWH (which
already enforces its own token-policy rules) and must not double-enforce
anything of its own before its real runway rules (wind-down/landing/
handoff-only/retire) are designed and built. See
docs/rules/lwr-version.md for the policy-author-facing description.
"""

from __future__ import annotations

from ..config import RuleConfig, RuleMode
from ..events import Event

rule_id = "lwr_version"

# Not `from .. import __version__`: lwr_core/__init__.py imports engine,
# which imports rules, which imports this module -- importing the package
# itself here would be a circular import. lwr_core/__init__.py re-exports
# the canonical `__version__`; that module is this string's one source of
# truth, kept in sync by tests/core/test_lwr_version.py.
_VERSION = "0.1.0"


def evaluate(event: Event, config: RuleConfig):
    """Always return a WARN Finding reporting the plugin version. Never denies.

    `config.mode` is already guaranteed non-OFF by the engine (it skips OFF
    rules before calling this). Unlike a normal rule, this one ignores
    `config.mode` for the purpose of severity -- it always reports at WARN,
    regardless of how a policy file configures it, so installing this
    walking skeleton can never itself block a dispatch.
    """
    from ..engine import Finding  # local import: engine imports this module.

    return Finding(
        rule_id=rule_id,
        mode=RuleMode.WARN,
        reason=f"lwr {_VERSION}: reporting only, no policy enforced yet",
    )
