"""Tests for Stage 1 candidate generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.llm.stage1_candidate_generation import Stage1CandidateGenerator, Stage1Input
from src.rules.rule_library import CalciteRule, load_standard_rule_library
from src.utils.config import Stage1Config


class FakeLLM:
    """Simple fake for deterministic test outputs."""

    def __init__(self, payload: dict):
        self.payload = payload

    def generate_json(self, *, model: str, prompt: str) -> dict:
        assert model
        assert "query_id" in prompt
        return self.payload


def test_stage1_happy_path_saves_file(tmp_path: Path) -> None:
    config = Stage1Config(max_rules=3, include_empty=True, output_dir=tmp_path)
    stage_input = Stage1Input(
        query_id="q_001",
        original_sql="SELECT * FROM t WHERE a > 1",
    )
    rules = [
        CalciteRule("FILTER_INTO_JOIN", "Push filter into join"),
        CalciteRule("PROJECT_TO_CALC", "Convert project to calc"),
    ]
    llm = FakeLLM(
        {
            "query_id": "q_001",
            "original_sql": "SELECT * FROM t WHERE a > 1",
            "candidate_pool_size": 3,
            "candidate_rules": ["FILTER_INTO_JOIN", "PROJECT_TO_CALC", "EMPTY"],
            "llm_recommended_order": ["FILTER_INTO_JOIN", "PROJECT_TO_CALC", "EMPTY"],
        }
    )

    generator = Stage1CandidateGenerator(config=config, llm_client=llm)
    result = generator.run_for_query(stage_input, rules)

    assert result["candidate_pool_size"] == 3
    assert (tmp_path / "q_001.json").exists()


def test_stage1_rejects_unknown_rule(tmp_path: Path) -> None:
    config = Stage1Config(max_rules=2, include_empty=False, output_dir=tmp_path)
    stage_input = Stage1Input(query_id="q_002", original_sql="SELECT 1")
    rules = [CalciteRule("PROJECT_TO_CALC", "Convert project to calc")]
    llm = FakeLLM(
        {
            "query_id": "q_002",
            "original_sql": "SELECT 1",
            "candidate_pool_size": 2,
            "candidate_rules": ["NOT_A_RULE"],
            "llm_recommended_order": ["NOT_A_RULE"],
        }
    )

    generator = Stage1CandidateGenerator(config=config, llm_client=llm)

    with pytest.raises(ValueError, match="Unknown rule selected"):
        generator.run_for_query(stage_input, rules)


def test_stage1_rejects_duplicate_candidate_rules(tmp_path: Path) -> None:
    config = Stage1Config(max_rules=2, include_empty=False, output_dir=tmp_path)
    stage_input = Stage1Input(query_id="q_003", original_sql="SELECT 1")
    rules = [CalciteRule("PROJECT_TO_CALC", "Convert project to calc")]
    llm = FakeLLM(
        {
            "query_id": "q_003",
            "original_sql": "SELECT 1",
            "candidate_pool_size": 2,
            "candidate_rules": ["PROJECT_TO_CALC", "PROJECT_TO_CALC"],
            "llm_recommended_order": ["PROJECT_TO_CALC"],
        }
    )

    generator = Stage1CandidateGenerator(config=config, llm_client=llm)

    with pytest.raises(ValueError, match="must not contain duplicates"):
        generator.run_for_query(stage_input, rules)


def test_load_standard_rule_library_supports_section_headers_and_dedup(tmp_path: Path) -> None:
    standard = tmp_path / "standard.txt"
    standard.write_text(
        "\n".join(
            [
                "rule_filter",
                "FILTER_REDUCE_EXPRESSIONS",
                "PROJECT_REDUCE_EXPRESSIONS",
                "rule_project",
                "PROJECT_REDUCE_EXPRESSIONS",
                "PROJECT_TO_CALC",
            ]
        ),
        encoding="utf-8",
    )

    loaded = load_standard_rule_library(standard)

    assert [rule.name for rule in loaded] == [
        "FILTER_REDUCE_EXPRESSIONS",
        "PROJECT_REDUCE_EXPRESSIONS",
        "PROJECT_TO_CALC",
    ]
