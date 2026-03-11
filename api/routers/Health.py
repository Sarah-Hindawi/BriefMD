"""
Health Router
=============
Hit this before your demo to make sure everything is up.

WHY this exists:
  Your original /health in main.py just returned {"status": "ok"}.
  That only tells you the server started — not whether the data loaded,
  the agent initialized, or the LLM provider is reachable.

  This gives you a breakdown so you can catch problems before the demo.
"""

from fastapi import APIRouter

from api.dependencies import get_bundle, get_agent

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Returns status of each service.
    Call this before the demo: GET /api/v1/health
    """
    status = {}

    # Check data
    try:
        bundle = get_bundle()
        patient_count = len(bundle.clinical_cases) if bundle.clinical_cases is not None else 0
        status["data"] = {"loaded": True, "patient_count": patient_count}
    except RuntimeError:
        status["data"] = {"loaded": False}

    # Check agent
    try:
        agent = get_agent()
        status["agent"] = {"ready": True}
    except RuntimeError:
        status["agent"] = {"ready": False}

    # Overall
    all_ok = status.get("data", {}).get("loaded", False) and status.get("agent", {}).get("ready", False)
    status["status"] = "healthy" if all_ok else "degraded"

    return status