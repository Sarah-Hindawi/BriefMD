import logging

from pydantic import ValidationError

from core.llm_client import LLMClient
from core.models.extracted import ExtractedData
from core.prompts.extract_prompt import EXTRACT_PROMPT, EXTRACT_SYSTEM

logger = logging.getLogger(__name__)


class Extractor:
    """Step 1: LLM reads discharge summary → structured ExtractedData."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    def extract(self, note_text: str) -> ExtractedData:
        prompt = EXTRACT_PROMPT.format(note_text=note_text)

        data = self.llm.generate_json(
            prompt,
            system=EXTRACT_SYSTEM,
            temperature=0.1,
        )

        if data is None:
            logger.warning("generate_json returned None, using regex fallback")
            raw = self.llm.generate(prompt, system=EXTRACT_SYSTEM, temperature=0.1)
            return ExtractedData.from_regex_fallback(raw)

        try:
            return ExtractedData(**data)
        except (ValidationError, TypeError) as e:
            logger.warning(f"Pydantic validation failed: {e}, using regex fallback")
            raw = str(data)
            return ExtractedData.from_regex_fallback(raw)
