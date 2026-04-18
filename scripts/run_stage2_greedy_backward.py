"""Offline greedy-backward reranker based on baseline CSV + single-rule rewriter jar."""

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
    text = text.replace("APP.", "")
    return " ".join(text.split())


class GreedyBackwardRunner:
    def __init__(self, *, benchmark: str, jar_path: Path, runs: int, warmup_runs: int) -> None:
        self.benchmark = benchmark
        self.jar_path = jar_path
        self.runs = runs
        self.warmup_runs = warmup_runs
        self.evaluator = BenchmarkEvaluator(benchmark=benchmark)

    def apply_rule(self, sql: str, rule: str) -> str | None:
        payload = json.dumps([self.benchmark, sql, rule], ensure_ascii=False)
        try:
            completed = subprocess.run(
                ["java", "-jar", str(self.jar_path)],
                input=payload,
                text=True,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            return None
        return completed.stdout.strip()

    def apply_sequence_with_time(self, original_sql: str, sequence: list[str]) -> tuple[str | None, float | None]:
        current_sql = original_sql
        start = time.perf_counter()
        for rule in sequence:
            rewritten = self.apply_rule(current_sql, rule)
            if rewritten is None:
                return None, None
            current_sql = normalize_sql(rewritten)
        return current_sql, (time.perf_counter() - start)

    def safe_latency(self, sql: str) -> float | None:
        try:
            return self.evaluator.trimmed_mean_latency_sec(
                normalize_sql(sql),
                runs=self.runs,
                warmup_runs=self.warmup_runs,
            )
        except Exception:
            return None

    def equivalent_sql(self, original_sql: str, rewritten_sql: str) -> bool:
        return self.evaluator.are_equivalent_sql(
            normalize_sql(original_sql),
            normalize_sql(rewritten_sql),
        )

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
        baseline = self.evaluate_sequence(original_sql, [])
        full = self.evaluate_sequence(original_sql, selected_rules)

        if (
            full["rewritten_sql"] is None
            or not full["equivalent"]
            or full["latency"] is None
            or baseline["latency"] is None
            or full["latency"] >= baseline["latency"]
        ):
            return full, baseline

        current = full
        while True:
            best_candidate = None
            for idx in range(len(current["rules"])):
                candidate_rules = current["rules"][:idx] + current["rules"][idx + 1 :]
                result = self.evaluate_sequence(original_sql, candidate_rules)
                if (
                    result["rewritten_sql"] is not None
                    and result["equivalent"]
                    and result["latency"] is not None
                    and result["latency"] < current["latency"]
                ):
                    if best_candidate is None or result["latency"] < best_candidate["latency"]:
                        best_candidate = result
            if best_candidate is None:
                break
            current = best_candidate
            if not current["rules"]:
                break
        return full, current


def diff_sec(old, new):
    if pd.isna(old) or pd.isna(new) or old is None or new is None:
        return None
    return old - new


def diff_pct(old, new):
    if pd.isna(old) or pd.isna(new) or old is None or new is None or old == 0:
        return None
    return round((old - new) / old * 100, 2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run offline greedy-backward rerank from baseline csv")
    parser.add_argument("--input-csv", default="baseline/baseline.csv")
    parser.add_argument("--stage1-csv", default="outputs/stage1/stage1_results.csv")
    parser.add_argument("--output-csv", default="baseline/baseline_reranked.csv")
    parser.add_argument("--benchmark", choices=["tpch", "tpchj"], default="tpch")
    parser.add_argument("--rewrite-jar-path", default="build/single_rule_rewriter.jar")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--warmup-runs", type=int, default=1)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    df = pd.read_csv(args.input_csv)
    stage1_df = pd.read_csv(args.stage1_csv)
    runner = GreedyBackwardRunner(
        benchmark=args.benchmark,
        jar_path=Path(args.rewrite_jar_path),
        runs=args.runs,
        warmup_runs=args.warmup_runs,
    )

    def stage1_rules_for_row(baseline_row) -> list[str]:
        if "query_id" in baseline_row and pd.notna(baseline_row["query_id"]) and "query_id" in stage1_df.columns:
            matches = stage1_df[stage1_df["query_id"] == baseline_row["query_id"]]
        else:
            matches = pd.DataFrame()
        if matches.empty and "original_sql" in stage1_df.columns:
            matches = stage1_df[stage1_df["original_sql"] == baseline_row["original_sql"]]
        if matches.empty:
            return []

        stage1_row = matches.iloc[0]
        for col in ("selected_rules", "llm_recommended_order", "candidate_rules"):
            if col in stage1_row and pd.notna(stage1_row[col]):
                parsed = parse_rules(stage1_row[col])
                if parsed:
                    return parsed
        return []

    new_original_trimmed_mean_sec = []
    new_rewritten_trimmed_mean_sec = []
    new_equivalence_result = []

    rewrite_all_rules_sql_col = []
    rewrite_all_rules_trimmed_mean_sec_col = []
    selected_rules_rewrite_sec_col = []

    final_rules_col = []
    final_sql_col = []
    final_trimmed_mean_sec_col = []
    final_rules_rewrite_sec_col = []

    final_improvement_sec_vs_original_col = []
    final_improvement_pct_vs_original_col = []
    final_improvement_sec_vs_rewrite_all_col = []
    final_improvement_pct_vs_rewrite_all_col = []
    rewrite_time_saved_sec_col = []
    rewrite_time_saved_pct_col = []
    rewritten_improvement_sec_vs_original_col = []
    rewritten_improvement_pct_vs_original_col = []

    for idx, row in df.iterrows():
        print(f"Processing {idx + 1}/{len(df)}")
        original_sql = row["original_sql"]
        rewritten_sql_old = row["rewritten_sql"] if "rewritten_sql" in row else None
        selected_rules = stage1_rules_for_row(row)

        original_lat = runner.safe_latency(original_sql)
        rewritten_lat = runner.safe_latency(rewritten_sql_old) if pd.notna(rewritten_sql_old) else None
        eq_old = runner.equivalent_sql(original_sql, rewritten_sql_old) if pd.notna(rewritten_sql_old) else None

        new_original_trimmed_mean_sec.append(original_lat)
        new_rewritten_trimmed_mean_sec.append(rewritten_lat)
        new_equivalence_result.append(eq_old)

        full_result, final_result = runner.backward_prune(original_sql, selected_rules)

        rewrite_all_rules_sql_col.append(full_result["rewritten_sql"])
        rewrite_all_rules_trimmed_mean_sec_col.append(full_result["latency"])
        selected_rules_rewrite_sec_col.append(full_result["rewrite_sec"])

        final_rules_col.append(json.dumps(final_result["rules"], ensure_ascii=False))
        final_sql_col.append(final_result["rewritten_sql"])
        final_trimmed_mean_sec_col.append(final_result["latency"])
        final_rules_rewrite_sec_col.append(final_result["rewrite_sec"])

        rewrite_all_lat = full_result["latency"]
        final_lat = final_result["latency"]
        full_rw_sec = full_result["rewrite_sec"]
        final_rw_sec = final_result["rewrite_sec"]

        final_improvement_sec_vs_original_col.append(diff_sec(original_lat, final_lat))
        final_improvement_pct_vs_original_col.append(diff_pct(original_lat, final_lat))
        final_improvement_sec_vs_rewrite_all_col.append(diff_sec(rewrite_all_lat, final_lat))
        final_improvement_pct_vs_rewrite_all_col.append(diff_pct(rewrite_all_lat, final_lat))
        rewrite_time_saved_sec_col.append(diff_sec(full_rw_sec, final_rw_sec))
        rewrite_time_saved_pct_col.append(diff_pct(full_rw_sec, final_rw_sec))
        rewritten_improvement_sec_vs_original_col.append(diff_sec(original_lat, rewritten_lat))
        rewritten_improvement_pct_vs_original_col.append(diff_pct(original_lat, rewritten_lat))

    df["original_trimmed_mean_sec"] = new_original_trimmed_mean_sec
    df["rewritten_trimmed_mean_sec"] = new_rewritten_trimmed_mean_sec
    df["equivalence_result"] = new_equivalence_result

    df["rewrite_all_rules_sql"] = rewrite_all_rules_sql_col
    df["rewrite_all_rules_trimmed_mean_sec"] = rewrite_all_rules_trimmed_mean_sec_col
    df["selected_rules_rewrite_sec"] = selected_rules_rewrite_sec_col

    df["final_rules"] = final_rules_col
    df["final_sql"] = final_sql_col
    df["final_trimmed_mean_sec"] = final_trimmed_mean_sec_col
    df["final_rules_rewrite_sec"] = final_rules_rewrite_sec_col

    df["rewritten_improvement_sec_vs_original"] = rewritten_improvement_sec_vs_original_col
    df["rewritten_improvement_pct_vs_original"] = rewritten_improvement_pct_vs_original_col
    df["final_improvement_sec_vs_original"] = final_improvement_sec_vs_original_col
    df["final_improvement_pct_vs_original"] = final_improvement_pct_vs_original_col
    df["final_improvement_sec_vs_rewrite_all"] = final_improvement_sec_vs_rewrite_all_col
    df["final_improvement_pct_vs_rewrite_all"] = final_improvement_pct_vs_rewrite_all_col
    df["rewrite_time_saved_sec"] = rewrite_time_saved_sec_col
    df["rewrite_time_saved_pct"] = rewrite_time_saved_pct_col

    output_path = Path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"\n✅ Saved to {output_path}")


if __name__ == "__main__":
    main()
