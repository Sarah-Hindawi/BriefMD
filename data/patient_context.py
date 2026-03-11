"""Join all 6 tables to build complete patient context by hadm_id."""

import logging
from dataclasses import dataclass

import pandas as pd

from data.loader import DataBundle

logger = logging.getLogger(__name__)


@dataclass
class PatientContext:
    subject_id: int
    hadm_id: int
    age: int
    gender: str
    admission_diagnosis: str
    discharge_summary: str
    diagnoses: pd.DataFrame
    labs: pd.DataFrame
    prescriptions: pd.DataFrame


def get_patient_context(hadm_id: int, bundle: DataBundle) -> PatientContext:
    """Join all 6 tables for a single admission."""
    case = bundle.clinical_cases[bundle.clinical_cases["hadm_id"] == hadm_id]
    if case.empty:
        raise ValueError(f"No clinical case found for hadm_id={hadm_id}")

    row = case.iloc[0]

    # Diagnoses with labels
    diagnoses = bundle.diagnoses[bundle.diagnoses["hadm_id"] == hadm_id].copy()
    if not diagnoses.empty and not bundle.diagnosis_dict.empty:
        diagnoses = diagnoses.merge(
            bundle.diagnosis_dict[["icd9_code", "short_title", "long_title"]],
            on="icd9_code",
            how="left",
        )

    # Labs with labels
    labs = bundle.labs[bundle.labs["hadm_id"] == hadm_id].copy()
    if not labs.empty and not bundle.lab_dict.empty:
        labs = labs.merge(
            bundle.lab_dict[["itemid", "lab_name", "fluid", "category"]],
            on="itemid",
            how="left",
        )

    # Prescriptions
    prescriptions = bundle.prescriptions[bundle.prescriptions["hadm_id"] == hadm_id].copy()

    logger.info(
        f"Patient context for hadm_id={hadm_id}: "
        f"{len(diagnoses)} diagnoses, {len(labs)} labs, {len(prescriptions)} prescriptions"
    )

    return PatientContext(
        subject_id=int(row.get("subject_id", 0)),
        hadm_id=hadm_id,
        age=int(row.get("age", 0)),
        gender=str(row.get("gender", "")),
        admission_diagnosis=str(row.get("admission_diagnosis", "")),
        discharge_summary=str(row.get("discharge_summary", "")),
        diagnoses=diagnoses,
        labs=labs,
        prescriptions=prescriptions,
    )


def list_patients(bundle: DataBundle) -> list[dict]:
    """List all patients with summary info."""
    cols = ["subject_id", "hadm_id", "age", "gender", "admission_diagnosis"]
    available = [c for c in cols if c in bundle.clinical_cases.columns]
    return bundle.clinical_cases[available].to_dict(orient="records")
