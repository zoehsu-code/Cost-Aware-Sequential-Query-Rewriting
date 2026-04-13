"""OpenAI-compatible JSON LLM client for Stage 1."""

from __future__ import annotations

import json
import os
from typing import Any


class OpenAICompatibleLLMClient:
    """Call an OpenAI-compatible `/chat/completions` endpoint and return parsed JSON."""

    def __init__(self, *, base_url: str, api_key_env_var: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_env_var = api_key_env_var
        self.api_key = api_key

    def generate_json(self, *, model: str, prompt: str) -> dict[str, Any]:
        import requests

        api_key = self.api_key or os.getenv(self.api_key_env_var)
        if not api_key:
            raise ValueError(
                f"Missing API key in environment variable: {self.api_key_env_var}"
            )

        payload = {
            "model": model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You must return valid JSON only."},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                },
                timeout=120,
            )
            resp.raise_for_status()
            response = resp.json()
        except requests.HTTPError as exc:
            details = exc.response.text if exc.response is not None else str(exc)
            raise RuntimeError(f"LLM API request failed: {details}") from exc

        content = response["choices"][0]["message"]["content"]
        return json.loads(content)
