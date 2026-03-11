import logging

import pandas as pd

from core.models.extracted import ExtractedData
from core.models.flags import (
    Contraindication,
    DiagnosisGap,
    DrugInteraction,
    Flag,
    Severity,
    VerificationFlags,
)

logger = logging.getLogger(__name__)

DANGEROUS_PAIRS = [
    {
        "drug": "rosiglitazone",
        "alt_names": ["avandia"],
        "condition": "heart failure",
        "icd9": ["4280"],
        "severity": "FDA black box",
    },
    {
        "drug": "metformin",
        "alt_names": ["glucophage"],
        "condition": "acute kidney injury",
        "icd9": ["5849"],
        "severity": "contraindicated",
    },
    {
        "drug": "nsaid",
        "alt_names": ["ibuprofen", "naproxen", "aspirin", "ketorolac"],
        "condition": "chronic kidney disease",
        "icd9": ["585"],
        "severity": "caution",
    },
]

DRUG_INTERACTIONS = [
    {
        "drug_a": "phenytoin",
        "alt_names_a": ["dilantin"],
        "drug_b": "warfarin",
        "alt_names_b": ["coumadin"],
        "severity": "drug-drug interaction",
        "detail": "Phenytoin displaces warfarin from protein binding, increasing bleeding risk. Monitor INR closely.",
    },
]


