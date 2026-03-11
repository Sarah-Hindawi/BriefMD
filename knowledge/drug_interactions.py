"""
Drug-Disease Contraindication Lookup
====================================
Curated table of dangerous drug-disease pairs. NO LLM involved.

The LLM's job is to EXPLAIN why a flagged interaction matters (via RAG).
This module's job is to DETECT that the interaction exists.

Sources: FDA black box warnings, UpToDate, clinical pharmacology references.
Each entry includes a citation so judges/clinicians can verify.

Usage:
    from knowledge.drug_interactions import check_interactions
    flags = check_interactions(prescriptions_df, diagnoses_df)
"""

import logging
import re
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DrugDiseaseInteraction:
    """A single known dangerous drug-disease pair."""
    drug_pattern: str          # Regex pattern matching drug names
    disease_codes: list[str]   # ICD-9 codes that make this drug dangerous
    disease_name: str          # Human-readable disease name
    severity: str              # "critical" or "warning"
    reason: str                # Why this combination is dangerous
    source: str                # Clinical reference


# ---------------------------------------------------------------------------
# Curated interaction database
# ---------------------------------------------------------------------------
# IMPORTANT: These are well-established contraindications, not edge cases.
# Each one has an FDA warning or strong clinical evidence behind it.
# ---------------------------------------------------------------------------

INTERACTIONS: list[DrugDiseaseInteraction] = [

    # ---- CARDIOVASCULAR ----

    DrugDiseaseInteraction(
        drug_pattern=r"rosiglitazone|avandia",
        disease_codes=["428.0", "428.1", "428.9", "428.20", "428.21",
                       "428.22", "428.23", "428.30", "428.31", "428.32",
                       "428.33", "428.40", "428.41", "428.42", "428.43"],
        disease_name="Congestive heart failure",
        severity="critical",
        reason=(
            "Rosiglitazone (Avandia) causes fluid retention and is "
            "contraindicated in NYHA Class III-IV heart failure. "
            "FDA black box warning: may cause or exacerbate heart failure."
        ),
        source="FDA Black Box Warning; NEJM 2007;356:2457-71",
    ),
    DrugDiseaseInteraction(
        drug_pattern=r"pioglitazone|actos",
        disease_codes=["428.0", "428.1", "428.9", "428.20", "428.21",
                       "428.22", "428.23", "428.30", "428.31", "428.32",
                       "428.33", "428.40", "428.41", "428.42", "428.43"],
        disease_name="Congestive heart failure",
        severity="critical",
        reason=(
            "Pioglitazone (Actos) is a thiazolidinedione that causes "
            "fluid retention. Contraindicated in NYHA Class III-IV heart failure."
        ),
        source="FDA Black Box Warning",
    ),
    DrugDiseaseInteraction(
        drug_pattern=r"metformin|glucophage",
        disease_codes=["585.1", "585.2", "585.3", "585.4", "585.5",
                       "585.6", "585.9"],
        disease_name="Chronic kidney disease",
        severity="warning",
        reason=(
            "Metformin requires dose adjustment or discontinuation in "
            "CKD stages 4-5 (eGFR <30) due to risk of lactic acidosis. "
            "Check creatinine and eGFR before continuing."
        ),
        source="FDA Label Update 2016; Kidney Int 2017;91:527-532",
    ),
    DrugDiseaseInteraction(
        drug_pattern=r"nsaid|ibuprofen|naproxen|diclofenac|indomethacin|ketorolac|meloxicam|celecoxib",
        disease_codes=["428.0", "428.1", "428.9", "428.20", "428.21",
                       "428.22", "428.23", "428.30", "428.31", "428.32",
                       "428.33", "428.40", "428.41", "428.42", "428.43"],
        disease_name="Congestive heart failure",
        severity="warning",
        reason=(
            "NSAIDs cause sodium and water retention, worsening heart failure. "
            "Associated with increased risk of hospitalization for CHF."
        ),
        source="AHA/ACC HF Guidelines 2022; JAMA 2000;284:1159",
    ),
    DrugDiseaseInteraction(
        drug_pattern=r"nsaid|ibuprofen|naproxen|diclofenac|indomethacin|ketorolac|meloxicam|celecoxib",
        disease_codes=["585.1", "585.2", "585.3", "585.4", "585.5",
                       "585.6", "585.9"],
        disease_name="Chronic kidney disease",
        severity="warning",
        reason=(
            "NSAIDs reduce renal blood flow via prostaglandin inhibition. "
            "Can accelerate CKD progression and cause acute kidney injury."
        ),
        source="KDIGO CKD Guidelines 2012",
    ),

    # ---- RENAL ----

    DrugDiseaseInteraction(
        drug_pattern=r"spironolactone|aldactone|eplerenone",
        disease_codes=["585.4", "585.5", "585.6", "585.9"],
        disease_name="Advanced chronic kidney disease",
        severity="critical",
        reason=(
            "Potassium-sparing diuretics in advanced CKD carry high risk "
            "of life-threatening hyperkalemia. Monitor potassium closely."
        ),
        source="KDIGO Guidelines; UpToDate",
    ),
    DrugDiseaseInteraction(
        drug_pattern=r"lithium",
        disease_codes=["585.1", "585.2", "585.3", "585.4", "585.5",
                       "585.6", "585.9"],
        disease_name="Chronic kidney disease",
        severity="critical",
        reason=(
            "Lithium is renally cleared. CKD increases lithium levels "
            "and toxicity risk. Requires significant dose reduction and "
            "frequent monitoring."
        ),
        source="Am J Psychiatry 2012;169:227-233",
    ),

    # ---- GI / BLEEDING ----

    DrugDiseaseInteraction(
        drug_pattern=r"warfarin|coumadin",
        disease_codes=["531.0", "531.2", "531.4", "531.6",   # gastric ulcer
                       "532.0", "532.2", "532.4", "532.6",   # duodenal ulcer
                       "533.0", "533.2", "533.4", "533.6",   # peptic ulcer
                       "578.0", "578.1", "578.9"],            # GI hemorrhage
        disease_name="GI bleeding / active ulcer",
        severity="critical",
        reason=(
            "Warfarin in the setting of active GI bleeding or ulceration "
            "significantly increases hemorrhage risk."
        ),
        source="ACCP Antithrombotic Guidelines",
    ),
    DrugDiseaseInteraction(
        drug_pattern=r"nsaid|ibuprofen|naproxen|diclofenac|aspirin|ketorolac",
        disease_codes=["531.0", "531.2", "531.4", "531.6",
                       "532.0", "532.2", "532.4", "532.6",
                       "533.0", "533.2", "533.4", "533.6"],
        disease_name="Active peptic ulcer",
        severity="critical",
        reason=(
            "NSAIDs and aspirin inhibit COX-1 protective prostaglandins "
            "in gastric mucosa. Contraindicated with active ulcer disease."
        ),
        source="ACG Peptic Ulcer Guidelines 2017",
    ),

    # ---- HEPATIC ----

    DrugDiseaseInteraction(
        drug_pattern=r"acetaminophen|tylenol|paracetamol",
        disease_codes=["571.0", "571.1", "571.2", "571.3", "571.5",
                       "571.6", "571.8", "571.9",  # chronic liver disease
                       "572.2", "572.3", "572.4",  # hepatic encephalopathy etc
                       "070.0", "070.1", "070.2", "070.3"],  # viral hepatitis
        disease_name="Liver disease",
        severity="warning",
        reason=(
            "Acetaminophen is hepatotoxic at lower doses in patients with "
            "liver disease. Maximum 2g/day (vs standard 4g/day)."
        ),
        source="FDA Advisory 2011; Hepatology 2005;42:1364-72",
    ),

    # ---- RESPIRATORY ----

    DrugDiseaseInteraction(
        drug_pattern=r"beta.?blocker|propranolol|metoprolol|atenolol|nadolol|timolol|carvedilol",
        disease_codes=["493.00", "493.01", "493.02", "493.10", "493.11",
                       "493.12", "493.20", "493.21", "493.22", "493.90",
                       "493.91", "493.92"],
        disease_name="Asthma",
        severity="warning",
        reason=(
            "Non-selective beta-blockers can trigger bronchospasm in asthma. "
            "Cardioselective agents (bisoprolol, metoprolol) may be used with "
            "caution. Avoid propranolol, nadolol, timolol."
        ),
        source="GINA Asthma Guidelines 2023",
    ),

    # ---- DIABETES + RENAL ----

    DrugDiseaseInteraction(
        drug_pattern=r"glyburide|glibenclamide|glipizide|glimepiride",
        disease_codes=["585.3", "585.4", "585.5", "585.6", "585.9"],
        disease_name="Chronic kidney disease (stage 3+)",
        severity="warning",
        reason=(
            "Sulfonylureas are renally cleared. In CKD, prolonged half-life "
            "increases severe hypoglycemia risk. Dose adjust or switch."
        ),
        source="Diabetes Care 2020;43(Suppl 1):S98-S110",
    ),
]


