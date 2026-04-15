"""Schemas and constants for Stage 2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_STEPS = 3
OUTPUT_COLUMNS = [
    "query_id",
    "policy",
    "selected_rules",
    "final_rule_sequence",
    "step_rewards",
    "original_sql",
    "rewritten_sql",
    "original_trimmed_mean_sec",
    "rewritten_trimmed_mean_sec",
    "speedup_ratio",
    "improvement_sec",
    "equivalence_result",
    "rewrite_success",
    "error_message",
    "llm_latency_ms",
    "rewrite_latency_sec",
    "processed_sec",
]


@dataclass(frozen=True)
class Stage2InputRow:
    """Input row parsed from Stage 1 CSV."""

    query_id: str
    original_sql: str
    candidate_rules: list[str]
    llm_recommended_order: list[str]
    llm_latency_ms: float | None = None
    greedy_step_reward_overrides: list[dict[str, float]] | None = None


@dataclass
class Stage2ResultRow:
    """One Stage 2 output row."""

    query_id: str
    policy: str
    selected_rules: list[str]
    final_rule_sequence: list[str]
    step_rewards: list[float]
    original_sql: str
    rewritten_sql: str
    original_trimmed_mean_sec: float | None
    rewritten_trimmed_mean_sec: float | None
    speedup_ratio: float | None
    improvement_sec: float | None
    equivalence_result: bool
    rewrite_success: bool
    error_message: str | None
    llm_latency_ms: float | None
    rewrite_latency_sec: float
    processed_sec: float

    def to_csv_row(self) -> dict[str, Any]:
        """Return row payload in the strict Stage 2 output format."""

        import json

        return {
            "query_id": self.query_id,
            "policy": self.policy,
            "selected_rules": json.dumps(self.selected_rules, ensure_ascii=False),
            "final_rule_sequence": json.dumps(self.final_rule_sequence, ensure_ascii=False),
            "step_rewards": json.dumps(self.step_rewards, ensure_ascii=False),
            "original_sql": self.original_sql,
            "rewritten_sql": self.rewritten_sql,
            "original_trimmed_mean_sec": self.original_trimmed_mean_sec,
            "rewritten_trimmed_mean_sec": self.rewritten_trimmed_mean_sec,
            "speedup_ratio": self.speedup_ratio,
            "improvement_sec": self.improvement_sec,
            "equivalence_result": self.equivalence_result,
            "rewrite_success": self.rewrite_success,
            "error_message": self.error_message,
            "llm_latency_ms": self.llm_latency_ms,
            "rewrite_latency_sec": self.rewrite_latency_sec,
            "processed_sec": self.processed_sec,
        }
