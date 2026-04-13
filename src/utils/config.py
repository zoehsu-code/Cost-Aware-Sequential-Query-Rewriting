"""Configuration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Stage1Config:
    """Configuration for Stage 1 candidate-rule generation."""

    max_rules: int
    include_empty: bool = True
    llm_model: str = "gpt-4.1-mini"
    prompt_version: str = "v1"
    output_dir: Path = Path("outputs/stage1")
    save_csv: bool = True

    def __post_init__(self) -> None:
        if self.max_rules <= 0:
            raise ValueError("max_rules must be a positive integer")
        if not self.llm_model:
            raise ValueError("llm_model must be non-empty")
        if not self.prompt_version:
            raise ValueError("prompt_version must be non-empty")