# ---------------------------------------------------------------------------
# Compile patterns once at import time
# ---------------------------------------------------------------------------

_COMPILED = [
    (re.compile(ix.drug_pattern, re.IGNORECASE), ix)
    for ix in INTERACTIONS
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class InteractionFlag:
    """A detected drug-disease interaction for a specific patient."""
    drug_name: str
    disease_name: str
    icd9_code: str
    severity: str
    reason: str
    source: str


def check_interactions(
    prescriptions: pd.DataFrame,
    diagnoses: pd.DataFrame,
) -> list[InteractionFlag]:
    """
    Check a patient's prescriptions against their diagnoses for
    known dangerous drug-disease pairs.

    Args:
        prescriptions: Patient's prescriptions DataFrame (must have 'drug' column)
        diagnoses: Patient's diagnoses DataFrame (must have 'icd9_code' column)

    Returns:
        List of InteractionFlag for each detected contraindication.
    """
    if prescriptions.empty or diagnoses.empty:
        return []

    # Get unique drug names and ICD-9 codes for this patient
    if "drug" not in prescriptions.columns or "icd9_code" not in diagnoses.columns:
        logger.warning("Missing 'drug' or 'icd9_code' column")
        return []

    drug_names = prescriptions["drug"].dropna().astype(str).str.strip().unique()
    patient_codes = set(
        diagnoses["icd9_code"].dropna().astype(str).str.strip().unique()
    )

    flags: list[InteractionFlag] = []
    seen: set[tuple[str, str]] = set()  # Deduplicate (drug, disease) pairs

    for drug in drug_names:
        for pattern, interaction in _COMPILED:
            if not pattern.search(drug):
                continue

            # Check if patient has any of the dangerous disease codes
            matching_codes = patient_codes & set(interaction.disease_codes)
            if not matching_codes:
                continue

            # Use the first matching code for the flag
            code = sorted(matching_codes)[0]
            dedup_key = (drug.lower(), interaction.disease_name)

            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            flags.append(InteractionFlag(
                drug_name=drug,
                disease_name=interaction.disease_name,
                icd9_code=code,
                severity=interaction.severity,
                reason=interaction.reason,
                source=interaction.source,
            ))

            logger.warning(
                f"INTERACTION: {drug} + {interaction.disease_name} "
                f"({code}) — {interaction.severity}"
            )

    logger.info(f"Checked {len(drug_names)} drugs × {len(patient_codes)} codes → {len(flags)} flags")
    return flags