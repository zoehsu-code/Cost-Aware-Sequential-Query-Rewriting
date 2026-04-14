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


def _parse_optional_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    return float(text)


def read_stage1_csv(path: Path) -> list[Stage2InputRow]:
    """Read Stage 1 CSV outputs as Stage 2 inputs."""

    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    parsed: list[Stage2InputRow] = []
    for row in rows:
        query_id = (row.get("query_id") or "").strip()
        original_sql = (row.get("original_sql") or "").strip()
        if not query_id or not original_sql:
            raise ValueError("Stage 1 CSV must contain non-empty query_id and original_sql")
        candidate_rules = _parse_json_list(row.get("candidate_rules"), "candidate_rules")
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
