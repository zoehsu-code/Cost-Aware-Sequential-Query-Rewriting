from __future__ import annotations

from decimal import Decimal

from src.stage2.evaluator import BenchmarkEvaluator


def test_are_equivalent_ignores_row_order_and_preserves_duplicates() -> None:
    cols_a = ["c1", "c2"]
    rows_a = [(1, "x"), (1, "x"), (2, "y")]
    cols_b = ["d1", "d2"]
    rows_b = [(2, "y"), (1, "x"), (1, "x")]

    assert BenchmarkEvaluator.are_equivalent(cols_a, rows_a, cols_b, rows_b) is True


def test_are_equivalent_applies_normalize_value_rules() -> None:
    cols = ["a", "b", "c", "d", "e"]
    rows_a = [(None, True, Decimal("1.234567891"), b" abc ", " text ")]
    rows_b = [(None, True, 1.2345678912, "abc", "text")]

    assert BenchmarkEvaluator.are_equivalent(cols, rows_a, cols, rows_b) is True


def test_are_equivalent_sql_returns_false_on_execution_error() -> None:
    class _StubEvaluator(BenchmarkEvaluator):
        def __init__(self) -> None:
            pass

        def execute_query(self, sql: str):  # type: ignore[override]
            raise RuntimeError("boom")

    evaluator = _StubEvaluator()
    assert evaluator.are_equivalent_sql("select 1", "select 1") is False
