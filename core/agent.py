import logging

import pandas as pd

from knowledge.hqo_checklist import run_hqo_checklist
from core.connector import Connector
from core.extractor import Extractor
from core.llm_client import LLMClient
from core.models.extracted import ExtractedData
from core.models.flags import VerificationResult
from core.models.network import ComorbidityNetwork
from core.models.report import (
    EDReport,
    FullReport,
    PCPReport,
    TodoItem,
)
from core.verifier import Verifier
from config.settings import settings

logger = logging.getLogger(__name__)


class Agent:
    """Orchestrator: Extract → Verify → Connect. Only Step 1 needs the LLM."""

    def __init__(
        self,
        llm_client: LLMClient,
        all_diagnoses: pd.DataFrame,
        diagnosis_dict: pd.DataFrame,
    ) -> None:
        self.llm = llm_client
        self.extractor = Extractor(llm_client)
        self.verifier = Verifier()
        self.connector = Connector(all_diagnoses, diagnosis_dict)

    def run(
        self,
        note_text: str,
        patient_diagnoses: pd.DataFrame,
        patient_labs: pd.DataFrame,
        patient_prescriptions: pd.DataFrame,
        subject_id: int = 0,
        hadm_id: int = 0,
    ) -> FullReport:
        """Full pipeline: Extract → Verify → Connect + both checklists."""

        # Step 1: Extract (LLM)
        logger.info(f"Step 1: Extracting from note ({len(note_text)} chars)")
        extracted = self.extractor.extract(note_text)

        # Step 2: Verify (deterministic)
        logger.info("Step 2: Verifying against structured data")
        flags = self.verifier.verify(
            extracted, patient_diagnoses, patient_labs, patient_prescriptions,
        )

        # Step 3: Connect (NetworkX)
        patient_codes = _get_patient_codes(patient_diagnoses)
        logger.info(f"Step 3: Building network ({len(patient_codes)} codes)")
        network = self.connector.connect(patient_codes, hadm_id=hadm_id)

        # Checklists (deterministic)
        hqo = run_hqo_checklist(extracted, note_text)

        return FullReport(
            subject_id=subject_id,
            hadm_id=hadm_id,
            extracted=extracted,
            flags=flags,
            network=network,
            hqo_checklist=hqo,
        )

    def run_ed_check(
        self,
        note_text: str,
        patient_diagnoses: pd.DataFrame,
        patient_labs: pd.DataFrame,
        patient_prescriptions: pd.DataFrame,
        subject_id: int = 0,
        hadm_id: int = 0,
    ) -> EDReport:
        """Side A: ED quality gate."""
        full = self.run(
            note_text, patient_diagnoses, patient_labs, patient_prescriptions,
            subject_id=subject_id, hadm_id=hadm_id,
        )

        fix_suggestions = _generate_fix_suggestions(full.flags, full.extracted)

        return EDReport(
            subject_id=subject_id,
            hadm_id=hadm_id,
            extracted=full.extracted,
            flags=full.flags,
            network=full.network,
            hqo_checklist=full.hqo_checklist,
            fix_suggestions=fix_suggestions,
        )

    def run_pcp_report(
        self,
        note_text: str,
        patient_diagnoses: pd.DataFrame,
        patient_labs: pd.DataFrame,
        patient_prescriptions: pd.DataFrame,
        subject_id: int = 0,
        hadm_id: int = 0,
    ) -> PCPReport:
        """Side B: PCP verified report."""
        full = self.run(
            note_text, patient_diagnoses, patient_labs, patient_prescriptions,
            subject_id=subject_id, hadm_id=hadm_id,
        )

        todo = _generate_todo_list(full.flags, full.extracted)

        # LLM call 2: generate PCP-facing summary
        logger.info("Generating PCP summary")
        pcp_summary = self.extractor.summarize_for_pcp(full.extracted)

        return PCPReport(
            subject_id=subject_id,
            hadm_id=hadm_id,
            pcp_summary=pcp_summary,
            extracted=full.extracted,
            flags=full.flags,
            network=full.network,
            hqo_checklist=full.hqo_checklist,
            todo_list=todo,
        )

    def ask(
        self,
        question: str,
        note_text: str,
        extracted: ExtractedData,
        patient_diagnoses: pd.DataFrame,
        patient_prescriptions: pd.DataFrame,
        age: int = 0,
        gender: str = "",
        admission_diagnosis: str = "",
    ) -> str:
        """PCP Q&A: LLM answers using patient data as context."""
        diagnoses_str = ", ".join(extracted.diagnoses_mentioned) if extracted.diagnoses_mentioned else "none extracted"
        meds_str = ", ".join(m.name for m in extracted.medications_discharge) if extracted.medications_discharge else "none extracted"
        allergies_str = ", ".join(extracted.allergies) if extracted.allergies else "none documented"
        labs_str = ", ".join(extracted.lab_results_discussed) if extracted.lab_results_discussed else "none discussed"
        follow_up_str = "; ".join(
            f"{f.provider} ({f.specialty}) in {f.timeframe}" for f in extracted.follow_up_plan
        ) if extracted.follow_up_plan else "none documented"

        pmh_str = ", ".join(extracted.past_medical_history) if extracted.past_medical_history else "none documented"

        prompt = f"""Answer the doctor's question using ONLY the patient data below.
Be concise and clinically precise. If the data doesn't contain the answer, say so.

Patient context:
- Age: {age if age else 'unknown'} years old
- Gender/Sex: {'Female' if gender == 'F' else 'Male' if gender == 'M' else gender or 'unknown'}
- Admission diagnosis: {admission_diagnosis or extracted.admission_diagnosis or 'unknown'}
- Chief complaint: {extracted.chief_complaint or 'unknown'}
- Past medical history: {pmh_str}
- Family history: {extracted.family_history or 'none documented'}
- Social history: {extracted.social_history or 'none documented'}
- Diagnoses: {diagnoses_str}
- Medications: {meds_str}
- Allergies: {allergies_str}
- Labs discussed: {labs_str}
- Follow-up plan: {follow_up_str}
- PCP: {extracted.pcp_name or 'not documented'}
- Discharge instructions: {extracted.discharge_instructions[:300] if extracted.discharge_instructions else 'none'}

Doctor's question: {question}"""

        return self.llm.generate(
            prompt,
            system="You are a clinical decision support assistant. Answer questions about this patient using only the provided data. Never diagnose or prescribe.",
            temperature=0.7,
        )


