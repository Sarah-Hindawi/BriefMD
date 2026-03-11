import logging

import pandas as pd

from knowledge.hqo_checklist import run_hqo_checklist
from knowledge.pcp_preferences import run_pcp_preferences
from core.connector import Connector
from core.extractor import Extractor
from core.llm_client import LLMClient
from core.models.extracted import ExtractedData
from core.models.flags import VerificationFlags
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
        pcp = run_pcp_preferences(extracted)

        return FullReport(
            subject_id=subject_id,
            hadm_id=hadm_id,
            extracted=extracted,
            flags=flags,
            network=network,
            hqo_checklist=hqo,
            pcp_preferences=pcp,
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

        return PCPReport(
            subject_id=subject_id,
            hadm_id=hadm_id,
            extracted=full.extracted,
            flags=full.flags,
            network=full.network,
            pcp_preferences=full.pcp_preferences,
            todo_list=todo,
        )

    def ask(
        self,
        question: str,
        note_text: str,
        extracted: ExtractedData,
        patient_diagnoses: pd.DataFrame,
        patient_prescriptions: pd.DataFrame,
    ) -> str:
        """PCP Q&A: Mistral answers using patient data as context."""
        diagnoses_str = ", ".join(extracted.diagnoses_mentioned) if extracted.diagnoses_mentioned else "none extracted"
        meds_str = ", ".join(m.name for m in extracted.medications_discharge) if extracted.medications_discharge else "none extracted"
        allergies_str = ", ".join(extracted.allergies) if extracted.allergies else "none documented"

        prompt = f"""Answer the doctor's question using ONLY the patient data below.
Be concise and clinically precise. If the data doesn't contain the answer, say so.

Patient context:
- Diagnoses: {diagnoses_str}
- Medications: {meds_str}
- Allergies: {allergies_str}
- Chief complaint: {extracted.chief_complaint}

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


def _generate_fix_suggestions(flags: VerificationFlags, extracted: ExtractedData) -> list[str]:
    suggestions: list[str] = []

    for c in flags.contraindications:
        suggestions.append(
            f"CRITICAL: Review {c.drug} — {c.severity_label} with {c.condition}. "
            f"Consider discontinuing or documenting clinical justification."
        )

    for di in flags.drug_interactions:
        suggestions.append(
            f"Review interaction: {di.drug_a} + {di.drug_b}. {di.detail}"
        )

    if flags.diagnosis_gaps:
        gap_names = [g.diagnosis for g in flags.diagnosis_gaps[:5]]
        suggestions.append(
            f"Add missing diagnoses to note: {', '.join(gap_names)}"
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


def _generate_todo_list(flags: VerificationFlags, extracted: ExtractedData) -> list[TodoItem]:
    todos: list[TodoItem] = []

    for c in flags.contraindications:
        todos.append(TodoItem(
            priority=1,
            action=f"Urgent: Review {c.drug} — {c.severity_label} with {c.condition}",
            reason=c.detail,
            category="medication",
        ))

    for di in flags.drug_interactions:
        todos.append(TodoItem(
            priority=1,
            action=f"Review interaction: {di.drug_a} + {di.drug_b}",
            reason=di.detail,
            category="medication",
        ))

    for gap in flags.diagnosis_gaps:
        todos.append(TodoItem(
            priority=2,
            action=f"Confirm diagnosis: {gap.diagnosis} (ICD9 {gap.icd9_code})",
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
