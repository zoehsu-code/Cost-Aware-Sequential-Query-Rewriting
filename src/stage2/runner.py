"""Stage 2 runner orchestrating rewrite, evaluation, and CSV outputs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from src.stage2.calcite_rewriter import CalciteRewriter
from src.stage2.evaluator import BenchmarkEvaluator
from src.stage2.io_utils import read_stage1_csv, write_stage2_csv
from src.stage2.policies import greedy_policy, llm_sequence_policy
from src.stage2.schemas import MAX_STEPS, Stage2ResultRow


@dataclass(frozen=True)
class Stage2RunConfig:
    stage1_csv: Path
    output_csv: Path
    policy: str
    benchmark: str
    db_id: str | None = None
    database_path: Path | None = None
    tpch_scale_factor: float = 1.0
    tpchj_init_sql: Path | None = None
    rewrite_jar_path: Path | None = None
    rewrite_main_class: str | None = None
    rewrite_timeout_sec: int = 120
    eval_runs: int = 5
    eval_warmup_runs: int = 1


class Stage2Runner:
    """Run Stage 2 for one policy on all rows from Stage 1 CSV."""

    def __init__(self, config: Stage2RunConfig) -> None:
        self.config = config
        self.rewriter = CalciteRewriter(
            jar_path=config.rewrite_jar_path,
            java_main_class=config.rewrite_main_class,
            timeout_sec=config.rewrite_timeout_sec,
        )
        self.evaluator = BenchmarkEvaluator(
            benchmark=config.benchmark,
            database_path=config.database_path,
            tpch_scale_factor=config.tpch_scale_factor,
            tpchj_init_sql=config.tpchj_init_sql,
        )

        self._latency_cache: dict[str, float] = {}
        self._equivalence_cache: dict[str, bool] = {}

    def _apply_rule(self, current_sql: str, rule: str) -> tuple[str, float]:
        resolved_db_id = self.config.db_id or self.config.benchmark
        return self.rewriter.apply_rule(db_id=resolved_db_id, sql=current_sql, rule=rule)

    def _latency_of_sql(self, sql: str) -> float:
        if sql in self._latency_cache:
            return self._latency_cache[sql]
        latency = self.evaluator.trimmed_mean_latency_sec(
            sql,
            runs=self.config.eval_runs,
            warmup_runs=self.config.eval_warmup_runs,
        )
        self._latency_cache[sql] = latency
        return latency

    def _is_equivalent_to_original(self, original_sql: str, candidate_sql: str) -> bool:
        key = f"{original_sql}\n---\n{candidate_sql}"
        if key in self._equivalence_cache:
            return self._equivalence_cache[key]
        result = self.evaluator.are_equivalent_sql(original_sql, candidate_sql)
        self._equivalence_cache[key] = result
        return result

    def _run_one_row(self, row) -> Stage2ResultRow:
        start = time.perf_counter()
        policy = self.config.policy
        rewrite_success = True
        error_message: str | None = None
        rewritten_sql = row.original_sql
        final_sequence: list[str] = []
        step_rewards: list[float] = []
        rewrite_latency_sec = 0.0
        equivalence_result = True

        try:
            if policy == "llm_sequence":
                policy_result = llm_sequence_policy(
                    row,
                    max_steps=MAX_STEPS,
                    apply_rule=self._apply_rule,
                )
            elif policy == "greedy":
                policy_result = greedy_policy(
                    row,
                    max_steps=MAX_STEPS,
                    apply_rule=self._apply_rule,
                    latency_of_sql=self._latency_of_sql,
                )
            else:
                raise ValueError("Unsupported policy. Only 'llm_sequence' and 'greedy' are allowed")

            rewritten_sql = policy_result.final_sql
            final_sequence = policy_result.final_rule_sequence
            step_rewards = policy_result.step_rewards
            rewrite_latency_sec = policy_result.rewrite_latency_sec
            equivalence_result = self._is_equivalent_to_original(row.original_sql, rewritten_sql)
        except Exception as exc:
            rewrite_success = False
            error_message = str(exc)
            equivalence_result = False

        original_latency: float | None = None
        rewritten_latency: float | None = None
        speedup_ratio: float | None = None
        improvement_sec: float | None = None

        if rewrite_success and equivalence_result:
            try:
                original_latency = self._latency_of_sql(row.original_sql)
                rewritten_latency = self._latency_of_sql(rewritten_sql)
                if rewritten_latency > 0:
                    speedup_ratio = original_latency / rewritten_latency
                improvement_sec = original_latency - rewritten_latency
            except Exception as exc:
                rewrite_success = False
                equivalence_result = False
                error_message = f"Evaluation failed: {exc}"

        processed_sec = time.perf_counter() - start
        return Stage2ResultRow(
            query_id=row.query_id,
            policy=policy,
            selected_rules=row.candidate_rules,
            final_rule_sequence=final_sequence,
            step_rewards=step_rewards,
            original_sql=row.original_sql,
            rewritten_sql=rewritten_sql,
            original_trimmed_mean_sec=original_latency,
            rewritten_trimmed_mean_sec=rewritten_latency,
            speedup_ratio=speedup_ratio,
            improvement_sec=improvement_sec,
            equivalence_result=equivalence_result,
            rewrite_success=rewrite_success,
            error_message=error_message,
            llm_latency_ms=row.llm_latency_ms,
            rewrite_latency_sec=rewrite_latency_sec,
            processed_sec=processed_sec,
        )

    def run(self) -> list[Stage2ResultRow]:
        rows = read_stage1_csv(self.config.stage1_csv)
        results = [self._run_one_row(row) for row in rows]
        write_stage2_csv(self.config.output_csv, results)
        return results