def _get_patient_codes(diagnoses: pd.DataFrame) -> list[str]:
    if diagnoses.empty or "icd9_code" not in diagnoses.columns:
        return []
    return list(diagnoses["icd9_code"].astype(str).str.strip().unique())


def _generate_fix_suggestions(result: VerificationResult, extracted: ExtractedData) -> list[str]:
    suggestions: list[str] = []

    for f in result.flags:
        if f.severity == "critical":
            suggestions.append(f"CRITICAL: {f.title}. {f.detail}")
        elif f.category == "medication":
            suggestions.append(f"Review: {f.title}. {f.detail}")

    if result.diagnoses_missed:
        suggestions.append(
            f"Add missing diagnoses to note: {', '.join(result.diagnoses_missed[:5])}"
        )

    if not extracted.follow_up_plan:
        suggestions.append("Add specific follow-up plan with provider name, date, and reason.")
    else:
        for item in extracted.follow_up_plan:
            if not item.timeframe or not item.provider:
                suggestions.append(
                    "Make follow-up plan specific: include provider name and appointment timeframe."
                )
                break

    if not extracted.allergies:
        suggestions.append("Document patient allergies in the discharge note.")

    if not extracted.lab_results_discussed:
        suggestions.append("Discuss relevant lab results and any pending tests in the note.")

    return suggestions


def _generate_todo_list(result: VerificationResult, extracted: ExtractedData) -> list[TodoItem]:
    todos: list[TodoItem] = []

    for f in result.flags:
        if f.severity == "critical":
            todos.append(TodoItem(
                priority=1,
                action=f.title,
                reason=f.detail,
                category=f.category,
            ))
        elif f.severity == "warning" and f.category == "medication":
            todos.append(TodoItem(
                priority=1,
                action=f.title,
                reason=f.detail,
                category="medication",
            ))

    for diag in result.diagnoses_missed:
        todos.append(TodoItem(
            priority=2,
            action=f"Confirm diagnosis: {diag}",
            reason="Coded in hospital records but not mentioned in discharge note",
            category="referral",
        ))

    for test in extracted.pending_tests:
        todos.append(TodoItem(
            priority=2,
            action=f"Follow up on pending test: {test.test_name}",
            reason=test.reason,
            category="lab",
        ))

    for item in extracted.follow_up_plan:
        if item.timeframe and item.provider:
            todos.append(TodoItem(
                priority=3,
                action=f"Schedule follow-up with {item.provider} ({item.specialty}) within {item.timeframe}",
                reason=item.reason,
                category="referral",
            ))

    todos.sort(key=lambda t: t.priority)
    return todos
