"""
PCP Router — Side B: Verified Report
=====================================
The PCP's workflow:
  1. GET  /api/v1/patients/{hadm_id}   → See patient context (in patients.py)
  2. POST /api/v1/pcp/report           → Get verified report with flags + to-do
  3. POST /api/v1/chat/ask             → Ask follow-up questions (in chat.py)


"""

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from api.dependencies import get_agent, get_bundle
from api.schemas.pcp_request import PCPReportRequest
from data.patient_context import get_patient_context

router = APIRouter()


class PCPSummaryRequest(BaseModel):
    hadm_id: int = Field(description="Hospital admission ID")


class PCPSummaryResponse(BaseModel):
    hadm_id: int
    pcp_summary: str = Field(description="LLM-generated 5-bullet summary for the receiving PCP")


@router.post("/report")
async def report(request: PCPReportRequest):
    """Full verified report: flags + gaps + network + actionable to-do list + PCP summary."""
    bundle = get_bundle()
    agent = get_agent()

    try:
        ctx = get_patient_context(request.hadm_id, bundle)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    report = agent.run_pcp_report(
        note_text=ctx.discharge_summary,
        patient_diagnoses=ctx.diagnoses,
        patient_labs=ctx.labs,
        patient_prescriptions=ctx.prescriptions,
        subject_id=ctx.subject_id,
        hadm_id=ctx.hadm_id,
    )

    return report.model_dump()


@router.post("/summarize", response_model=PCPSummaryResponse)
async def summarize(request: PCPSummaryRequest):
    """Generate a 5-bullet PCP-facing summary from the discharge note.

    Runs extraction then summarization (2 LLM calls).
    Lighter than /report — no verification, no network, no checklist.
    """
    bundle = get_bundle()
    agent = get_agent()

    try:
        ctx = get_patient_context(request.hadm_id, bundle)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    extracted = agent.extractor.extract(ctx.discharge_summary)
    summary = agent.extractor.summarize_for_pcp(extracted)

    return PCPSummaryResponse(hadm_id=request.hadm_id, pcp_summary=summary)


