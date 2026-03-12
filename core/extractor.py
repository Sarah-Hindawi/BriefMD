import logging

from pydantic import ValidationError

from core.llm_client import LLMClient
from core.models.extracted import ExtractedData
from core.prompts.extract_prompt import EXTRACT_PROMPT, EXTRACT_SYSTEM, SUMMARIZE_PROMPT, SUMMARIZE_SYSTEM

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

    def summarize_for_pcp(self, extracted: ExtractedData) -> str:
        """Step 1B: Generate 5-bullet summary for receiving clinician.

        Runs AFTER extraction. Uses extracted data to keep the prompt
        short — no need to resend the full discharge note.
        """
        meds = [m.name for m in extracted.medications_discharge[:10]] if extracted.medications_discharge else []
        follow_ups = [
            f"{f.provider} ({f.specialty})" if f.specialty else f.provider
            for f in extracted.follow_up_plan[:5]
        ] if extracted.follow_up_plan else ["none documented"]

        # Detect missing sections
        missing = []
        if not extracted.allergies:
            missing.append("allergies")
        if not extracted.follow_up_plan:
            missing.append("follow-up plan")
        if not extracted.discharge_instructions:
            missing.append("discharge instructions")
        if not extracted.lab_results_discussed:
            missing.append("lab results")

        prompt = SUMMARIZE_PROMPT.format(
            chief_complaint=extracted.chief_complaint or "unknown",
            diagnoses=", ".join(extracted.diagnoses_mentioned[:10]) if extracted.diagnoses_mentioned else "none extracted",
            medications=", ".join(meds) if meds else "none extracted",
            allergies=", ".join(extracted.allergies) if extracted.allergies else "none documented",
            follow_up="; ".join(follow_ups),
            missing=", ".join(missing) if missing else "none",
        )
        return self.llm.generate(prompt, system=SUMMARIZE_SYSTEM, temperature=0.3)
