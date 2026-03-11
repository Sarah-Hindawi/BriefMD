"""
PCP Schemas — Side B: Verified Report
======================================
Request/response models for the Primary Care Physician's post-discharge workflow.

The PCP receives the discharge note → BriefMD verifies, contextualizes, and
produces an actionable structured report.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional

from api.schemas.shared import (
    Flag,
    FlagSeverity,
    ExtractedData,
    ComorbidityNetwork,
    HQOChecklistResult,
    AnalysisMetadata,
)


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
class PCPReportRequest(BaseModel):
    """What the PCP dashboard sends to generate a verified report."""
    hadm_id: int = Field(description="Hospital admission ID")
    discharge_note: Optional[str] = Field(
        default=None,
        description="Discharge note text. If omitted, loads from dataset."
    )
    # PCP-specific options
    include_todo: bool = Field(
        default=True,
        description="Generate actionable to-do list for follow-up"
    )
    include_monitoring_plan: bool = Field(
        default=True,
        description="Generate a monitoring plan based on comorbidities"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "hadm_id": 100006,
                "include_todo": True,
                "include_monitoring_plan": True,
            }
        }


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class PCPReportResponse(BaseModel):
    """
    Full verified report for the PCP.

    Sections:
    1. Priority Alerts — what needs immediate attention
    2. Structured Summary — verified extracted data
    3. Gaps & Flags — what's missing or concerning
    4. To-Do List — actionable follow-up items
    5. Comorbidity Network — condition interactions
    6. Monitoring Plan — what to track going forward
    """
    metadata: AnalysisMetadata

    # Patient one-liner for quick orientation
    patient_summary: str = Field(
        description=(
            "One-paragraph summary: age, gender, why admitted, "
            "what happened, key diagnoses, discharge disposition"
        )
    )

    # Priority alerts (critical flags only, shown at top)
    priority_alerts: list[Flag] = Field(
        default_factory=list,
        description="Critical and warning flags the PCP must see first"
    )

    # Full extracted + verified data
    extracted: ExtractedData

    # All flags (including non-critical)
    all_flags: list[Flag] = Field(default_factory=list)

    # Flag summary counts
    flag_counts: FlagCounts

    # Gaps in documentation
    documentation_gaps: list[str] = Field(
        default_factory=list,
        description="Information the PCP would expect but isn't in the note"
    )

    # Actionable to-do list
    todo_items: list[TodoItem] = Field(default_factory=list)

    # HQO checklist (how well the ED note meets Ontario standards)
    hqo_checklist: HQOChecklistResult

    # Comorbidity network
    comorbidity_network: ComorbidityNetwork

    # Monitoring plan
    monitoring_plan: list[MonitoringItem] = Field(default_factory=list)


class FlagCounts(BaseModel):
    critical: int = 0
    warning: int = 0
    monitor: int = 0
    info: int = 0
    total: int = 0


class TodoItem(BaseModel):
    """A specific action the PCP should take post-discharge."""
    id: str
    priority: int = Field(description="1 = urgent, 2 = soon, 3 = routine")
    category: str = Field(description="'medication_review', 'lab_follow_up', 'referral', 'appointment', 'monitoring'")
    task: str = Field(description="Human-readable task description")
    timeframe: Optional[str] = Field(
        default=None,
        description="When this should be done, e.g. 'within 48 hours', 'within 1 week'"
    )
    rationale: Optional[str] = Field(
        default=None,
        description="Why this task matters — RAG-retrieved guideline context"
    )
    completed: bool = False


class MonitoringItem(BaseModel):
    """Something the PCP should track over time for this patient."""
    condition: str
    what_to_monitor: str
    frequency: str = Field(description="e.g. 'weekly for 4 weeks', 'at next visit'")
    red_flags: list[str] = Field(
        default_factory=list,
        description="Symptoms that should trigger escalation"
    )
    related_diagnoses: list[str] = Field(default_factory=list)


# Rebuild for forward refs
PCPReportResponse.model_rebuild()