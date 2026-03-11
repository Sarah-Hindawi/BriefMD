"""
ED Schemas — Side A: Quality Gate
=================================
Request/response models for the ED doctor's quality check workflow.

The ED doctor writes a discharge note → BriefMD checks it BEFORE it leaves.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional

from api.schemas.shared import (
    Flag,
    ExtractedData,
    ComorbidityNetwork,
    HQOChecklistResult,
    AnalysisMetadata,
)


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
class EDAnalysisRequest(BaseModel):
    """What the ED dashboard sends to trigger a quality gate check."""
    hadm_id: int = Field(description="Hospital admission ID to load patient context")
    discharge_note: Optional[str] = Field(
        default=None,
        description=(
            "The discharge note text to analyze. "
            "If omitted, loads the existing discharge_summary from the dataset."
        ),
    )

    class Config:
        json_schema_extra = {
            "example": {
                "hadm_id": 100006,
                "discharge_note": None,  # Will load from dataset
            }
        }


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class EDAnalysisResponse(BaseModel):
    """
    Full quality gate report for the ED doctor.

    Sections map to what the ED doctor sees:
    1. Flags — what's wrong or missing
    2. Extracted vs Actual — what the note says vs what the data shows
    3. HQO Checklist — compliance with Ontario Safe Discharge Practices
    4. Comorbidity Network — how conditions interact
    5. Suggestions — what to fix before sending
    """
    # Metadata
    metadata: AnalysisMetadata

    # What the LLM extracted from the note
    extracted: ExtractedData

    # Verification results
    flags: list[Flag] = Field(default_factory=list)

    # Breakdown by category
    diagnoses_in_note: int = Field(description="How many diagnoses the note mentions")
    diagnoses_in_record: int = Field(description="How many coded diagnoses exist")
    diagnoses_missed: list[str] = Field(
        default_factory=list,
        description="Diagnoses in the record but NOT mentioned in the note"
    )

    medications_in_note: int = 0
    medications_in_record: int = 0
    medication_issues: list[Flag] = Field(
        default_factory=list,
        description="Contraindications, interactions, or missing meds"
    )

    labs_referenced_in_note: int = 0
    labs_in_record: int = 0
    critical_labs_missed: list[str] = Field(
        default_factory=list,
        description="Critical/abnormal lab values not mentioned in the note"
    )

    # HQO compliance
    hqo_checklist: HQOChecklistResult

    # Comorbidity network
    comorbidity_network: ComorbidityNetwork

    # Actionable suggestions for the ED doctor
    suggestions: list[EDSuggestion] = Field(default_factory=list)


class EDSuggestion(BaseModel):
    """A specific fix the ED doctor should make before sending the note."""
    priority: int = Field(description="1 = must fix, 2 = should fix, 3 = nice to have")
    category: str
    message: str
    auto_fixable: bool = Field(
        default=False,
        description="Whether BriefMD can suggest exact text to add"
    )
    suggested_text: Optional[str] = Field(
        default=None,
        description="If auto_fixable, the text to insert"
    )


# Rebuild for forward refs
EDAnalysisResponse.model_rebuild()