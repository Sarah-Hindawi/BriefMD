"""
ED Router — Side A: Quality Gate
=================================
The ED doctor's workflow:
  1. GET  /summaries          → Browse available cases
  2. GET  /summaries/{hadm_id} → Read the note + see record counts
  3. POST /analyze            → Run full quality gate pipeline
  4. POST /checklist          → Quick HQO-only check (no full pipeline)
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.dependencies import get_agent, get_bundle
from api.schemas.ed_request import EDAnalysisRequest
from knowledge.hqo_checklist import run_hqo_checklist
from data.patient_context import get_patient_context

router = APIRouter()


@router.post("/analyze")
async def analyze(request: EDAnalysisRequest):
    """Full pipeline: extraction + verification + HQO checklist + fix suggestions."""
    bundle = get_bundle()
    agent = get_agent()

    try:
        ctx = get_patient_context(request.hadm_id, bundle)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    note_text = request.discharge_note or ctx.discharge_summary

    report = agent.run_ed_check(
        note_text=note_text,
        patient_diagnoses=ctx.diagnoses,
        patient_labs=ctx.labs,
        patient_prescriptions=ctx.prescriptions,
        subject_id=ctx.subject_id,
        hadm_id=ctx.hadm_id,
    )

    return report.model_dump()


@router.post("/checklist")
async def checklist(request: EDAnalysisRequest):
    """Just HQO checklist compliance (9 items, pass/fail). No full pipeline."""
    bundle = get_bundle()
    agent = get_agent()

    try:
        ctx = get_patient_context(request.hadm_id, bundle)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    note_text = request.discharge_note or ctx.discharge_summary

    extracted = agent.extractor.extract(note_text)
    items = run_hqo_checklist(extracted, note_text)

    return {
        "patient_id": request.hadm_id,
        "items": [item.model_dump() for item in items],
        "passed": sum(1 for item in items if item.passed),
        "total": len(items),
    }
# ---------------------------------------------------------------------------
# GET endpoints — View BEFORE you analyze
# ---------------------------------------------------------------------------
# WHY: Your original ed.py jumped straight to POST /analyze.
# The ED doctor needs to SEE the note first, pick a patient,
# and understand what data exists before running the quality gate.
# ---------------------------------------------------------------------------


@router.get("/summaries")
async def list_summaries(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(
        default=None, description="Filter by admission diagnosis keyword"
    ),
):
    """
    List available discharge summaries for ED review.

    Returns lightweight records (no full note text) so the
    ED dashboard can show a scrollable list of cases.
    """
    bundle = get_bundle()
    cases = bundle.clinical_cases

    # Optional keyword filter
    if search:
        search_lower = search.lower()
        cases = cases[
            cases["admission_diagnosis"]
            .str.lower()
            .str.contains(search_lower, na=False)
        ]

    # Paginate
    page = cases.iloc[offset : offset + limit]

    results = []
    for _, row in page.iterrows():
        results.append(
            {
                "hadm_id": int(row["hadm_id"]),
                "subject_id": int(row["subject_id"]),
                "age": int(row["age"]) if row.get("age") else None,
                "gender": row.get("gender"),
                "admission_diagnosis": row.get("admission_diagnosis"),
                "has_discharge_summary": bool(row.get("discharge_summary")),
                # First 150 chars so the doctor can identify the case
                "summary_preview": (
                    str(row["discharge_summary"])[:150] + "..."
                    if row.get("discharge_summary")
                    else None
                ),
            }
        )

    return {
        "total": len(cases),
        "offset": offset,
        "limit": limit,
        "results": results,
    }


@router.get("/summaries/{hadm_id}")
async def get_summary(hadm_id: int):
    """
    Get the full discharge summary + record counts for a specific admission.

    WHY record_counts: Before the ED doctor runs the quality gate, they can
    see "this patient has 12 diagnoses and 8 meds" and already sense if the
    note looks thin compared to what's in the record.
    """
    bundle = get_bundle()

    try:
        ctx = get_patient_context(hadm_id, bundle)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "hadm_id": ctx.hadm_id,
        "subject_id": ctx.subject_id,
        "age": ctx.age,
        "gender": ctx.gender,
        "admission_diagnosis": ctx.admission_diagnosis,
        "discharge_summary": ctx.discharge_summary,
        "record_counts": {
            "diagnoses": len(ctx.diagnoses),
            "medications": len(ctx.prescriptions),
            "labs": len(ctx.labs),
        },
    }
