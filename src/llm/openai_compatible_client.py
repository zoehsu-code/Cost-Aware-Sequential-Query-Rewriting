"""OpenAI-compatible JSON LLM client for Stage 1."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request


class OpenAICompatibleLLMClient:
    """Call an OpenAI-compatible `/chat/completions` endpoint and return parsed JSON."""

    def __init__(self, *, base_url: str, api_key_env_var: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_env_var = api_key_env_var

    def generate_json(self, *, model: str, prompt: str) -> dict[str, Any]:
        api_key = os.getenv(self.api_key_env_var)
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
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=120) as resp:
                response = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM API request failed: {exc.code} {details}") from exc

        content = response["choices"][0]["message"]["content"]
        return json.loads(content)
