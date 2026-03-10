"""Ontario HQO Safe Discharge Practices — 9 items. Deterministic, no LLM."""

import re

from core.models.extracted import ExtractedData
from core.models.report import ChecklistItem

HQO_CHECKLIST = [
    {"id": "hqo_01", "label": "Discharge summary completed"},
    {"id": "hqo_02", "label": "Diagnosis documented"},
    {"id": "hqo_03", "label": "Medication reconciliation"},
    {"id": "hqo_04", "label": "Follow-up plan specified"},
    {"id": "hqo_05", "label": "Pending tests documented"},
    {"id": "hqo_06", "label": "Patient education provided"},
    {"id": "hqo_07", "label": "PCP identified"},
    {"id": "hqo_08", "label": "Allergies documented"},
    {"id": "hqo_09", "label": "Summary sent within 48h"},
]


def run_hqo_checklist(
    extracted: ExtractedData,
    note_text: str,
) -> list[ChecklistItem]:
    return [_check_item(item, extracted, note_text) for item in HQO_CHECKLIST]


def _check_item(
    item: dict,
    extracted: ExtractedData,
    note_text: str,
) -> ChecklistItem:
    item_id = item["id"]
    label = item["label"]

    match item_id:
        case "hqo_01":
            passed = len(note_text.strip()) > 0
            detail = "" if passed else "No discharge summary text found"

        case "hqo_02":
            passed = len(extracted.diagnoses_mentioned) > 0
            detail = (
                f"{len(extracted.diagnoses_mentioned)} diagnoses documented"
                if passed
                else "No diagnoses found in note"
            )

        case "hqo_03":
            has_meds = len(extracted.medications_discharge) > 0
            has_changes = any(
                m.is_new or m.is_changed or m.is_stopped
                for m in extracted.medications_discharge
            ) or len(extracted.medications_stopped) > 0
            passed = has_meds and has_changes
            if not has_meds:
                detail = "No medications listed"
            elif not has_changes:
                detail = "Medications listed but no changes documented"
            else:
                detail = "Medication changes documented"

        case "hqo_04":
            passed = _has_specific_follow_up(extracted)
            detail = (
                "Specific follow-up plan found"
                if passed
                else "Follow-up plan missing or vague (no provider/timeframe)"
            )

        case "hqo_05":
            passed = len(extracted.pending_tests) > 0
            detail = (
                f"{len(extracted.pending_tests)} pending tests documented"
                if passed
                else "No pending tests documented"
            )

        case "hqo_06":
            passed = len(extracted.discharge_instructions.strip()) > 0
            detail = "" if passed else "No discharge instructions found"

        case "hqo_07":
            passed = len(extracted.pcp_name.strip()) > 0
            detail = (
                f"PCP: {extracted.pcp_name}"
                if passed
                else "No PCP name/contact identified"
            )

        case "hqo_08":
            passed = len(extracted.allergies) > 0
            detail = (
                f"{len(extracted.allergies)} allergies documented"
                if passed
                else "No allergies documented"
            )

        case "hqo_09":
            # Timestamp check — pass if note exists (actual timing checked at API layer)
            passed = len(note_text.strip()) > 0
            detail = "Timestamp validation deferred to API layer"

        case _:
            passed = False
            detail = f"Unknown checklist item: {item_id}"

    return ChecklistItem(id=item_id, label=label, passed=passed, detail=detail)


_VAGUE_FOLLOW_UP = re.compile(
    r"(call\s+(your|the)\s+(pcp|doctor|physician)|follow\s*up\s+as\s+needed|see\s+your\s+doctor)",
    re.IGNORECASE,
)


def _has_specific_follow_up(extracted: ExtractedData) -> bool:
    if not extracted.follow_up_plan:
        return False

    return any(
        item.provider.strip()
        and item.timeframe.strip()
        and not _VAGUE_FOLLOW_UP.search(f"{item.provider} {item.timeframe}")
        for item in extracted.follow_up_plan
    )