class Verifier:
    """Step 2: Cross-reference extracted data vs structured tables. No LLM."""

    def verify(
        self,
        extracted: ExtractedData,
        diagnoses: pd.DataFrame,
        labs: pd.DataFrame,
        prescriptions: pd.DataFrame,
    ) -> VerificationFlags:
        result = VerificationFlags()

        self._check_diagnosis_gaps(extracted, diagnoses, result)
        self._check_contraindications(extracted, prescriptions, diagnoses, result)
        self._check_drug_interactions(extracted, prescriptions, result)
        self._check_lab_gaps(extracted, labs, result)
        self._check_follow_up(extracted, result)
        self._check_allergies(extracted, result)

        logger.info(
            f"Verification complete: {len(result.contraindications)} contraindications, "
            f"{len(result.drug_interactions)} interactions, "
            f"{len(result.diagnosis_gaps)} diagnosis gaps, "
            f"{len(result.flags)} flags"
        )
        return result

    def _check_diagnosis_gaps(
        self,
        extracted: ExtractedData,
        diagnoses: pd.DataFrame,
        result: VerificationFlags,
    ) -> None:
        if diagnoses.empty:
            return

        mentioned_lower = [d.lower() for d in extracted.diagnoses_mentioned]

        for _, row in diagnoses.iterrows():
            code = str(row.get("icd9_code", ""))
            title = str(row.get("short_title", row.get("long_title", "")))

            found = any(
                title.lower() in m or m in title.lower()
                for m in mentioned_lower
                if m
            )

            if not found:
                result.diagnosis_gaps.append(
                    DiagnosisGap(
                        icd9_code=code,
                        diagnosis=title,
                        mentioned_in_note=False,
                    )
                )

        if result.diagnosis_gaps:
            result.flags.append(Flag(
                severity=Severity.YELLOW,
                category="diagnosis",
                summary=f"{len(result.diagnosis_gaps)} coded diagnoses not mentioned in note",
                detail=", ".join(g.diagnosis for g in result.diagnosis_gaps[:5]),
            ))

    def _check_contraindications(
        self,
        extracted: ExtractedData,
        prescriptions: pd.DataFrame,
        diagnoses: pd.DataFrame,
        result: VerificationFlags,
    ) -> None:
        med_names = _collect_med_names(extracted, prescriptions)
        diag_codes = set()
        if not diagnoses.empty and "icd9_code" in diagnoses.columns:
            diag_codes = {str(c).strip() for c in diagnoses["icd9_code"]}

        for pair in DANGEROUS_PAIRS:
            all_drug_names = [pair["drug"]] + pair.get("alt_names", [])
            drug_match = _any_match(all_drug_names, med_names)

            if not drug_match:
                continue

            code_match = any(
                code.startswith(icd9)
                for code in diag_codes
                for icd9 in pair["icd9"]
            )

            if code_match:
                result.contraindications.append(Contraindication(
                    drug=drug_match,
                    condition=pair["condition"],
                    icd9=", ".join(pair["icd9"]),
                    severity_label=pair["severity"],
                    detail=f"{drug_match} prescribed to patient with {pair['condition']}",
                ))
                result.flags.append(Flag(
                    severity=Severity.RED,
                    category="contraindication",
                    summary=f"{drug_match} + {pair['condition']} ({pair['severity']})",
                    detail=f"Patient has ICD9 {', '.join(pair['icd9'])} and is prescribed {drug_match}",
                ))

    def _check_drug_interactions(
        self,
        extracted: ExtractedData,
        prescriptions: pd.DataFrame,
        result: VerificationFlags,
    ) -> None:
        med_names = _collect_med_names(extracted, prescriptions)

        for pair in DRUG_INTERACTIONS:
            names_a = [pair["drug_a"]] + pair.get("alt_names_a", [])
            names_b = [pair["drug_b"]] + pair.get("alt_names_b", [])

            match_a = _any_match(names_a, med_names)
            match_b = _any_match(names_b, med_names)

            if match_a and match_b:
                result.drug_interactions.append(DrugInteraction(
                    drug_a=match_a,
                    drug_b=match_b,
                    severity_label=pair["severity"],
                    detail=pair.get("detail", ""),
                ))
                result.flags.append(Flag(
                    severity=Severity.ORANGE,
                    category="drug-interaction",
                    summary=f"{match_a} + {match_b} ({pair['severity']})",
                    detail=pair.get("detail", ""),
                ))

    def _check_lab_gaps(
        self,
        extracted: ExtractedData,
        labs: pd.DataFrame,
        result: VerificationFlags,
    ) -> None:
        if labs.empty:
            return

        discussed_lower = {l.lower() for l in extracted.lab_results_discussed if l}

        if "lab_name" in labs.columns:
            lab_names = labs["lab_name"].dropna().unique()
        elif "itemid" in labs.columns:
            lab_names = labs["itemid"].dropna().unique()
        else:
            return

        total_labs = len(lab_names)
        if total_labs > 0 and not discussed_lower:
            result.lab_gaps.append(f"{total_labs} lab results not discussed in note")
            result.flags.append(Flag(
                severity=Severity.YELLOW,
                category="lab",
                summary=f"{total_labs} lab results not discussed in note",
            ))

    def _check_follow_up(
        self,
        extracted: ExtractedData,
        result: VerificationFlags,
    ) -> None:
        if not extracted.follow_up_plan:
            result.flags.append(Flag(
                severity=Severity.YELLOW,
                category="follow-up",
                summary="No follow-up plan specified",
            ))
            return

        for item in extracted.follow_up_plan:
            if not item.timeframe or not item.provider:
                result.flags.append(Flag(
                    severity=Severity.YELLOW,
                    category="follow-up",
                    summary="Follow-up plan is vague",
                    detail=f"Provider: '{item.provider}', Timeframe: '{item.timeframe}'",
                ))

    def _check_allergies(
        self,
        extracted: ExtractedData,
        result: VerificationFlags,
    ) -> None:
        if not extracted.allergies:
            result.flags.append(Flag(
                severity=Severity.YELLOW,
                category="allergies",
                summary="No allergies documented in note",
            ))


def _collect_med_names(
    extracted: ExtractedData,
    prescriptions: pd.DataFrame,
) -> set[str]:
    names: set[str] = set()

    for med in extracted.medications_discharge + extracted.medications_stopped:
        names.add(med.name.lower())

    if not prescriptions.empty and "drug" in prescriptions.columns:
        for drug in prescriptions["drug"].dropna().unique():
            names.add(str(drug).lower())

    return names


def _any_match(drug_names: list[str], med_set: set[str]) -> str:
    for name in drug_names:
        for med in med_set:
            if name.lower() in med or med in name.lower():
                return med
    return ""
