"""Stage 2 policies: llm_sequence and greedy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.stage2.schemas import MAX_STEPS, Stage2InputRow


@dataclass
class PolicyResult:
    final_sql: str
    final_rule_sequence: list[str]
    step_rewards: list[float]
    rewrite_latency_sec: float


def _clean_rule_list(rules: list[str]) -> list[str]:
    return [rule for rule in rules if rule and rule != "EMPTY"]


def llm_sequence_policy(
    row: Stage2InputRow,
    *,
    max_steps: int = MAX_STEPS,
    apply_rule: Callable[[str, str], tuple[str, float]],
) -> PolicyResult:
    """Apply rules in Stage 1 recommended order, fallback to candidate_rules."""

    sequence_source = row.llm_recommended_order or row.candidate_rules
    candidate_set = set(_clean_rule_list(row.candidate_rules))

    sequence: list[str] = []
    for rule in _clean_rule_list(sequence_source):
        if rule in candidate_set and rule not in sequence:
            sequence.append(rule)
        if len(sequence) >= max_steps:
            break

    current_sql = row.original_sql
    total_rewrite_latency = 0.0
    for rule in sequence:
        current_sql, latency = apply_rule(current_sql, rule)
        total_rewrite_latency += latency

    return PolicyResult(
        final_sql=current_sql,
        final_rule_sequence=sequence,
        step_rewards=[],
        rewrite_latency_sec=total_rewrite_latency,
    )


def greedy_policy(
    row: Stage2InputRow,
    *,
    max_steps: int = MAX_STEPS,
    apply_rule: Callable[[str, str], tuple[str, float]],
    latency_of_sql: Callable[[str], float],
) -> PolicyResult:
    """Greedy policy with optional per-step reward overrides.

    Default reward is real latency delta:
        reward = current_latency - candidate_latency
    If row.greedy_step_reward_overrides is provided, current step can override
    reward by rule name, e.g. [{"R1": 1.2, "R2": -0.1}, {"R2": 0.6}].
    """

    current_sql = row.original_sql
    current_latency = latency_of_sql(current_sql)
    remaining_rules = _clean_rule_list(row.candidate_rules)
    sequence: list[str] = []
    step_rewards: list[float] = []
    total_rewrite_latency = 0.0

    for step_index in range(max_steps):
        best_rule: str | None = None
        best_sql: str | None = None
        best_reward = float("-inf")
        best_rewrite_latency = 0.0
        candidate_rewards: dict[str, float] = {}

        for rule in list(remaining_rules):
            try:
                rewritten_sql, rewrite_latency = apply_rule(current_sql, rule)
            except Exception:
                continue

            candidate_latency = latency_of_sql(rewritten_sql)
            reward = current_latency - candidate_latency
            candidate_rewards[rule] = reward
            print(
                f"[GreedyCandidate] query_id={row.query_id} step={step_index + 1} "
                f"rule={rule} current_latency={current_latency} "
                f"candidate_latency={candidate_latency} reward={reward}"
            )
            if reward > best_reward:
                best_reward = reward
                best_rule = rule
                best_sql = rewritten_sql
                best_rewrite_latency = rewrite_latency

        if candidate_rewards:
            print(
                f"[GreedyStep] query_id={row.query_id} step={step_index + 1} "
                f"candidate_rewards={candidate_rewards} best_rule={best_rule} best_reward={best_reward}"
            )

        if best_rule is None:
            break

        # Required early stopping.
        if best_reward <= 0:
            break

        current_sql = best_sql if best_sql is not None else current_sql
        current_latency = latency_of_sql(current_sql)
        sequence.append(best_rule)
        step_rewards.append(best_reward)
        total_rewrite_latency += best_rewrite_latency
        remaining_rules.remove(best_rule)

    return PolicyResult(
        final_sql=current_sql,
        final_rule_sequence=sequence,
        step_rewards=step_rewards,
        rewrite_latency_sec=total_rewrite_latency,
    )
