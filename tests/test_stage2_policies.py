from __future__ import annotations

from src.stage2.policies import greedy_policy, llm_sequence_policy
from src.stage2.schemas import Stage2InputRow


def test_greedy_policy_records_step_rewards_for_accepted_steps() -> None:
    row = Stage2InputRow(
        query_id="q1",
        original_sql="orig",
        candidate_rules=["R1", "R2"],
        llm_recommended_order=[],
    )

    rewrites = {
        ("orig", "R1"): ("sql_r1", 0.10),
        ("orig", "R2"): ("sql_r2", 0.10),
        ("sql_r1", "R2"): ("sql_r1_r2", 0.10),
    }
    latencies = {"orig": 10.0, "sql_r1": 8.0, "sql_r2": 9.0, "sql_r1_r2": 7.0}

    result = greedy_policy(
        row,
        max_steps=3,
        apply_rule=lambda sql, rule: rewrites[(sql, rule)],
        latency_of_sql=lambda sql: latencies[sql],
    )

    assert result.final_rule_sequence == ["R1", "R2"]
    assert result.step_rewards == [2.0, 1.0]
    assert result.final_sql == "sql_r1_r2"


def test_greedy_policy_stops_when_best_reward_non_positive() -> None:
    row = Stage2InputRow(
        query_id="q2",
        original_sql="orig",
        candidate_rules=["R1"],
        llm_recommended_order=[],
    )

    result = greedy_policy(
        row,
        max_steps=3,
        apply_rule=lambda sql, rule: ("same_latency_sql", 0.05),
        latency_of_sql=lambda sql: 10.0,
    )

    assert result.final_rule_sequence == []
    assert result.step_rewards == []
    assert result.final_sql == "orig"


def test_llm_sequence_policy_exposes_empty_step_rewards() -> None:
    row = Stage2InputRow(
        query_id="q3",
        original_sql="orig",
        candidate_rules=["R1"],
        llm_recommended_order=["R1"],
    )

    result = llm_sequence_policy(
        row,
        max_steps=3,
        apply_rule=lambda sql, rule: ("rewritten", 0.02),
    )

    assert result.final_rule_sequence == ["R1"]
    assert result.step_rewards == []
