"""
app/security/abac_engine.py

Attribute-Based Access Control engine.

Evaluates rules like:
    department == "Sales" AND lead.owner == user.id

ADR-021: Pluggable Security — ABAC policies are composable and independently
replaceable. The engine is stateless and fully in-process.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class ABACOperator(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"


class ABACEffect(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass(frozen=True)
class ABACRule:
    """A single attribute rule: attribute <operator> value.

    attribute: dot-notation path into context_attrs, e.g. "user.department"
    operator:  ABACOperator
    value:     expected value (string, list, number)
    """
    attribute: str
    operator: ABACOperator
    value: Any


@dataclass
class ABACPolicy:
    """A list of rules combined with AND logic, plus an effect on match."""
    rules: List[ABACRule]
    effect: ABACEffect = ABACEffect.ALLOW
    name: str = ""

    def is_empty(self) -> bool:
        return len(self.rules) == 0


def _get_nested(attrs: Dict[str, Any], path: str) -> Any:
    """Resolve dot-notation path: 'lead.owner' -> attrs['lead']['owner']."""
    parts = path.split(".")
    val = attrs
    for part in parts:
        if isinstance(val, dict):
            val = val.get(part)
        else:
            return None
    return val


def _evaluate_rule(rule: ABACRule, context_attrs: Dict[str, Any]) -> bool:
    actual = _get_nested(context_attrs, rule.attribute)
    expected = rule.value

    match rule.operator:
        case ABACOperator.EQ:
            return actual == expected
        case ABACOperator.NEQ:
            return actual != expected
        case ABACOperator.IN:
            return actual in (expected if isinstance(expected, (list, tuple, set)) else [expected])
        case ABACOperator.NOT_IN:
            return actual not in (expected if isinstance(expected, (list, tuple, set)) else [expected])
        case ABACOperator.CONTAINS:
            return expected in actual if actual is not None else False
        case ABACOperator.GT:
            return actual > expected if actual is not None else False
        case ABACOperator.GTE:
            return actual >= expected if actual is not None else False
        case ABACOperator.LT:
            return actual < expected if actual is not None else False
        case ABACOperator.LTE:
            return actual <= expected if actual is not None else False
        case _:
            return False


class ABACEngine:
    """Stateless ABAC evaluation engine.

    All rules within a policy are combined with AND logic.
    An empty policy always returns its default effect (ALLOW by default).
    """

    @staticmethod
    def evaluate(policy: ABACPolicy, context_attrs: Dict[str, Any]) -> bool:
        """Evaluate a policy against a context attribute dict.

        Returns True if the policy's rules are satisfied (regardless of effect).
        The caller decides how to interpret ALLOW vs DENY effect.
        """
        if policy.is_empty():
            return policy.effect == ABACEffect.ALLOW

        return all(_evaluate_rule(rule, context_attrs) for rule in policy.rules)

    @staticmethod
    def evaluate_all(
        policies: List[ABACPolicy],
        context_attrs: Dict[str, Any],
    ) -> ABACEffect:
        """Evaluate multiple policies. DENY wins over ALLOW (fail-closed).

        Returns:
            DENY if any DENY-effect policy matches.
            ALLOW if any ALLOW-effect policy matches and no DENY matched.
            DENY if no policies match (fail-closed default).
        """
        allow_matched = False
        for policy in policies:
            matched = ABACEngine.evaluate(policy, context_attrs)
            if matched:
                if policy.effect == ABACEffect.DENY:
                    return ABACEffect.DENY
                else:
                    allow_matched = True
        return ABACEffect.ALLOW if allow_matched else ABACEffect.DENY
