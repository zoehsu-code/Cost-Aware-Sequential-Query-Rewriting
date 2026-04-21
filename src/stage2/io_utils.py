"""I/O helpers for Stage 2."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.stage2.schemas import OUTPUT_COLUMNS, Stage2InputRow, Stage2ResultRow


def _parse_json_list(raw: str | None, field_name: str) -> list[str]:
    if raw is None:
        return []
    text = raw.strip()
    if not text:
        return []
    data = json.loads(text)
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise ValueError(f"{field_name} must be a JSON string array")
    return data


def _parse_rule_list(raw: str | None, field_name: str) -> list[str]:
    """Parse rule list from JSON array text or simple delimiter-separated text."""

    if raw is None:
        return []
    text = raw.strip()
    if not text:
        return []

    try:
        data = json.loads(text)
        if isinstance(data, list) and all(isinstance(item, str) for item in data):
            return data
    except json.JSONDecodeError:
        pass

    separators = [",", "|", ";"]
    for separator in separators:
        if separator in text:
            parsed = [item.strip() for item in text.split(separator) if item.strip()]
            if parsed:
                return parsed

    raise ValueError(f"{field_name} must be a JSON string array or delimiter-separated string")


def _parse_optional_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    return float(text)


def _parse_optional_step_reward_overrides(raw: str | None) -> list[dict[str, float]] | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("greedy_step_reward_overrides must be a JSON array")
    parsed: list[dict[str, float]] = []
    for index, step_item in enumerate(data):
        if not isinstance(step_item, dict):
            raise ValueError(
                f"greedy_step_reward_overrides[{index}] must be a JSON object of rule->reward"
            )
        step_map: dict[str, float] = {}
        for key, value in step_item.items():
            if not isinstance(key, str):
                raise ValueError(
                    f"greedy_step_reward_overrides[{index}] keys must be strings (rule names)"
                )
            if not isinstance(value, (int, float)):
                raise ValueError(
                    f"greedy_step_reward_overrides[{index}][{key}] must be a number"
                )
            step_map[key] = float(value)
        parsed.append(step_map)
    return parsed


def read_stage1_csv(path: Path) -> list[Stage2InputRow]:
    """Read Stage 1 CSV outputs as Stage 2 inputs."""

    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    parsed: list[Stage2InputRow] = []
    for row in rows:
        query_id = (row.get("query_id") or "").strip()
        original_sql = (row.get("original_sql") or "").strip()
        if not query_id or not original_sql:
            raise ValueError("Stage 1 CSV must contain non-empty query_id and original_sql")
        candidate_rules_raw = row.get("candidate_rules")
        if candidate_rules_raw is None or not candidate_rules_raw.strip():
            candidate_rules_raw = row.get("rule_set") or row.get("ruleset")
        candidate_rules = _parse_rule_list(candidate_rules_raw, "candidate_rules/rule_set")
        llm_recommended_order = _parse_json_list(
            row.get("llm_recommended_order"), "llm_recommended_order"
        )
        parsed.append(
            Stage2InputRow(
                query_id=query_id,
                original_sql=original_sql,
                candidate_rules=candidate_rules,
                llm_recommended_order=llm_recommended_order,
                llm_latency_ms=_parse_optional_float(row.get("llm_latency_ms")),
                greedy_step_reward_overrides=_parse_optional_step_reward_overrides(
                    row.get("greedy_step_reward_overrides")
                ),
            )
        )
    return parsed


def write_stage2_csv(path: Path, rows: list[Stage2ResultRow]) -> None:
    """Write Stage 2 outputs with strict column order."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())
