from __future__ import annotations

from pydantic import BaseModel, Field

from core.models.extracted import ExtractedData
from core.models.flags import VerificationResult
from core.models.network import ComorbidityNetwork


class ChecklistItem(BaseModel):
    id: str
    label: str
    passed: bool
    detail: str = ""


class TodoItem(BaseModel):
    priority: int = 1
    action: str
    reason: str = ""
    category: str = ""  # e.g. "lab", "referral", "medication"


class FullReport(BaseModel):
    """Complete pipeline output before splitting into ED/PCP views."""

    subject_id: int
    hadm_id: int
    extracted: ExtractedData
    flags: VerificationResult
    network: ComorbidityNetwork
    hqo_checklist: list[ChecklistItem] = Field(default_factory=list)
    pcp_preferences: list[ChecklistItem] = Field(default_factory=list)


class EDReport(BaseModel):
    """Side A — ED doctor quality gate."""

    subject_id: int
    hadm_id: int
    extracted: ExtractedData
    flags: VerificationResult
    network: ComorbidityNetwork
    hqo_checklist: list[ChecklistItem] = Field(default_factory=list)
    fix_suggestions: list[str] = Field(default_factory=list)


class PCPReport(BaseModel):
    """Side B — PCP verified report."""

    subject_id: int
    hadm_id: int
    pcp_summary: str = Field(default="", description="LLM-generated 5-bullet summary for the receiving PCP")
    extracted: ExtractedData
    flags: VerificationResult
    network: ComorbidityNetwork
    hqo_checklist: list[ChecklistItem] = Field(default_factory=list)
    todo_list: list[TodoItem] = Field(default_factory=list)
