import uuid
from datetime import datetime
from typing import Any, Protocol

from app.models.enums import ConditionOperator, ConditionValueType
from app.models.workflow import WorkflowCondition


# ── Operator Classes Registry ────────────────────────────────────────────────

class Operator(Protocol):
    def compare(self, actual: Any, expected: Any) -> bool:
        ...


class EqualOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        return actual == expected


class NotEqualOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        return actual != expected


class GreaterThanOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        try:
            return float(actual) > float(expected)
        except (ValueError, TypeError):
            return False


class GreaterThanOrEqualOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        try:
            return float(actual) >= float(expected)
        except (ValueError, TypeError):
            return False


class LessThanOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        try:
            return float(actual) < float(expected)
        except (ValueError, TypeError):
            return False


class LessThanOrEqualOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        try:
            return float(actual) <= float(expected)
        except (ValueError, TypeError):
            return False


class ContainsOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        if actual is None or expected is None:
            return False
        return str(expected).lower() in str(actual).lower()


class StartsWithOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        if actual is None or expected is None:
            return False
        return str(actual).lower().startswith(str(expected).lower())


class EndsWithOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        if actual is None or expected is None:
            return False
        return str(actual).lower().endswith(str(expected).lower())


class InOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        if actual is None or expected is None:
            return False
        elements = [item.strip().lower() for item in str(expected).split(",") if item.strip()]
        return str(actual).lower() in elements


class NotInOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        if actual is None or expected is None:
            return True
        elements = [item.strip().lower() for item in str(expected).split(",") if item.strip()]
        return str(actual).lower() not in elements


class IsNullOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        return actual is None


class IsNotNullOperator:
    def compare(self, actual: Any, expected: Any) -> bool:
        return actual is not None


# Operator Registry Map
OPERATORS: dict[ConditionOperator, Operator] = {
    ConditionOperator.EQ: EqualOperator(),
    ConditionOperator.NE: NotEqualOperator(),
    ConditionOperator.GT: GreaterThanOperator(),
    ConditionOperator.GTE: GreaterThanOrEqualOperator(),
    ConditionOperator.LT: LessThanOperator(),
    ConditionOperator.LTE: LessThanOrEqualOperator(),
    ConditionOperator.CONTAINS: ContainsOperator(),
    ConditionOperator.STARTS_WITH: StartsWithOperator(),
    ConditionOperator.ENDS_WITH: EndsWithOperator(),
    ConditionOperator.IN: InOperator(),
    ConditionOperator.NOT_IN: NotInOperator(),
    ConditionOperator.IS_NULL: IsNullOperator(),
    ConditionOperator.IS_NOT_NULL: IsNotNullOperator(),
}

# ── Condition Engine ──────────────────────────────────────────────────────────

class WorkflowConditionEngine:
    """Pure business logic engine for checking workflow rule conditions."""

    @staticmethod
    def evaluate(conditions: list[WorkflowCondition], payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        """Evaluates a list of conditions against a flat payload dict.
        All condition filters in this MVP combine with AND logic.
        Returns a tuple: (passed: bool, trace: dict)
        """
        import time
        if not conditions:
            return True, {"passed": True, "conditions": []}

        # Enforce deterministic order by group_id and order
        sorted_conditions = sorted(
            conditions, key=lambda c: (c.group_id or "", c.order)
        )

        trace_conditions = []
        overall_passed = True

        for cond in sorted_conditions:
            cond_start_ns = time.perf_counter_ns()
            actual_raw = payload.get(cond.field)
            if hasattr(actual_raw, "value"):
                actual_raw = actual_raw.value  # Unpack SQLAlchemy custom Enum wrapper values

            # Cast both fields to correct condition value type
            actual_cast = cast_value(actual_raw, cond.value_type)
            expected_cast = cast_value(cond.value, cond.value_type)

            op_handler = OPERATORS.get(cond.operator)
            if op_handler is None:
                matched = False
            else:
                matched = op_handler.compare(actual_cast, expected_cast)

            cond_end_ns = time.perf_counter_ns()
            evaluation_ms = (cond_end_ns - cond_start_ns) / 1_000_000.0

            trace_conditions.append({
                "field": cond.field,
                "operator": cond.operator.value,
                "expected": cond.value,
                "actual": str(actual_raw) if actual_raw is not None else None,
                "result": matched,
                "evaluation_ms": evaluation_ms,
            })

            if not matched:
                overall_passed = False
                break

        return overall_passed, {
            "passed": overall_passed,
            "conditions": trace_conditions,
        }


def cast_value(val: Any, value_type: ConditionValueType) -> Any:
    """Helper to convert values into comparative data types."""
    if val is None:
        return None
    if value_type == ConditionValueType.NUMBER:
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0
    if value_type == ConditionValueType.BOOLEAN:
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes")
    if value_type == ConditionValueType.DATETIME:
        if isinstance(val, datetime):
            return val
        try:
            # Replaces Z suffix with offset timezone mapping
            return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        except Exception:
            return None
    return str(val)
