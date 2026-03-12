"""
Chat Router — RAG Q&A
=====================
Moved from pcp.py so BOTH ED and PCP dashboards can use it.
The workflow:
  1. GET  /api/v1/patients/{hadm_id} → See patient context (in patients.py)
  2. POST /api/v1/chat/ask           → Ask follow-up questions (    this file)      


"""

from fastapi import APIRouter, HTTPException

from api.dependencies import get_agent, get_bundle
from api.schemas.chat_schema import ChatRequest, AskResponse
from data.patient_context import get_patient_context

router = APIRouter()


@router.post("/ask", response_model=AskResponse)
async def ask(request: ChatRequest):
    """
    RAG-powered Q&A grounded in patient data + clinical guidelines.

    The LLM answers using:
    1. The patient's discharge summary
    2. Extracted structured data (diagnoses, meds)
    3. Your teammate's similar-case retrieval from ChromaDB
    4. Clinical guidelines (HQO, drug interactions)

    The LLM should NOT answer from general knowledge — only from
    retrieved context. If the answer isn't in the context, it says so.
    """
    bundle = get_bundle()
    agent = get_agent()

    try:
        ctx = get_patient_context(request.hadm_id, bundle)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    extracted = agent.extractor.extract(ctx.discharge_summary)

    answer = agent.ask(
        question=request.question,
        note_text=ctx.discharge_summary,
        extracted=extracted,
        patient_diagnoses=ctx.diagnoses,
        patient_prescriptions=ctx.prescriptions,
        age=ctx.age,
        gender=ctx.gender,
        admission_diagnosis=ctx.admission_diagnosis,
    )

    return AskResponse(
        hadm_id=request.hadm_id,
        question=request.question,
        answer=answer,
        # TODO: populate these once RAG pipeline returns source metadata
        sources=[],
        confidence=None,
    )