from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MedicationItem(BaseModel):
    name: str
    dose: str = ""
    route: str = ""
    frequency: str = ""
    is_new: bool = False
    is_changed: bool = False
    is_stopped: bool = False
    change_reason: str = ""


class FollowUpItem(BaseModel):
    provider: str = ""
    specialty: str = ""
    timeframe: str = ""
    reason: str = ""


class PendingTest(BaseModel):
    test_name: str
    reason: str = ""


class ExtractedData(BaseModel):
    """Step 1 output: structured data extracted from discharge summary by LLM."""

    chief_complaint: str = ""
    admission_diagnosis: str = ""
    discharge_diagnosis: str = ""

    past_medical_history: list[str] = Field(default_factory=list)
    family_history: str = ""
    social_history: str = ""

    diagnoses_mentioned: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)

    medications_discharge: list[MedicationItem] = Field(default_factory=list)
    medications_stopped: list[MedicationItem] = Field(default_factory=list)

    lab_results_discussed: list[str] = Field(default_factory=list)
    pending_tests: list[PendingTest] = Field(default_factory=list)

    follow_up_plan: list[FollowUpItem] = Field(default_factory=list)
    pcp_name: str = ""

    discharge_instructions: str = ""
    clinical_assessment: str = ""

    @classmethod
    def from_regex_fallback(cls, raw: str) -> ExtractedData:
        """Best-effort extraction when LLM returns malformed JSON."""
        logger.warning("Using regex fallback for extraction")

        def find_list(pattern: str) -> list[str]:
            match = re.search(pattern, raw, re.IGNORECASE)
            if not match:
                return []
            return [s.strip().strip('"\'') for s in match.group(1).split(",") if s.strip()]

        return cls(
            chief_complaint=_extract_field(raw, "chief_complaint"),
            admission_diagnosis=_extract_field(raw, "admission_diagnosis"),
            discharge_diagnosis=_extract_field(raw, "discharge_diagnosis"),
            diagnoses_mentioned=find_list(r"diagnoses_mentioned[\"']?\s*:\s*\[(.*?)\]"),
            allergies=find_list(r"allergies[\"']?\s*:\s*\[(.*?)\]"),
            discharge_instructions=_extract_field(raw, "discharge_instructions"),
        )


def _extract_field(raw: str, field: str) -> str:
    match = re.search(rf'"{field}"\s*:\s*"(.*?)"', raw, re.IGNORECASE)
    return match.group(1) if match else ""
