"""Find the best demo patient and pre-cache results to data/demo_cache.json."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.logging import setup_logging
from config.settings import settings
from core.agent import Agent
from core.llm_client import LLMClient
from data.loader import load_from_local
from data.patient_context import get_patient_context


def find_demo_patient():
    """Find patient with most diagnoses + dangerous interactions + documented allergies."""
    bundle = load_from_local()
    cases = bundle.clinical_cases

    scored: list[dict] = []
    for _, row in cases.iterrows():
        hadm_id = int(row["hadm_id"])
        patient_diags = bundle.diagnoses[bundle.diagnoses["hadm_id"] == hadm_id]
        patient_rx = bundle.prescriptions[bundle.prescriptions["hadm_id"] == hadm_id]

        diag_codes = set(patient_diags["icd9_code"].astype(str).str.strip()) if not patient_diags.empty else set()
        drug_names = set(patient_rx["drug"].str.lower()) if not patient_rx.empty and "drug" in patient_rx.columns else set()

        # Score: diagnosis count + bonus for dangerous combos
        score = len(diag_codes)

        # Avandia/rosiglitazone + CHF
        has_chf = any(c.startswith("4280") for c in diag_codes)
        has_avandia = bool(drug_names & {"rosiglitazone", "avandia"})
        if has_chf and has_avandia:
            score += 50

        # Phenytoin + warfarin
        has_phenytoin = bool(drug_names & {"phenytoin", "dilantin"})
        has_warfarin = bool(drug_names & {"warfarin", "coumadin"})
        if has_phenytoin and has_warfarin:
            score += 30

        # Metformin + AKI
        has_aki = any(c.startswith("5849") for c in diag_codes)
        has_metformin = bool(drug_names & {"metformin", "glucophage"})
        if has_aki and has_metformin:
            score += 20

        scored.append({
            "hadm_id": hadm_id,
            "subject_id": int(row.get("subject_id", 0)),
            "age": int(row.get("age", 0)),
            "gender": str(row.get("gender", "")),
            "diagnosis_count": len(diag_codes),
            "score": score,
        })

    scored.sort(key=lambda r: r["score"], reverse=True)
    best = scored[0]

    print(f"\nBest demo patient:")
    print(f"  hadm_id:    {best['hadm_id']}")
    print(f"  subject_id: {best['subject_id']}")
    print(f"  age:        {best['age']}")
    print(f"  gender:     {best['gender']}")
    print(f"  diagnoses:  {best['diagnosis_count']}")
    print(f"  score:      {best['score']}")

    return best


def cache_demo_results(hadm_id: int):
    """Run full pipeline on demo patient and save to JSON."""
    bundle = load_from_local()
    ctx = get_patient_context(hadm_id, bundle)

    llm = LLMClient()
    agent = Agent(
        llm_client=llm,
        all_diagnoses=bundle.diagnoses,
        diagnosis_dict=bundle.diagnosis_dict,
    )

    print(f"\nRunning pipeline on hadm_id={hadm_id}...")
    report = agent.run(
        note_text=ctx.discharge_summary,
        patient_diagnoses=ctx.diagnoses,
        patient_labs=ctx.labs,
        patient_prescriptions=ctx.prescriptions,
        subject_id=ctx.subject_id,
        hadm_id=ctx.hadm_id,
    )

    cache_path = Path("data/demo_cache.json")
    cache_path.write_text(json.dumps(report.model_dump(), indent=2, default=str))
    print(f"Cached to {cache_path}")


if __name__ == "__main__":
    setup_logging()
    best = find_demo_patient()

    if "--cache" in sys.argv:
        cache_demo_results(best["hadm_id"])
    else:
        print("\nRun with --cache to generate demo_cache.json (requires Ollama)")
