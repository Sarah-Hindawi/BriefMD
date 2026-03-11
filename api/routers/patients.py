from fastapi import APIRouter, HTTPException

from api.dependencies import get_bundle
from api.schemas.shared import PatientDetail, PatientSummary
from data.patient_context import get_patient_context, list_patients

router = APIRouter()


@router.get("/patients", response_model=list[PatientSummary])
async def get_patients():
    """List all patients."""
    bundle = get_bundle()
    rows = list_patients(bundle)
    return [PatientSummary(**row) for row in rows]


@router.get("/patient/{hadm_id}", response_model=PatientDetail)
async def get_patient(hadm_id: int):
    """Full patient context (all 6 tables joined)."""
    bundle = get_bundle()

    try:
        ctx = get_patient_context(hadm_id, bundle)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return PatientDetail(
        subject_id=ctx.subject_id,
        hadm_id=ctx.hadm_id,
        age=ctx.age,
        gender=ctx.gender,
        admission_diagnosis=ctx.admission_diagnosis,
        discharge_summary=ctx.discharge_summary,
        diagnosis_count=len(ctx.diagnoses),
        lab_count=len(ctx.labs),
        prescription_count=len(ctx.prescriptions),
    )


@router.get("/patient/{hadm_id}/network")
async def get_patient_network(hadm_id: int):
    """Comorbidity graph data (nodes, edges, clusters)."""
    bundle = get_bundle()

    try:
        ctx = get_patient_context(hadm_id, bundle)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    from api.dependencies import get_agent

    agent = get_agent()
    patient_codes = list(ctx.diagnoses["icd9_code"].astype(str).str.strip().unique()) if not ctx.diagnoses.empty else []
    network = agent.connector.connect(patient_codes, hadm_id=hadm_id)

    return network.model_dump()
