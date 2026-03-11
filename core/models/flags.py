from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    RED = "red"          # Dangerous — must fix before discharge
    ORANGE = "orange"    # Drug interaction or contraindication
    YELLOW = "yellow"    # Missing info — should fix


class Flag(BaseModel):
    severity: Severity
    category: str
    summary: str
    detail: str = ""


class Contraindication(BaseModel):
    drug: str
    condition: str
    icd9: str = ""
    severity_label: str = ""  # e.g. "FDA black box", "contraindicated"
    detail: str = ""


class DrugInteraction(BaseModel):
    drug_a: str
    drug_b: str
    severity_label: str = ""
    detail: str = ""


class DiagnosisGap(BaseModel):
    icd9_code: str
    diagnosis: str
    mentioned_in_note: bool = False


class VerificationFlags(BaseModel):
    """Step 2 output: cross-referencing extracted data vs structured tables."""

    contraindications: list[Contraindication] = Field(default_factory=list)
    drug_interactions: list[DrugInteraction] = Field(default_factory=list)
    diagnosis_gaps: list[DiagnosisGap] = Field(default_factory=list)
    lab_gaps: list[str] = Field(default_factory=list)
    flags: list[Flag] = Field(default_factory=list)

    @property
    def red_flags(self) -> list[Flag]:
        return [f for f in self.flags if f.severity == Severity.RED]

    @property
    def orange_flags(self) -> list[Flag]:
        return [f for f in self.flags if f.severity == Severity.ORANGE]

    @property
    def yellow_flags(self) -> list[Flag]:
        return [f for f in self.flags if f.severity == Severity.YELLOW]

    @property
    def has_critical(self) -> bool:
        return len(self.contraindications) > 0 or len(self.red_flags) > 0
