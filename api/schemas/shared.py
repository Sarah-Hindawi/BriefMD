"""
BriefMD Shared Schemas
======================
Base models used across ED and PCP endpoints.


"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class AnalysisMode(str, Enum):
    ED = "ed"          # Side A — quality gate before note leaves
    PCP = "pcp"        # Side B — verified report for receiving clinician


class FlagSeverity(str, Enum):
    CRITICAL = "critical"   # Red — immediate safety risk (e.g. contraindication)
    WARNING = "warning"     # Yellow — missing info or partial mismatch
    INFO = "info"           # Blue — informational, no action required
    MONITOR = "monitor"     # Orange — PCP should watch this


class VerificationStatus(str, Enum):
    VERIFIED = "verified"       # Matches structured data
    MISMATCH = "mismatch"       # Contradicts structured data
    MISSING = "missing"         # Not found in structured data
    UNVERIFIABLE = "unverifiable"  # Insufficient data to check


# ---------------------------------------------------------------------------
# Core data building blocks
# ---------------------------------------------------------------------------
class PatientSummary(BaseModel):
    """Lightweight patient info for lists and selectors."""
    subject_id: int
    hadm_id: int
    age: Optional[int] = None
    gender: Optional[str] = None
    admission_diagnosis: Optional[str] = None


class PatientContext(BaseModel):
    """Full patient context assembled from the 6 dataset tables."""
    subject_id: int
    hadm_id: int
    age: Optional[int] = None
    gender: Optional[str] = None
    admission_diagnosis: Optional[str] = None
    discharge_summary: Optional[str] = None

    # Structured data from CSV tables
    diagnoses: list[DiagnosisItem] = Field(default_factory=list)
    medications: list[MedicationItem] = Field(default_factory=list)
    labs: list[LabItem] = Field(default_factory=list)

class PatientDetail(BaseModel):
    subject_id: int
    hadm_id: int
    age: int = 0
    gender: str = ""
    admission_diagnosis: str = ""
    discharge_summary: str = ""
    diagnosis_count: int = 0
    lab_count: int = 0
    prescription_count: int = 0


class DiagnosisItem(BaseModel):
    seq_num: int
    icd9_code: str
    short_title: str
    long_title: Optional[str] = None


class MedicationItem(BaseModel):
    drug: str
    dose_value: Optional[str] = None
    dose_unit: Optional[str] = None
    route: Optional[str] = None
    startdate: Optional[str] = None
    enddate: Optional[str] = None


class LabItem(BaseModel):
    itemid: int
    lab_name: str
    charttime: str
    value: Optional[str] = None
    unit: Optional[str] = None
    category: Optional[str] = None


# Rebuild PatientContext so forward refs to DiagnosisItem etc. resolve
PatientContext.model_rebuild()


# ---------------------------------------------------------------------------
# Flag (used by both ED and PCP)
# ---------------------------------------------------------------------------
class Flag(BaseModel):
    """A single clinical flag raised by the pipeline."""
    id: str = Field(description="Unique flag ID, e.g. 'flag_med_contraindication_01'")
    severity: FlagSeverity
    category: str = Field(description="Category: 'medication', 'diagnosis', 'lab', 'documentation', 'follow_up'")
    title: str = Field(description="Short human-readable title")
    detail: str = Field(description="Explanation of the flag")
    evidence: Optional[str] = Field(
        default=None,
        description="Source evidence — structured data or guideline reference"
    )
    guideline_ref: Optional[str] = Field(
        default=None,
        description="RAG-retrieved guideline context explaining why this matters"
    )
    suggested_action: Optional[str] = Field(
        default=None,
        description="What the clinician should do about this flag"
    )


# ---------------------------------------------------------------------------
# Extracted data (what the LLM pulled from the discharge note)
# ---------------------------------------------------------------------------
class ExtractedDiagnosis(BaseModel):
    name: str
    icd9_code: Optional[str] = None
    status: VerificationStatus = VerificationStatus.UNVERIFIABLE


class ExtractedMedication(BaseModel):
    name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    status: VerificationStatus = VerificationStatus.UNVERIFIABLE


class ExtractedData(BaseModel):
    """Structured data extracted from the discharge note by the LLM."""
    diagnoses_mentioned: list[ExtractedDiagnosis] = Field(default_factory=list)
    medications_mentioned: list[ExtractedMedication] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    procedures: list[str] = Field(default_factory=list)
    follow_up_plan: Optional[str] = None
    follow_up_date: Optional[str] = None
    code_status: Optional[str] = None
    discharge_disposition: Optional[str] = None
    labs_referenced: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Comorbidity network
# ---------------------------------------------------------------------------
class ComorbidityNode(BaseModel):
    id: str
    label: str
    icd9_code: Optional[str] = None
    is_patient_condition: bool = True  # vs. connected but not diagnosed


class ComorbidityEdge(BaseModel):
    source: str
    target: str
    weight: float = Field(description="Co-occurrence frequency in dataset")
    is_dangerous: bool = False
    reason: Optional[str] = None  # Why this pair is dangerous


class ComorbidityNetwork(BaseModel):
    nodes: list[ComorbidityNode] = Field(default_factory=list)
    edges: list[ComorbidityEdge] = Field(default_factory=list)
    clusters: list[list[str]] = Field(
        default_factory=list,
        description="Groups of related conditions"
    )


# ---------------------------------------------------------------------------
# HQO Checklist (Ontario Safe Discharge Practices)
# ---------------------------------------------------------------------------
class ChecklistItem(BaseModel):
    id: str
    requirement: str
    met: bool
    detail: Optional[str] = Field(
        default=None,
        description="Evidence from the note, or explanation of why unmet"
    )


class HQOChecklistResult(BaseModel):
    items: list[ChecklistItem] = Field(default_factory=list)
    score: int = Field(description="Number of items met")
    total: int = Field(description="Total checklist items")
    compliance_pct: float = Field(description="score / total as percentage")


# ---------------------------------------------------------------------------
# Timestamps and metadata
# ---------------------------------------------------------------------------
class AnalysisMetadata(BaseModel):
    analysis_id: str
    mode: AnalysisMode
    timestamp: datetime
    model_used: str
    processing_time_seconds: float
    llm_calls_made: int
