"""PCP preferences from Walke et al. (2024, PMC11169121) — 6 items. Deterministic, no LLM."""

import re

from core.models.extracted import ExtractedData
from core.models.report import ChecklistItem

PCP_PREFERENCES = [
    {"id": "pcp_01", "label": "Actionable to-do list"},
    {"id": "pcp_02", "label": "Incidental findings flagged"},
    {"id": "pcp_03", "label": "Medication change justification"},
    {"id": "pcp_04", "label": "Duration of therapy"},
    {"id": "pcp_05", "label": "No hospital-specific orders"},
    {"id": "pcp_06", "label": "Summary not day-by-day"},
]

_HOSPITAL_ORDERS = re.compile(
    r"(IV\s+(drip|infusion|push|bolus)|central\s+line|telemetry|"
    r"strict\s+I\s*&?\s*O|NPO|foley\s+catheter|restraints)",
    re.IGNORECASE,
)

_DAY_BY_DAY = re.compile(
    r"(hospital\s+day\s+#?\d|day\s+\d\s+of\s+admission|on\s+day\s+\d|"
    r"HD\s*#?\d|POD\s*#?\d)",
    re.IGNORECASE,
)


def run_pcp_preferences(extracted: ExtractedData) -> list[ChecklistItem]:
    return [_check_item(item, extracted) for item in PCP_PREFERENCES]


def _check_item(item: dict, extracted: ExtractedData) -> ChecklistItem:
    item_id = item["id"]
    label = item["label"]

    match item_id:
        case "pcp_01":
            has_pending = len(extracted.pending_tests) > 0
            has_follow_up = len(extracted.follow_up_plan) > 0
            passed = has_pending or has_follow_up
            detail = (
                "Actionable items found (pending tests/follow-ups)"
                if passed
                else "No pending labs, referrals, or follow-ups documented"
            )

        case "pcp_02":
            passed = len(extracted.lab_results_discussed) > 0
            detail = (
                f"{len(extracted.lab_results_discussed)} lab findings discussed"
                if passed
                else "No incidental or lab findings flagged for follow-up"
            )

        case "pcp_03":
            has_changes = any(
                m.change_reason.strip()
                for m in extracted.medications_discharge + extracted.medications_stopped
            )
            passed = has_changes
            detail = (
                "Medication change reasons documented"
                if passed
                else "No justification for medication changes"
            )

        case "pcp_04":
            has_duration = any(
                m.frequency.strip()
                for m in extracted.medications_discharge
            )
            passed = has_duration
            detail = (
                "Therapy duration/frequency documented"
                if passed
                else "No antibiotic end dates or therapy durations found"
            )

        case "pcp_05":
            instructions = extracted.discharge_instructions
            meds_text = " ".join(m.route for m in extracted.medications_discharge)
            combined = f"{instructions} {meds_text}"
            has_hospital_orders = bool(_HOSPITAL_ORDERS.search(combined))
            passed = not has_hospital_orders
            detail = (
                "No hospital-specific orders in discharge plan"
                if passed
                else "Hospital-specific orders found in discharge plan (e.g. IV protocols)"
            )

        case "pcp_06":
            assessment = extracted.clinical_assessment
            instructions = extracted.discharge_instructions
            combined = f"{assessment} {instructions}"
            is_day_by_day = bool(_DAY_BY_DAY.search(combined))
            passed = not is_day_by_day
            detail = (
                "Summary is a true summary, not a timeline"
                if passed
                else "Summary reads as day-by-day timeline rather than a concise summary"
            )

        case _:
            passed = False
            detail = f"Unknown preference item: {item_id}"

    return ChecklistItem(id=item_id, label=label, passed=passed, detail=detail)
