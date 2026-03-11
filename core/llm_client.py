"""
BriefMD LLM Client
==================
Multi-provider cloud API client. NO local GPU, NO Ollama.

Provider priority:
  1. Groq  (Llama 3.3 70B) — fastest, best reasoning for extraction
  2. Mistral (mistral-small-latest) — high token budget for RAG Q&A
  3. Google Gemini (gemini-2.0-flash) — emergency fallback

All three are free tier. If one fails, we fall through to the next.
The calling code never knows which provider answered.

Required env vars (set in .env):
  GROQ_API_KEY=gsk_...
  MISTRAL_API_KEY=...
  GOOGLE_API_KEY=...          (for Gemini)

Install:
  pip install groq mistralai google-genai httpx
"""

import json
import logging
import os
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

class _GroqProvider:
    """Groq — Llama 3.3 70B on custom LPU hardware. ~300 tok/s."""

    name = "groq"
    model = "llama-3.3-70b-versatile"

    def __init__(self):
        self.api_key = os.environ.get("GROQ_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
                logger.info("Groq provider initialized")
            except ImportError:
                logger.warning("groq package not installed. pip install groq")

    @property
    def available(self) -> bool:
        return self.client is not None

    def generate(self, prompt: str, system: str = "", temperature: float = 0.1,
                 max_tokens: int = 4096) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            top_p=0.9,
        )
        return response.choices[0].message.content or ""


