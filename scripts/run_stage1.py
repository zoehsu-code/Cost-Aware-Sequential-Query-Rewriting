"""CLI runner for Stage 1 candidate generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.llm.openai_compatible_client import OpenAICompatibleLLMClient
from src.llm.stage1_candidate_generation import Stage1CandidateGenerator, Stage1Input
from src.rules.rule_library import load_standard_rule_library
from src.utils.config import Stage1Config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Stage 1 candidate generation for one query.")
    parser.add_argument("--query-id", required=True)
    parser.add_argument("--original-sql", required=True)
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
    parser.add_argument("--api-base-url", default="https://api.openai.com/v1")
    parser.add_argument("--api-key-env-var", default="OPENAI_API_KEY")
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
    llm_client = OpenAICompatibleLLMClient(
        base_url=config.api_base_url, api_key_env_var=config.api_key_env_var
    )
    generator = Stage1CandidateGenerator(config=config, llm_client=llm_client)
    rules = load_standard_rule_library(Path(args.rule_library))
    result = generator.run_for_query(
        Stage1Input(query_id=args.query_id, original_sql=args.original_sql), rules
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
