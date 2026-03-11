"""
Verification Flags
==================
Output of core/verifier.py. Each flag represents something the verifier
found by comparing extracted data against the patient's actual record.
"""

from pydantic import BaseModel, Field
from typing import Optional


class VerificationFlag(BaseModel):
    """A single issue found during verification."""
    severity: str = Field(description="'critical', 'warning', 'info', 'monitor'")
    category: str = Field(description="'medication', 'diagnosis', 'lab', 'documentation', 'follow_up'")
    title: str
    detail: str
    evidence: Optional[str] = Field(
        default=None,
        description="Structured data that proves this flag (e.g., ICD-9 code, lab value)"
    )
    suggested_action: Optional[str] = None


class VerificationResult(BaseModel):
    """Complete output of the verification step."""
    flags: list[VerificationFlag] = Field(default_factory=list)

    # Diagnosis comparison
    diagnoses_in_note: int = 0
    diagnoses_in_record: int = 0
    diagnoses_missed: list[str] = Field(default_factory=list)
    diagnoses_matched: list[str] = Field(default_factory=list)

    # Medication comparison
    medications_in_note: int = 0
    medications_in_record: int = 0
    medication_issues: list[VerificationFlag] = Field(default_factory=list)

    # Lab comparison
    labs_in_note: int = 0
    labs_in_record: int = 0
    abnormal_labs: int = 0
    critical_labs_missed: list[str] = Field(
        default_factory=list,
        description="Critical/abnormal lab values not mentioned in the note"
    )

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.flags if f.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.flags if f.severity == "warning")

    @property
    def total_flags(self) -> int:
        return len(self.flags)