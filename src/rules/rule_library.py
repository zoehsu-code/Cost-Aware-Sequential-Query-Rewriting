"""Rule library helpers for rewrite actions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_STANDARD_RULE_LIBRARY_PATH = Path("rule_library/standard.txt")


@dataclass(frozen=True)
class CalciteRule:
    """One Apache Calcite rewrite rule and its short description."""

    name: str
    description: str = ""


def normalize_rule_library(rules: Iterable[CalciteRule]) -> list[CalciteRule]:
    """Return a list of validated unique rules preserving input order."""

    normalized: list[CalciteRule] = []
    seen: set[str] = set()
    for rule in rules:
        name = rule.name.strip()
        if not name:
            raise ValueError("Rule name must be non-empty")
        if name == "EMPTY":
            raise ValueError("Rule library must not contain reserved name 'EMPTY'")
        if name in seen:
            raise ValueError(f"Duplicate rule in library: {name}")
        seen.add(name)
        normalized.append(CalciteRule(name=name, description=rule.description.strip()))
    return normalized


def rule_names(rules: Iterable[CalciteRule]) -> set[str]:
    """Return the set of allowed rule names."""

    return {rule.name for rule in rules}


def render_rule_library_for_prompt(rules: Iterable[CalciteRule]) -> str:
    """Render rules into a compact prompt-friendly list."""

    lines: list[str] = []
    for rule in rules:
        if rule.description:
            lines.append(f"- {rule.name}: {rule.description}")
        else:
            lines.append(f"- {rule.name}")
    return "\n".join(lines)


def load_standard_rule_library(path: Path = DEFAULT_STANDARD_RULE_LIBRARY_PATH) -> list[CalciteRule]:
    """Load centralized Calcite rule names from `rule_library/standard.txt`."""

    if not path.exists():
        raise FileNotFoundError(f"Rule library file not found: {path}")

    parsed_rules: list[CalciteRule] = []
    seen: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("rule_"):
            continue
        if line in seen:
            continue
        seen.add(line)
        parsed_rules.append(CalciteRule(name=line))

    return normalize_rule_library(parsed_rules)
