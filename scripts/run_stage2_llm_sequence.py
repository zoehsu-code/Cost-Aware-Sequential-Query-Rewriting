"""Run Stage 2 with llm_sequence policy."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.stage2.runner import Stage2RunConfig, Stage2Runner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Stage 2 (llm_sequence)")
    parser.add_argument("--stage1-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--db-id", default=None, help="Optional; defaults to benchmark name")
    parser.add_argument("--benchmark", choices=["tpch", "tpchj"], default="tpch")
    parser.add_argument("--database-path", default=None)
    parser.add_argument("--tpch-scale-factor", type=float, default=1.0)
    parser.add_argument("--tpchj-init-sql", default=None)
    parser.add_argument("--rewrite-jar-path", default=None)
    parser.add_argument("--rewrite-main-class", default=None)
    parser.add_argument("--rewrite-timeout-sec", type=int, default=120)
    parser.add_argument("--eval-runs", type=int, default=5)
    parser.add_argument("--eval-warmup-runs", type=int, default=1)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = Stage2RunConfig(
        stage1_csv=Path(args.stage1_csv),
        output_csv=Path(args.output_csv),
        policy="llm_sequence",
        db_id=args.db_id,
        benchmark=args.benchmark,
        database_path=Path(args.database_path) if args.database_path else None,
        tpch_scale_factor=args.tpch_scale_factor,
        tpchj_init_sql=Path(args.tpchj_init_sql) if args.tpchj_init_sql else None,
        rewrite_jar_path=Path(args.rewrite_jar_path) if args.rewrite_jar_path else None,
        rewrite_main_class=args.rewrite_main_class,
        rewrite_timeout_sec=args.rewrite_timeout_sec,
        eval_runs=args.eval_runs,
        eval_warmup_runs=args.eval_warmup_runs,
    )
    Stage2Runner(config).run()


if __name__ == "__main__":
    main()
