"""Offline greedy-backward reranker based on baseline/stage1 CSV + single-rule rewriter jar."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import time
from pathlib import Path

import pandas as pd

from src.stage2.evaluator import BenchmarkEvaluator


def parse_rules(cell) -> list[str]:
    if pd.isna(cell):
        return []
    if isinstance(cell, list):
        return [str(item) for item in cell]
    text = str(cell).strip()
    if not text:
        return []
    try:
        value = ast.literal_eval(text)
        if isinstance(value, list):
            return [str(item) for item in value]
    except Exception:
        pass
    return [part.strip() for part in text.split(",") if part.strip()]


def normalize_sql(sql: str) -> str:
    text = str(sql).strip()
    text = text.replace("`", "")
    text = " ".join(text.split())
    return text


class GreedyBackwardRunner:
    def __init__(
        self,
        benchmark: str,
        jar_path: Path,
        runs: int = 5,
        warmup_runs: int = 1,
    ) -> None:
        self.benchmark = benchmark
        self.jar_path = jar_path
        self.runs = runs
        self.warmup_runs = warmup_runs
        self.evaluator = BenchmarkEvaluator(benchmark=benchmark)

    def apply_one_rule(self, sql: str, rule: str) -> str | None:
        payload = json.dumps([self.benchmark, sql, rule], ensure_ascii=False)
        cmd = ["java", "-jar", str(self.jar_path)]
        try:
            result = subprocess.run(
                cmd,
                input=payload,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] rewrite failed for rule={rule}")
            if e.stderr:
                print(e.stderr.strip())
            return None

        rewritten = result.stdout.strip()
        if not rewritten:
            return None
        return normalize_sql(rewritten)

    def apply_sequence_with_time(self, sql: str, rules: list[str]) -> tuple[str | None, float | None]:
        current_sql = normalize_sql(sql)
        start = time.perf_counter()

        for rule in rules:
            rewritten = self.apply_one_rule(current_sql, rule)
            if rewritten is None:
                return None, None
            current_sql = normalize_sql(rewritten)

        elapsed = time.perf_counter() - start
        return current_sql, elapsed

    def safe_latency(self, sql: str | None) -> float | None:
        if sql is None:
            return None
        try:
            return self.evaluator.trimmed_mean_latency_sec(
                sql,
                runs=self.runs,
                warmup_runs=self.warmup_runs,
            )
        except Exception:
            return None

    def equivalent_sql(self, original_sql: str, rewritten_sql: str | None) -> bool:
        if rewritten_sql is None:
            return False
        try:
            return self.evaluator.are_equivalent_sql(original_sql, rewritten_sql)
        except Exception:
            return False

    def evaluate_sequence(self, original_sql: str, sequence: list[str]) -> dict:
        if not sequence:
            rewritten_sql = normalize_sql(original_sql)
            rewrite_sec = 0.0
        else:
            rewritten_sql, rewrite_sec = self.apply_sequence_with_time(original_sql, sequence)
            if rewritten_sql is None:
                return {
                    "rules": list(sequence),
                    "rewritten_sql": None,
                    "rewrite_sec": None,
                    "latency": None,
                    "equivalent": False,
                }

        latency = self.safe_latency(rewritten_sql)
        equivalent = self.equivalent_sql(original_sql, rewritten_sql) if rewritten_sql is not None else False

        return {
            "rules": list(sequence),
            "rewritten_sql": rewritten_sql,
            "rewrite_sec": rewrite_sec,
            "latency": latency,
            "equivalent": equivalent,
        }

    def backward_prune(self, original_sql: str, selected_rules: list[str]) -> tuple[dict, dict]:
        full = self.evaluate_sequence(original_sql, selected_rules)

        if full["rewritten_sql"] is None or full["latency"] is None:
            return full, full

        best_rules = list(full["rules"])
        q_cur = full["rewritten_sql"]
        lat_cur = full["latency"]
        rewrite_sec_cur = full["rewrite_sec"]
        eq_cur = full["equivalent"]

        improved = True

        # FIRST-IMPROVEMENT greedy backward pruning
        # A candidate is accepted only if:
        # 1. The rewrite succeeds
        # 2. The rewritten query is equivalent to the original query
        # 3. The latency is valid (not None)
        # 4. The latency is lower than the current best
        # Once such a candidate is found, accept it immediately,
        # break the loop, and restart from the updated rule set
        while improved:
            improved = False
            for idx in range(len(best_rules)):
                candidate_rules = best_rules[:idx] + best_rules[idx + 1 :]
                result = self.evaluate_sequence(original_sql, candidate_rules)

                if (
                    result["rewritten_sql"] is not None
                    and result["equivalent"]
                    and result["latency"] is not None
                    and result["latency"] < lat_cur
                ):
                    best_rules = candidate_rules
                    q_cur = result["rewritten_sql"]
                    lat_cur = result["latency"]
                    rewrite_sec_cur = result["rewrite_sec"]
                    eq_cur = result["equivalent"]
                    improved = True
                    break

        final = {
            "rules": best_rules,
            "rewritten_sql": q_cur,
            "rewrite_sec": rewrite_sec_cur,
            "latency": lat_cur,
            "equivalent": eq_cur,
        }
        return full, final


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run offline greedy-backward rerank from stage1/baseline csv")
    parser.add_argument("--stage1-csv", default=None)
    parser.add_argument("--baseline-csv", default=None)
    parser.add_argument("--output-csv", default="baseline/baseline_reranked.csv")
    parser.add_argument("--benchmark", choices=["tpch", "tpchj"], default="tpch")
    parser.add_argument("--rewrite-jar-path", default="build/single_rule_rewriter.jar")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--warmup-runs", type=int, default=1)
    return parser


def main() -> None:
    args = build_parser().parse_args()

    has_stage1 = bool(args.stage1_csv)
    has_baseline = bool(args.baseline_csv)

    if has_stage1 == has_baseline:
        raise ValueError("Provide exactly one input source: --stage1-csv OR --baseline-csv")

    input_path = Path(args.stage1_csv) if has_stage1 else Path(args.baseline_csv)
    source = "stage1" if has_stage1 else "baseline"

    df = pd.read_csv(input_path)

    runner = GreedyBackwardRunner(
        benchmark=args.benchmark,
        jar_path=Path(args.rewrite_jar_path),
        runs=args.runs,
        warmup_runs=args.warmup_runs,
    )

    def selected_rules_for_row(row) -> list[str]:
        for col in ("candidate_rules", "selected_rules", "llm_recommended_order", "rule_set", "ruleset"):
            if col in row and pd.notna(row[col]):
                parsed = parse_rules(row[col])
                if parsed:
                    return parsed
        return []

    rewrite_all_rules_sql_col = []
    rewrite_all_rules_trimmed_mean_sec_col = []
    selected_rules_rewrite_sec_col = []
    rewrite_all_equivalence_col = []

    final_rule_set_col = []
    final_sql_col = []
    final_trimmed_mean_sec_col = []
    final_rules_rewrite_sec_col = []
    final_equivalence_col = []

    for idx, row in df.iterrows():
        print(f"Processing {idx + 1}/{len(df)}")

        original_sql = row["original_sql"]
        selected_rules = selected_rules_for_row(row)

        full_result, final_result = runner.backward_prune(original_sql, selected_rules)

        rewrite_all_rules_sql_col.append(full_result["rewritten_sql"])
        rewrite_all_rules_trimmed_mean_sec_col.append(full_result["latency"])
        selected_rules_rewrite_sec_col.append(full_result["rewrite_sec"])
        rewrite_all_equivalence_col.append(full_result["equivalent"])

        final_rule_set_col.append(json.dumps(final_result["rules"], ensure_ascii=False))
        final_sql_col.append(final_result["rewritten_sql"])
        final_trimmed_mean_sec_col.append(final_result["latency"])
        final_rules_rewrite_sec_col.append(final_result["rewrite_sec"])
        final_equivalence_col.append(final_result["equivalent"])

    df["rewrite_all_rules_sql"] = rewrite_all_rules_sql_col
    df["rewrite_all_rules_trimmed_mean_sec"] = rewrite_all_rules_trimmed_mean_sec_col
    df["selected_rules_rewrite_sec"] = selected_rules_rewrite_sec_col
    df["rewrite_all_equivalence_result"] = rewrite_all_equivalence_col

    df["final_rule_set"] = final_rule_set_col
    df["final_sql"] = final_sql_col
    df["final_trimmed_mean_sec"] = final_trimmed_mean_sec_col
    df["final_rules_rewrite_sec"] = final_rules_rewrite_sec_col
    df["final_equivalence_result"] = final_equivalence_col

    output_path = Path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"\n✅ source={source} input={input_path} saved={output_path}")


if __name__ == "__main__":
    main()
