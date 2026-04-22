"""Stage 1 LLM candidate rule-pool generation."""

from __future__ import annotations

import json
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from src.rules.rule_library import (
    CalciteRule,
    normalize_rule_library,
    render_rule_library_for_prompt,
    rule_names,
)
from src.utils.config import Stage1Config


@dataclass(frozen=True)
class Stage1Input:
    """Input payload for Stage 1 candidate generation."""

    query_id: str
    original_sql: str


class LLMClient(Protocol):
    """Protocol for structured-output LLM calls used by Stage 1."""

    def generate_json(self, *, model: str, prompt: str) -> dict[str, Any]:
        """Generate a JSON-like dictionary from the provided prompt."""


class Stage1CandidateGenerator:
    """Build prompt, call LLM, validate output, and persist one file per query."""

    def __init__(self, config: Stage1Config, llm_client: LLMClient) -> None:
        self.config = config
        self.llm_client = llm_client

    def build_prompt(self, stage_input: Stage1Input, rule_library: list[CalciteRule]) -> str:
        """Build strict prompt for selecting a query-specific candidate rule pool."""

        include_empty_text = "enabled" if self.config.include_empty else "disabled"
        return (
            "You are Stage 1 in a two-stage SQL rewrite system.\n"
            "Select at most max_rules candidate rewrite rules from the Apache Calcite rule library.\n"
            "Do NOT generate rewritten SQL. Do NOT execute rules. Do NOT pick final trajectory.\n"
            "Return valid JSON only with keys: "
            "query_id, original_sql, candidate_pool_size, candidate_rules, llm_recommended_order.\n"
            f"prompt_version: {self.config.prompt_version}\n"
            f"query_id: {stage_input.query_id}\n"
            f"original_sql: {stage_input.original_sql}\n"
            f"max_rules: {self.config.max_rules}\n"
            f"include_empty: {include_empty_text}\n"
            "candidate_pool_size must equal max_rules.\n"
            "candidate_rules must contain no duplicates.\n"
            "llm_recommended_order must be a permutation or ordered subset of candidate_rules.\n"
            "Allowed rule library:\n"
            f"{render_rule_library_for_prompt(rule_library)}\n"
            "Use EMPTY only if include_empty is enabled.\n"
        )

    def run_for_query(self, stage_input: Stage1Input, rule_library: list[CalciteRule]) -> dict[str, Any]:
        """Generate and validate Stage 1 output for one query."""

        normalized_library = normalize_rule_library(rule_library)
        prompt = self.build_prompt(stage_input, normalized_library)
        output = self.llm_client.generate_json(model=self.config.llm_model, prompt=prompt)
        validated = self.validate_output(output, stage_input, normalized_library)
        self.save_output(validated)
        return validated

    def validate_output(
        self,
        output: dict[str, Any],
        stage_input: Stage1Input,
        rule_library: list[CalciteRule],
    ) -> dict[str, Any]:
        """Validate output shape and semantic constraints."""

        required_keys = {
            "query_id",
            "original_sql",
            "candidate_pool_size",
            "candidate_rules",
            "llm_recommended_order",
        }
        if set(output.keys()) != required_keys:
            raise ValueError("Output JSON keys do not match required structure")

        output_query_id = str(output["query_id"])
        if output_query_id != stage_input.query_id:
            raise ValueError("query_id must be preserved exactly")
        output["query_id"] = stage_input.query_id
        if output["original_sql"] != stage_input.original_sql:
            output["original_sql"] = stage_input.original_sql

        candidate_pool_size = output["candidate_pool_size"]
        if candidate_pool_size != self.config.max_rules:
            raise ValueError("candidate_pool_size must equal configured max_rules")

        candidate_rules = output["candidate_rules"]
        if not isinstance(candidate_rules, list) or not all(
            isinstance(rule, str) for rule in candidate_rules
        ):
            raise ValueError("candidate_rules must be a list of strings")
        if len(candidate_rules) > self.config.max_rules:
            raise ValueError("candidate_rules must contain at most max_rules entries")
        if len(set(candidate_rules)) != len(candidate_rules):
            raise ValueError("candidate_rules must not contain duplicates")

        allowed_rules = rule_names(rule_library)
        for rule in candidate_rules:
            if rule == "EMPTY":
                if not self.config.include_empty:
                    raise ValueError("EMPTY is not allowed when include_empty is disabled")
                continue
            if rule not in allowed_rules:
                raise ValueError(f"Unknown rule selected: {rule}")

        if self.config.include_empty and len(candidate_rules) < self.config.max_rules:
            if "EMPTY" not in candidate_rules:
                raise ValueError("EMPTY must be included when include_empty is enabled")

        order = output["llm_recommended_order"]
        if not isinstance(order, list) or not all(isinstance(rule, str) for rule in order):
            raise ValueError("llm_recommended_order must be a list of strings")
        if len(set(order)) != len(order):
            raise ValueError("llm_recommended_order must not contain duplicates")
        if any(rule not in set(candidate_rules) for rule in order):
            raise ValueError(
                "llm_recommended_order must be a permutation or ordered subset of candidate_rules"
            )

        return output

    def save_output(self, output: dict[str, Any]) -> Path:
        """Save one JSON file per query under a JSON subfolder (and optional CSV sidecar)."""

        output_dir = self.config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        json_dir = output_dir / "json"
        json_dir.mkdir(parents=True, exist_ok=True)
        path = json_dir / f"{output['query_id']}.json"
        path.write_text(json.dumps(output, indent=2), encoding="utf-8")
        if self.config.save_csv:
            self.save_output_csv(output)
        return path

    def save_output_csv(self, output: dict[str, Any]) -> Path:
        """Append output row into one consolidated CSV for human inspection."""

        output_dir = self.config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "stage1_results.csv"
        fieldnames = [
            "query_id",
            "original_sql",
            "candidate_pool_size",
            "candidate_rules",
            "llm_recommended_order",
        ]
        file_exists = path.exists() and path.stat().st_size > 0
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
            )
            if not file_exists:
                writer.writeheader()
            writer.writerow(
                {
                    "query_id": output["query_id"],
                    "original_sql": output["original_sql"],
                    "candidate_pool_size": output["candidate_pool_size"],
                    "candidate_rules": json.dumps(output["candidate_rules"], ensure_ascii=False),
                    "llm_recommended_order": json.dumps(
                        output["llm_recommended_order"], ensure_ascii=False
                    ),
                }
            )
        return path
