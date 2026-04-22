"""Offline llm-sequence runner based on stage1/baseline CSV + single-rule rewriter jar."""

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


class LLMSequenceRunner:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run offline llm-sequence evaluation from stage1/baseline csv"
    )
    parser.add_argument(
        "--stage1-csv",
        default=None,
        help="Input CSV path. If omitted, path is resolved by --input-source.",
    )
    parser.add_argument(
        "--input-source",
        choices=["stage1", "baseline"],
        default="stage1",
        help="Select default input CSV source when --stage1-csv is omitted.",
    )
    parser.add_argument(
        "--baseline-csv",
        default="baseline/stage1_results.csv",
        help="Default baseline CSV path when --input-source=baseline.",
    )
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--benchmark", choices=["tpch", "tpchj"], default="tpch")
    parser.add_argument("--rewrite-jar-path", default="build/single_rule_rewriter.jar")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--warmup-runs", type=int, default=1)
    return parser


def resolve_input_csv(args: argparse.Namespace) -> tuple[Path, str]:
    if args.stage1_csv:
        return Path(args.stage1_csv), "custom"
    if args.input_source == "baseline":
        return Path(args.baseline_csv), "baseline"
    return Path("outputs/stage1/stage1_results.csv"), "stage1"


def main() -> None:
    args = build_parser().parse_args()

    input_path, source = resolve_input_csv(args)
    df = pd.read_csv(input_path)

    runner = LLMSequenceRunner(
        benchmark=args.benchmark,
        jar_path=Path(args.rewrite_jar_path),
        runs=args.runs,
        warmup_runs=args.warmup_runs,
    )

    def selected_rules_for_row(row) -> list[str]:
        # Prefer LLM recommended order if available.
        for col in ("llm_recommended_order", "candidate_rules", "selected_rules", "rule_set", "ruleset"):
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

        result = runner.evaluate_sequence(original_sql, selected_rules)

        # Keep column names aligned with greedy_backward output.
        rewrite_all_rules_sql_col.append(result["rewritten_sql"])
        rewrite_all_rules_trimmed_mean_sec_col.append(result["latency"])
        selected_rules_rewrite_sec_col.append(result["rewrite_sec"])
        rewrite_all_equivalence_col.append(result["equivalent"])

        final_rule_set_col.append(json.dumps(result["rules"], ensure_ascii=False))
        final_sql_col.append(result["rewritten_sql"])
        final_trimmed_mean_sec_col.append(result["latency"])
        final_rules_rewrite_sec_col.append(result["rewrite_sec"])
        final_equivalence_col.append(result["equivalent"])

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
