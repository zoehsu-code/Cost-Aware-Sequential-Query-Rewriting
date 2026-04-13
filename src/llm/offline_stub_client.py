"""Offline stub client for Stage 1 testing without external AI APIs."""

from __future__ import annotations

import re
from typing import Any


class OfflineStubLLMClient:
    """Deterministic Stage 1 JSON generator derived from prompt contents."""

    _QUERY_ID_RE = re.compile(r"^query_id:\s*(.+)$", re.MULTILINE)
    _ORIGINAL_SQL_RE = re.compile(r"^original_sql:\s*(.+)$", re.MULTILINE)
    _MAX_RULES_RE = re.compile(r"^max_rules:\s*(\d+)$", re.MULTILINE)
    _INCLUDE_EMPTY_RE = re.compile(r"^include_empty:\s*(enabled|disabled)$", re.MULTILINE)
    _RULE_LINE_RE = re.compile(r"^- ([A-Z0-9_]+)(?::.*)?$", re.MULTILINE)

    def generate_json(self, *, model: str, prompt: str) -> dict[str, Any]:
        del model  # Unused in offline mode, kept for protocol compatibility.

        query_id = self._extract(self._QUERY_ID_RE, prompt, "query_id")
        original_sql = self._extract(self._ORIGINAL_SQL_RE, prompt, "original_sql")
        max_rules = int(self._extract(self._MAX_RULES_RE, prompt, "max_rules"))
        include_empty = self._extract(self._INCLUDE_EMPTY_RE, prompt, "include_empty") == "enabled"

        parsed_rules = [rule for rule in self._RULE_LINE_RE.findall(prompt) if rule != "EMPTY"]
        deduped_rules: list[str] = []
        seen: set[str] = set()
        for rule in parsed_rules:
            if rule in seen:
                continue
            seen.add(rule)
            deduped_rules.append(rule)

        candidate_rules: list[str] = deduped_rules[:max_rules]
        if include_empty:
            non_empty_budget = max(max_rules - 1, 0)
            candidate_rules = deduped_rules[:non_empty_budget]
            if max_rules > 0:
                candidate_rules.append("EMPTY")

        return {
            "query_id": query_id,
            "original_sql": original_sql,
            "candidate_pool_size": max_rules,
            "candidate_rules": candidate_rules,
            "llm_recommended_order": list(candidate_rules),
        }

    @staticmethod
    def _extract(pattern: re.Pattern[str], text: str, field_name: str) -> str:
        match = pattern.search(text)
        if not match:
            raise ValueError(f"OfflineStubLLMClient failed to parse '{field_name}' from prompt")
        return match.group(1).strip()