class _MistralProvider:
    """Mistral — mistral-small-latest. Good JSON mode, high token budget."""

    name = "mistral"
    model = "mistral-small-latest"

    def __init__(self):
        self.api_key = os.environ.get("MISTRAL_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from mistralai import Mistral
                self.client = Mistral(api_key=self.api_key)
                logger.info("Mistral provider initialized")
            except ImportError:
                logger.warning("mistralai package not installed. pip install mistralai")

    @property
    def available(self) -> bool:
        return self.client is not None

    def generate(self, prompt: str, system: str = "", temperature: float = 0.1,
                 max_tokens: int = 4096) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.complete(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""


class _GeminiProvider:
    """Google Gemini 2.0 Flash — emergency fallback. Free tier."""

    name = "gemini"
    model = "gemini-2.0-flash"

    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini provider initialized")
            except ImportError:
                logger.warning("google-genai package not installed. pip install google-genai")

    @property
    def available(self) -> bool:
        return self.client is not None

    def generate(self, prompt: str, system: str = "", temperature: float = 0.1,
                 max_tokens: int = 4096) -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        return response.text or ""


# ---------------------------------------------------------------------------
# Main LLM Client — the only interface the rest of the app uses
# ---------------------------------------------------------------------------

class LLMClient:
    """
    Multi-provider LLM client with automatic fallback.

    Usage:
        llm = LLMClient()
        text = llm.generate("Extract data from this note...")
        data = llm.generate_json("...", system="Return ONLY valid JSON.")
    """

    def __init__(self):
        # Initialize all providers — they silently skip if API key missing
        self._providers = [
            _GroqProvider(),
            _MistralProvider(),
            _GeminiProvider(),
        ]

        available = [p.name for p in self._providers if p.available]
        if not available:
            logger.error(
                "NO LLM providers available. Set at least one of: "
                "GROQ_API_KEY, MISTRAL_API_KEY, GOOGLE_API_KEY"
            )
        else:
            logger.info(f"LLM providers available: {', '.join(available)}")

        self._last_provider: str = ""
        self._call_count: int = 0
        self._total_time: float = 0.0

    @property
    def available_providers(self) -> list[str]:
        return [p.name for p in self._providers if p.available]

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        preferred_provider: Optional[str] = None,
    ) -> str:
        """
        Generate text using the first available provider.

        Args:
            prompt: User message / main prompt.
            system: System message (instructions, persona).
            temperature: 0.0 = deterministic, 1.0 = creative. Default 0.1 for clinical.
            max_tokens: Max response length.
            preferred_provider: Force a specific provider ("groq", "mistral", "gemini").

        Returns:
            Generated text string.

        Raises:
            RuntimeError: If all providers fail.
        """
        providers = self._get_provider_order(preferred_provider)
        errors = []

        for provider in providers:
            if not provider.available:
                continue

            try:
                start = time.perf_counter()
                logger.info(
                    f"LLM call → {provider.name} ({provider.model}), "
                    f"prompt_len={len(prompt)}"
                )

                text = provider.generate(
                    prompt=prompt,
                    system=system or "",
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                elapsed = time.perf_counter() - start
                self._last_provider = provider.name
                self._call_count += 1
                self._total_time += elapsed

                logger.info(
                    f"LLM response ← {provider.name}: "
                    f"len={len(text)}, time={elapsed:.2f}s"
                )
                return text

            except Exception as e:
                elapsed = time.perf_counter() - start
                logger.warning(
                    f"LLM provider {provider.name} failed after {elapsed:.1f}s: {e}"
                )
                errors.append(f"{provider.name}: {e}")
                continue

        error_msg = "All LLM providers failed:\n" + "\n".join(errors)
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        preferred_provider: Optional[str] = None,
    ) -> dict | list | None:
        """
        Generate and parse JSON response. Handles markdown fences,
        malformed output, and retry on parse failure.

        Returns:
            Parsed JSON (dict or list), or None if parsing fails.
        """
        # First attempt
        raw = self.generate(
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            preferred_provider=preferred_provider,
        )

        parsed = self._parse_json(raw)
        if parsed is not None:
            return parsed

        # Retry once with explicit instruction
        logger.warning("JSON parse failed on first attempt. Retrying with stricter prompt.")
        retry_prompt = (
            "Your previous response was not valid JSON. "
            "Please return ONLY a valid JSON object. No markdown, no explanation, "
            "no text before or after the JSON.\n\n"
            f"Original request:\n{prompt}"
        )

        raw_retry = self.generate(
            prompt=retry_prompt,
            system=(system or "") + "\nReturn ONLY valid JSON. No markdown fences.",
            temperature=0.0,  # Deterministic for retry
            max_tokens=max_tokens,
            preferred_provider=preferred_provider,
        )

        parsed_retry = self._parse_json(raw_retry)
        if parsed_retry is not None:
            return parsed_retry

        logger.error(f"JSON parse failed after retry. Raw: {raw_retry[:500]}")
        return None

    def health_check(self) -> dict[str, str]:
        """
        Test each provider with a minimal call.
        Returns status for each: "ok", "no_key", or error message.
        """
        results = {}
        for provider in self._providers:
            if not provider.available:
                results[provider.name] = "no_api_key"
                continue
            try:
                response = provider.generate(
                    prompt="Reply with exactly: ok",
                    system="Reply with exactly one word: ok",
                    temperature=0.0,
                    max_tokens=10,
                )
                results[provider.name] = "ok" if "ok" in response.lower() else f"unexpected: {response[:50]}"
            except Exception as e:
                results[provider.name] = f"error: {e}"
        return results

    @property
    def stats(self) -> dict:
        return {
            "total_calls": self._call_count,
            "total_time": round(self._total_time, 2),
            "avg_time": round(self._total_time / max(self._call_count, 1), 2),
            "last_provider": self._last_provider,
            "available_providers": self.available_providers,
        }

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _get_provider_order(self, preferred: Optional[str]) -> list:
        """Return providers in priority order, with preferred first if specified."""
        if preferred:
            preferred_lower = preferred.lower()
            reordered = [p for p in self._providers if p.name == preferred_lower]
            reordered += [p for p in self._providers if p.name != preferred_lower]
            return reordered
        return self._providers

    @staticmethod
    def _parse_json(raw: str) -> dict | list | None:
        """Parse JSON from LLM output. Handles markdown fences and whitespace."""
        if not raw:
            return None

        # Strip markdown fences
        cleaned = re.sub(r"```(?:json)?\s*", "", raw)
        cleaned = re.sub(r"```\s*$", "", cleaned)
        cleaned = cleaned.strip()

        # Try direct parse
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            pass

        # Extract first JSON object or array
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
        if match:
            try:
                return json.loads(match.group(1))
            except (json.JSONDecodeError, TypeError):
                pass

        return None