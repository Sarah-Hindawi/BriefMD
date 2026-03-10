import json
import logging
import re

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Mistral 7B Instruct via Ollama. Only LLM interface in the project."""

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
    ) -> None:
        self.host = host or settings.ollama_host
        self.model = model or settings.ollama_model
        self._url = f"{self.host}/api/generate"

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        temperature = temperature if temperature is not None else settings.llm_temperature
        max_tokens = max_tokens or settings.llm_max_tokens

        full_prompt = f"[INST] {system}\n\n{prompt} [/INST]" if system else f"[INST] {prompt} [/INST]"

        logger.info(f"LLM request: model={self.model}, temp={temperature}, prompt_len={len(full_prompt)}")

        response = httpx.post(
            self._url,
            json={
                "model": self.model,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "top_p": 0.9,
                },
            },
            timeout=120.0,
        )
        response.raise_for_status()

        text = response.json().get("response", "")
        logger.info(f"LLM response: len={len(text)}")
        return text

    def generate_json(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float | None = None,
    ) -> dict | list | None:
        raw = self.generate(prompt, system=system, temperature=temperature)

        # Strip markdown fences Mistral likes to add
        cleaned = re.sub(r"```(?:json)?\s*", "", raw)
        cleaned = cleaned.strip()

        # Try direct parse first
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            pass

        # Regex fallback: extract first JSON object or array
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
        if match:
            try:
                return json.loads(match.group(1))
            except (json.JSONDecodeError, TypeError):
                pass

        logger.warning(f"LLM JSON parse failed. Raw response: {raw[:500]}")
        return None
