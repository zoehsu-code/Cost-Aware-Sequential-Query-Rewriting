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
    api_base_url: str = "https://genai.vocareum.com/v1"
    api_key_env_var: str = "VOC_API_KEY"

    def __post_init__(self) -> None:
        if self.max_rules <= 0:
            raise ValueError("max_rules must be a positive integer")
        if not self.llm_model:
            raise ValueError("llm_model must be non-empty")
        if not self.prompt_version:
            raise ValueError("prompt_version must be non-empty")
        if not self.api_base_url:
            raise ValueError("api_base_url must be non-empty")
        if not self.api_key_env_var:
            raise ValueError("api_key_env_var must be non-empty")
