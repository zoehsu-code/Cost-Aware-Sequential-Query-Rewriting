"""CLI runner for Stage 1 candidate generation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from src.llm.offline_stub_client import OfflineStubLLMClient
from src.llm.openai_compatible_client import OpenAICompatibleLLMClient
from src.llm.stage1_candidate_generation import Stage1CandidateGenerator, Stage1Input
from src.rules.rule_library import load_standard_rule_library
from src.utils.config import Stage1Config


class _DryRunLLMClient:
    """Placeholder client for prompt-building checks in dry-run mode."""

    def generate_json(self, *, model: str, prompt: str) -> dict:
        raise RuntimeError("Dry-run mode does not call LLM")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Stage 1 candidate generation for one query.")
    parser.add_argument("--query-id")
    parser.add_argument("--original-sql")
    parser.add_argument(
        "--input-csv",
        help="Optional batch input CSV path with columns: query_id, original_sql",
    )
    parser.add_argument("--max-rules", type=int, default=5)
    parser.add_argument(
        "--include-empty",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether EMPTY is allowed/required under Stage 1 constraints.",
    )
    parser.add_argument(
        "--save-csv",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether to save per-query CSV sidecar output.",
    )
    parser.add_argument("--llm-model", default="gpt-4.1-mini")
    parser.add_argument("--prompt-version", default="v1")
    parser.add_argument("--output-dir", default="outputs/stage1")
    parser.add_argument("--rule-library", default="rule_library/standard.txt")
    parser.add_argument("--api-base-url", default="https://genai.vocareum.com/v1")
    parser.add_argument("--api-key-env-var", default="VOC_API_KEY")
    parser.add_argument("--api-key", default=None)
    parser.add_argument(
        "--llm-mode",
        choices=["openai", "offline"],
        default="openai",
        help="Use 'offline' to test without any external AI API.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs/rule library/prompt building without any LLM API call.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config = Stage1Config(
        max_rules=args.max_rules,
        include_empty=args.include_empty,
        llm_model=args.llm_model,
        prompt_version=args.prompt_version,
        output_dir=Path(args.output_dir),
        save_csv=args.save_csv,
        api_base_url=args.api_base_url,
        api_key_env_var=args.api_key_env_var,
    )
    llm_client = _DryRunLLMClient() if args.dry_run else None
    if llm_client is None:
        if args.llm_mode == "offline":
            llm_client = OfflineStubLLMClient()
        else:
            llm_client = OpenAICompatibleLLMClient(
                base_url=config.api_base_url,
                api_key_env_var=config.api_key_env_var,
                api_key=args.api_key,
            )
    generator = Stage1CandidateGenerator(config=config, llm_client=llm_client)
    rules = load_standard_rule_library(Path(args.rule_library))

    if args.input_csv:
        rows = list(csv.DictReader(Path(args.input_csv).read_text(encoding="utf-8").splitlines()))
        if not rows:
            raise ValueError(f"Input CSV is empty: {args.input_csv}")
        for row in rows:
            query_id = (row.get("query_id") or "").strip()
            original_sql = (row.get("original_sql") or "").strip()
            if not query_id or not original_sql:
                raise ValueError(
                    "Each CSV row must contain non-empty columns: query_id, original_sql"
                )
            stage_input = Stage1Input(query_id=query_id, original_sql=original_sql)
            if args.dry_run:
                prompt = generator.build_prompt(stage_input, rules)
                print(
                    json.dumps(
                        {
                            "dry_run": True,
                            "query_id": query_id,
                            "prompt_chars": len(prompt),
                            "planned_output_json": str(config.output_dir / f"{query_id}.json"),
                            "planned_output_csv": str(config.output_dir / f"{query_id}.csv"),
                        },
                        ensure_ascii=False,
                    )
                )
                continue
            result = generator.run_for_query(stage_input, rules)
            print(json.dumps(result, ensure_ascii=False))
        return

    if not args.query_id or not args.original_sql:
        raise ValueError("Provide --query-id and --original-sql, or use --input-csv")

    stage_input = Stage1Input(query_id=args.query_id, original_sql=args.original_sql)
    if args.dry_run:
        prompt = generator.build_prompt(stage_input, rules)
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "query_id": args.query_id,
                    "prompt_chars": len(prompt),
                    "planned_output_json": str(config.output_dir / f"{args.query_id}.json"),
                    "planned_output_csv": str(config.output_dir / f"{args.query_id}.csv"),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    result = generator.run_for_query(stage_input, rules)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
