"""
BriefMD Verifier — Step 2 of the Pipeline
==========================================
DETERMINISTIC. NO LLM. Pure Python comparisons.

Takes the ExtractedData from Step 1 (extractor) and compares it against
the patient's actual structured data from the MIMIC dataset.

Catches:
  - Diagnoses in the record but missing from the note
  - Drug-disease contraindications
  - Abnormal lab values not referenced in the note
  - Medication discrepancies
  - Documentation gaps

This is where clinical safety lives. Every check is grounded in data,
not model inference. The LLM's only role is EXPLAINING flags later.
"""

import logging
from typing import Optional

import pandas as pd

from core.models.extracted import ExtractedData
from core.models.flags import VerificationFlag, VerificationResult
from knowledge.drug_interactions import (
    check_interactions,
    InteractionFlag,
)
from knowledge.lab_ranges import LabRangeChecker, LabAlert

logger = logging.getLogger(__name__)


class Verifier:
    """
    Compares LLM-extracted data against structured patient records.

    Initialize with a LabRangeChecker instance (computed once at startup).
    Then call verify() per patient.
    """

    def __init__(
        self,
        lab_ranges: Optional[LabRangeChecker] = None,
        diagnosis_dict: Optional[pd.DataFrame] = None,
    ):
        """
        Args:
            lab_ranges: Pre-computed LabRangeChecker from the full dataset.
                        If None, lab checks are skipped.
            diagnosis_dict: diagnosis_dictionary.csv.gz for ICD-9 → name lookup.
        """
        self.lab_ranges = lab_ranges
        self.diagnosis_dict = diagnosis_dict
        self._icd9_to_name: dict[str, str] = {}
        if diagnosis_dict is not None:
            self._icd9_to_name = dict(
                zip(
                    diagnosis_dict["icd9_code"].astype(str).str.strip(),
                    diagnosis_dict["short_title"].fillna("Unknown"),
                )
            )

    def verify(
        self,
        extracted: ExtractedData,
        patient_diagnoses: pd.DataFrame,
        patient_labs: pd.DataFrame,
        patient_prescriptions: pd.DataFrame,
        hadm_id: int | None = None,
    ) -> VerificationResult:
        """
        Run all verification checks. Returns a VerificationResult
        containing every flag found.

        Args:
            extracted: Structured data the LLM pulled from the discharge note.
            patient_diagnoses: From diagnoses_subset — columns: icd9_code, seq_num, ...
            patient_labs: From labs_subset — columns: itemid, charttime, value, unit, ...
            patient_prescriptions: From prescriptions_subset — columns: drug, dose_value, ...
            hadm_id: For logging context.
        """
        result = VerificationResult()

        logger.info(f"Verifying patient hadm_id={hadm_id}")

        # 1. Diagnosis comparison
        self._check_diagnoses(extracted, patient_diagnoses, result)

        # 2. Medication comparison + drug-disease interactions
        self._check_medications(extracted, patient_prescriptions, patient_diagnoses, result)

        # 3. Lab value checks
        self._check_labs(extracted, patient_labs, result)

        # 4. Documentation completeness
        self._check_documentation(extracted, result)

        logger.info(
            f"Verification complete: {result.total_flags} flags "
            f"({result.critical_count} critical, {result.warning_count} warning)"
        )
        return result

    # -----------------------------------------------------------------------
    # 1. DIAGNOSES
    # -----------------------------------------------------------------------

    def _check_diagnoses(
        self,
        extracted: ExtractedData,
        patient_diagnoses: pd.DataFrame,
        result: VerificationResult,
    ) -> None:
        """Compare diagnoses mentioned in note vs coded ICD-9 diagnoses."""

        if patient_diagnoses.empty:
            result.diagnoses_in_record = 0
            result.diagnoses_in_note = len(extracted.diagnoses_mentioned)
            return

        # Get coded diagnoses
        coded = patient_diagnoses["icd9_code"].astype(str).str.strip().unique().tolist()
        result.diagnoses_in_record = len(coded)
        result.diagnoses_in_note = len(extracted.diagnoses_mentioned)

        # Build searchable set from the note (lowercased)
        note_diagnoses_lower = {d.lower().strip() for d in extracted.diagnoses_mentioned}

        # For each coded diagnosis, check if it's mentioned in the note
        missed = []
        matched = []

        for icd9 in coded:
            name = self._icd9_to_name.get(icd9, "")
            name_lower = name.lower()

            # Check if any extracted diagnosis matches this code or name
            found = False
            for note_dx in note_diagnoses_lower:
                if (
                    icd9 in note_dx
                    or name_lower in note_dx
                    or note_dx in name_lower
                    or self._fuzzy_diagnosis_match(note_dx, name_lower)
                ):
                    found = True
                    break

            if found:
                matched.append(f"{name} ({icd9})")
            else:
                missed.append(f"{name} ({icd9})")

        result.diagnoses_matched = matched
        result.diagnoses_missed = missed

        # Flag if significant diagnoses are missed
        if missed:
            n_missed = len(missed)
            result.flags.append(VerificationFlag(
                severity="warning" if n_missed <= 3 else "critical" if n_missed > 5 else "warning",
                category="diagnosis",
                title=f"{n_missed} diagnoses not mentioned in note",
                detail=(
                    f"Patient has {result.diagnoses_in_record} coded diagnoses "
                    f"but note mentions {result.diagnoses_in_note}. "
                    f"Missing: {', '.join(missed[:5])}"
                    + (f" and {n_missed - 5} more" if n_missed > 5 else "")
                ),
                evidence=f"ICD-9 codes: {', '.join(icd9 for icd9 in coded if self._icd9_to_name.get(icd9, '') + f' ({icd9})' in missed)}",
                suggested_action="Add missing diagnoses to the discharge summary.",
            ))

    def _fuzzy_diagnosis_match(self, note_text: str, coded_name: str) -> bool:
        """
        Handle common abbreviations and variations.
        'chf' matches 'congestive heart failure', 'dm' matches 'diabetes mellitus', etc.
        """
        abbreviations = {
            "chf": "congestive heart failure",
            "cad": "coronary atherosclerosis",
            "copd": "chronic obstructive pulmonary",
            "dm": "diabetes mellitus",
            "dm2": "diabetes mellitus",
            "t2dm": "diabetes mellitus",
            "htn": "hypertension",
            "ckd": "chronic kidney",
            "esrd": "end stage renal",
            "afib": "atrial fibrillation",
            "a-fib": "atrial fibrillation",
            "mi": "myocardial infarction",
            "pe": "pulmonary embolism",
            "dvt": "deep vein thrombosis",
            "uti": "urinary tract infection",
            "bph": "benign prostatic hyperplasia",
            "gerd": "gastroesophageal reflux",
            "pna": "pneumonia",
            "ards": "acute respiratory distress",
            "aki": "acute kidney",
            "sle": "systemic lupus",
            "ra": "rheumatoid arthritis",
            "ms": "multiple sclerosis",
            "tia": "transient ischemic",
            "cva": "cerebrovascular",
        }

        # Check if note text is a known abbreviation
        expanded = abbreviations.get(note_text)
        if expanded and expanded in coded_name:
            return True

        # Check if coded name abbreviated form matches
        for abbrev, full in abbreviations.items():
            if abbrev == note_text and full in coded_name:
                return True

        return False

    # -----------------------------------------------------------------------
    # 2. MEDICATIONS
    # -----------------------------------------------------------------------

    def _check_medications(
        self,
        extracted: ExtractedData,
        patient_prescriptions: pd.DataFrame,
        patient_diagnoses: pd.DataFrame,
        result: VerificationResult,
    ) -> None:
        """Compare meds in note vs prescriptions table. Check drug-disease interactions."""

        # a) Count comparison
        note_med_names = [m.name.lower().strip() for m in extracted.medications_discharge]
        result.medications_in_note = len(note_med_names)

        if not patient_prescriptions.empty:
            record_meds = patient_prescriptions["drug"].dropna().unique().tolist()
            result.medications_in_record = len(record_meds)
        else:
            record_meds = []
            result.medications_in_record = 0

        # b) Drug-disease interactions
        # check_interactions takes DataFrames directly
        interactions = check_interactions(patient_prescriptions, patient_diagnoses)

        for interaction in interactions:
            flag = VerificationFlag(
                severity=interaction.severity,
                category="medication",
                title=f"{interaction.drug_name.title()} contraindicated with {interaction.disease_name}",
                detail=interaction.reason,
                evidence=f"Drug: {interaction.drug_name}, ICD-9: {interaction.icd9_code} ({interaction.disease_name})",
                suggested_action=interaction.alternative or "Review and consider alternative.",
            )
            result.medication_issues.append(flag)
            result.flags.append(flag)

        # c) Meds in record but not in note (possible omissions)
        if record_meds and note_med_names:
            note_med_set = set(note_med_names)
            record_med_lower = {m.lower().strip() for m in record_meds}

            # Only flag high-risk med classes not mentioned
            high_risk_classes = {
                "warfarin", "heparin", "insulin", "metformin", "digoxin",
                "lithium", "phenytoin", "carbamazepine", "methotrexate",
                "amiodarone", "vancomycin", "gentamicin",
            }

            for med in record_med_lower:
                first_word = med.split()[0]
                if first_word in high_risk_classes:
                    # Check if it's mentioned in note (fuzzy)
                    mentioned = any(
                        first_word in note_med or note_med in first_word
                        for note_med in note_med_set
                    )
                    if not mentioned:
                        result.flags.append(VerificationFlag(
                            severity="warning",
                            category="medication",
                            title=f"High-risk medication {first_word.title()} in record but not in note",
                            detail=f"Patient has a prescription for {med} but it's not mentioned in the discharge summary.",
                            evidence=f"Prescription record: {med}",
                            suggested_action=f"Verify {first_word.title()} status and document in note.",
                        ))

    # -----------------------------------------------------------------------
    # 3. LABS
    # -----------------------------------------------------------------------

    def _check_labs(
        self,
        extracted: ExtractedData,
        patient_labs: pd.DataFrame,
        result: VerificationResult,
    ) -> None:
        """Check for abnormal labs and flag critical values not mentioned in note."""

        result.labs_in_note = len(extracted.lab_results_discussed)
        result.labs_in_record = len(patient_labs) if not patient_labs.empty else 0

        if self.lab_ranges is None or patient_labs.empty:
            return

        alerts = self.lab_ranges.check_patient_labs(
            patient_labs,
            labs_mentioned_in_note=extracted.lab_results_discussed,
        )

        result.abnormal_labs = len(alerts)

        # Group alerts by severity
        critical_unmentioned = [a for a in alerts if a.severity == "critical" and not a.mentioned_in_note]
        warning_unmentioned = [a for a in alerts if a.severity == "warning" and not a.mentioned_in_note]

        # Flag critical labs not mentioned
        for alert in critical_unmentioned:
            flag_detail = (
                f"{alert.lab_name}: {alert.value} {alert.unit} "
                f"(ref: {alert.ref_low}–{alert.ref_high}). "
                f"{'Above' if alert.direction == 'high' else 'Below'} reference range."
            )
            result.critical_labs_missed.append(flag_detail)
            result.flags.append(VerificationFlag(
                severity="critical",
                category="lab",
                title=f"Critical {alert.lab_name} not referenced in note",
                detail=flag_detail,
                evidence=f"itemid={alert.itemid}, value={alert.value}, ref={alert.ref_low}-{alert.ref_high}",
                suggested_action=f"Document {alert.lab_name} value and follow-up plan.",
            ))

        # Summarize warning-level unmentioned labs (don't flood with individual flags)
        if warning_unmentioned:
            names = [a.lab_name for a in warning_unmentioned[:5]]
            n_more = len(warning_unmentioned) - 5
            detail = (
                f"{len(warning_unmentioned)} abnormal lab values not mentioned in note: "
                f"{', '.join(names)}"
                + (f" and {n_more} more" if n_more > 0 else "")
            )
            result.flags.append(VerificationFlag(
                severity="warning",
                category="lab",
                title=f"{len(warning_unmentioned)} abnormal labs not referenced in note",
                detail=detail,
                suggested_action="Review abnormal results and document relevant findings.",
            ))

    # -----------------------------------------------------------------------
    # 4. DOCUMENTATION COMPLETENESS
    # -----------------------------------------------------------------------

    def _check_documentation(
        self,
        extracted: ExtractedData,
        result: VerificationResult,
    ) -> None:
        """Check for basic documentation gaps that aren't caught by HQO checklist."""

        # Missing allergies
        if not extracted.allergies:
            result.flags.append(VerificationFlag(
                severity="warning",
                category="documentation",
                title="No allergies documented",
                detail="Allergy list is empty. Document 'NKDA' if no known allergies.",
                suggested_action="Confirm and document allergy status.",
            ))

        # Missing follow-up plan
        if not extracted.follow_up_plan:
            result.flags.append(VerificationFlag(
                severity="warning",
                category="follow_up",
                title="No follow-up plan documented",
                detail="No specific follow-up appointments or providers listed in the discharge note.",
                suggested_action="Document follow-up provider, specialty, and timeframe.",
            ))

        # Missing discharge instructions
        if not extracted.discharge_instructions or not extracted.discharge_instructions.strip():
            result.flags.append(VerificationFlag(
                severity="warning",
                category="documentation",
                title="No discharge instructions found",
                detail="Patient discharge instructions section is empty or missing.",
                suggested_action="Add discharge instructions including warning signs and when to return to ED.",
            ))

        # No medications at all (suspicious for most inpatient stays)
        if not extracted.medications_discharge and not extracted.medications_stopped:
            result.flags.append(VerificationFlag(
                severity="info",
                category="medication",
                title="No medications documented in discharge note",
                detail="Neither active nor discontinued medications were found in the note.",
                suggested_action="Verify medication list is complete.",
            ))