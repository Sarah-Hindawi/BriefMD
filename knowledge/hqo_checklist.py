"""
Ontario HQO Quality Standard: Transitions Between Hospital and Home
===================================================================
Source: Ontario Health (Quality), "Transitions Between Hospital and Home:
        Care for People of All Ages" — Quality Standard (2020)
        ISBN 978-1-4868-3854-7

10 Quality Statements. Deterministic checks — no LLM needed.

IMPORTANT: Some statements CANNOT be fully verified from discharge note text alone
(e.g., QS3: Patient/Family Involvement, QS10: Out-of-Pocket Costs). For these,
we flag them as REMINDERS rather than pass/fail. This is clinically honest.
"""

import re
from core.models.extracted import ExtractedData
from core.models.report import ChecklistItem


# ---------------------------------------------------------------------------
# The 10 Quality Statements from the official HQO document
# ---------------------------------------------------------------------------

HQO_CHECKLIST = [
    {
        "id": "hqo_01",
        "label": "Information-Sharing on Admission",
        "hqo_ref": "Quality Statement 1",
        "summary": (
            "Hospital shares admission info with primary care and "
            "community providers via real-time electronic notification."
        ),
        "checkable": True,
    },
    {
        "id": "hqo_02",
        "label": "Comprehensive Assessment",
        "hqo_ref": "Quality Statement 2",
        "summary": (
            "Patient receives comprehensive assessment of health care "
            "and social support needs, started early on admission."
        ),
        "checkable": True,
    },
    {
        "id": "hqo_03",
        "label": "Patient/Family/Caregiver Involvement",
        "hqo_ref": "Quality Statement 3",
        "summary": (
            "Patient is involved in transition planning. Family and "
            "caregivers involved if patient consents."
        ),
        "checkable": False,  # Cannot verify from note text alone
    },
    {
        "id": "hqo_04",
        "label": "Patient/Family Education, Training & Support",
        "hqo_ref": "Quality Statement 4",
        "summary": (
            "Patient and caregivers have information and support to "
            "manage health care needs at home. Includes warning signs, "
            "medications, follow-up appointments, community resources."
        ),
        "checkable": True,
    },
    {
        "id": "hqo_05",
        "label": "Transition Plan",
        "hqo_ref": "Quality Statement 5",
        "summary": (
            "Written transition plan developed in partnership with "
            "patient, caregivers, hospital team, and community providers. "
            "Shared within 48 hours of discharge."
        ),
        "checkable": True,
    },
    {
        "id": "hqo_06",
        "label": "Coordinated Transitions",
        "hqo_ref": "Quality Statement 6",
        "summary": (
            "A named health care professional is responsible for "
            "transition planning, coordination, and communication."
        ),
        "checkable": True,  # Can check if a coordinator name appears
    },
    {
        "id": "hqo_07",
        "label": "Medication Review & Support",
        "hqo_ref": "Quality Statement 7",
        "summary": (
            "Medication reviews on admission, before discharge, and "
            "once home. Includes reconciliation, adherence, optimization, "
            "and affordability consideration."
        ),
        "checkable": True,
    },
    {
        "id": "hqo_08",
        "label": "Coordinated Follow-Up Medical Care",
        "hqo_ref": "Quality Statement 8",
        "summary": (
            "Follow-up medical care with primary care provider and/or "
            "specialist coordinated and booked before leaving hospital."
        ),
        "checkable": True,
    },
    {
        "id": "hqo_09",
        "label": "Home & Community Care Support",
        "hqo_ref": "Quality Statement 9",
        "summary": (
            "Patient assessed for type, amount, and timing of home care "
            "and community support services. Services arranged before discharge."
        ),
        "checkable": True,  # Partial — check if home care is mentioned
    },
    {
        "id": "hqo_10",
        "label": "Out-of-Pocket Costs & Limits of Funded Services",
        "hqo_ref": "Quality Statement 10",
        "summary": (
            "Patient's ability to pay for out-of-pocket health care "
            "costs considered. Information and alternatives for "
            "unaffordable costs included in transition plan."
        ),
        "checkable": False,  # Rarely documented in discharge summaries
    },
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_hqo_checklist(
    extracted: ExtractedData,
    note_text: str,
) -> list[ChecklistItem]:
    """
    Run all 10 HQO Quality Statement checks against extracted data.

    Returns a ChecklistItem for each statement. Items that cannot be
    verified from note text are flagged as reminders (passed=False)
    with an explanatory detail.
    """
    return [_check_item(item, extracted, note_text) for item in HQO_CHECKLIST]


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

# Regex patterns used across checks
_VAGUE_FOLLOW_UP = re.compile(
    r"(call\s+(your|the)\s+(pcp|doctor|physician)"
    r"|follow\s*[-\s]?up\s+as\s+needed"
    r"|see\s+your\s+doctor)",
    re.IGNORECASE,
)

_HOME_CARE_KEYWORDS = re.compile(
    r"(home\s*(care|health|nursing|services)"
    r"|community\s*(care|support|services)"
    r"|visiting\s+nurse"
    r"|home\s+oxygen"
    r"|dme\b"
    r"|durable\s+medical\s+equipment"
    r"|physical\s+therapy\s+at\s+home"
    r"|VNA\b)",
    re.IGNORECASE,
)

_COST_KEYWORDS = re.compile(
    r"(cost|afford|insurance|coverage|out[-\s]of[-\s]pocket"
    r"|financial|copay|co-pay|trillium|ODB|ontario\s+drug\s+benefit"
    r"|assistance\s+program)",
    re.IGNORECASE,
)

_COORDINATOR_KEYWORDS = re.compile(
    r"(care\s+coordinator|discharge\s+coordinator|transition\s+coordinator"
    r"|case\s+manager|patient\s+navigator|social\s+worker"
    r"|discharge\s+planner)",
    re.IGNORECASE,
)

_WARNING_SIGNS_KEYWORDS = re.compile(
    r"(return\s+to\s+(the\s+)?(ed|er|emergency)"
    r"|warning\s+signs?"
    r"|seek\s+(immediate\s+)?(medical\s+)?attention"
    r"|call\s+911"
    r"|danger\s+signs?"
    r"|if\s+you\s+experience)",
    re.IGNORECASE,
)


def _check_item(
    item: dict,
    extracted: ExtractedData,
    note_text: str,
) -> ChecklistItem:
    item_id = item["id"]
    label = item["label"]
    checkable = item["checkable"]

    match item_id:

        # QS1: Information-Sharing on Admission
        # Check: Is PCP identified? Is there a discharge summary at all?
        case "hqo_01":
            has_pcp = bool(extracted.pcp_name and extracted.pcp_name.strip())
            has_note = len(note_text.strip()) > 0
            passed = has_pcp and has_note
            if not has_note:
                detail = "No discharge summary text found"
            elif not has_pcp:
                detail = "No primary care provider identified in note"
            else:
                detail = f"PCP identified: {extracted.pcp_name}"

        # QS2: Comprehensive Assessment
        # Check: Are diagnoses, meds, and key clinical info documented?
        case "hqo_02":
            has_dx = len(extracted.diagnoses_mentioned) > 0
            has_assessment = bool(
                extracted.clinical_assessment
                and extracted.clinical_assessment.strip()
            )
            passed = has_dx and has_assessment
            if not has_dx:
                detail = "No diagnoses documented in note"
            elif not has_assessment:
                detail = (
                    f"{len(extracted.diagnoses_mentioned)} diagnoses found "
                    "but no clinical assessment narrative"
                )
            else:
                detail = (
                    f"{len(extracted.diagnoses_mentioned)} diagnoses documented "
                    "with clinical assessment"
                )

        # QS3: Patient/Family/Caregiver Involvement
        # CANNOT verify from text — flag as reminder
        case "hqo_03":
            passed = False
            detail = (
                "Cannot verify from discharge note text. "
                "Reminder: document that patient/family were involved "
                "in transition planning decisions."
            )

        # QS4: Patient/Family Education, Training & Support
        # Check: Are discharge instructions present? Warning signs included?
        case "hqo_04":
            has_instructions = bool(
                extracted.discharge_instructions
                and extracted.discharge_instructions.strip()
            )
            has_warning_signs = bool(_WARNING_SIGNS_KEYWORDS.search(note_text))
            passed = has_instructions and has_warning_signs
            if not has_instructions:
                detail = "No discharge instructions found"
            elif not has_warning_signs:
                detail = (
                    "Discharge instructions present but no warning signs "
                    "or 'return to ED if...' guidance found"
                )
            else:
                detail = (
                    "Discharge instructions with warning signs documented"
                )

        # QS5: Transition Plan
        # Check: Is there a plan with medications, follow-up, and instructions?
        case "hqo_05":
            has_meds = len(extracted.medications_discharge) > 0
            has_follow_up = _has_specific_follow_up(extracted)
            has_instructions = bool(
                extracted.discharge_instructions
                and extracted.discharge_instructions.strip()
            )
            passed = has_meds and has_follow_up
            missing = []
            if not has_meds:
                missing.append("medication list")
            if not has_follow_up:
                missing.append("specific follow-up plan")
            if not has_instructions:
                missing.append("discharge instructions")
            if passed:
                detail = "Transition plan includes medications and follow-up"
            else:
                detail = f"Incomplete transition plan — missing: {', '.join(missing)}"

        # QS6: Coordinated Transitions
        # Check: Is a named coordinator/case manager documented?
        case "hqo_06":
            has_coordinator = bool(_COORDINATOR_KEYWORDS.search(note_text))
            passed = has_coordinator
            detail = (
                "Transition coordinator role referenced in note"
                if passed
                else "No named transition coordinator or case manager documented"
            )

        # QS7: Medication Review & Support
        # Check: Are medications listed with changes documented?
        case "hqo_07":
            has_meds = len(extracted.medications_discharge) > 0
            has_changes = any(
                m.is_new or m.is_changed or m.is_stopped
                for m in extracted.medications_discharge
            ) or len(extracted.medications_stopped) > 0
            passed = has_meds and has_changes
            if not has_meds:
                detail = "No medications listed"
            elif not has_changes:
                detail = (
                    "Medications listed but no changes documented "
                    "(new, changed, or stopped medications not identified)"
                )
            else:
                new_count = sum(
                    1 for m in extracted.medications_discharge if m.is_new
                )
                stopped_count = len(extracted.medications_stopped) + sum(
                    1 for m in extracted.medications_discharge if m.is_stopped
                )
                changed_count = sum(
                    1 for m in extracted.medications_discharge if m.is_changed
                )
                detail = (
                    f"Medication reconciliation: {new_count} new, "
                    f"{changed_count} changed, {stopped_count} stopped"
                )

        # QS8: Coordinated Follow-Up Medical Care
        # Check: Is follow-up booked with a named provider and timeframe?
        case "hqo_08":
            passed = _has_specific_follow_up(extracted)
            detail = (
                "Specific follow-up care coordinated with provider and timeframe"
                if passed
                else (
                    "Follow-up plan missing or vague — "
                    "no specific provider and timeframe documented"
                )
            )

        # QS9: Home & Community Care Support
        # Check: Is home care mentioned or assessed?
        case "hqo_09":
            has_home_care = bool(_HOME_CARE_KEYWORDS.search(note_text))
            passed = has_home_care
            detail = (
                "Home/community care services referenced in note"
                if passed
                else "No home or community care assessment documented"
            )

        # QS10: Out-of-Pocket Costs
        # Rarely documented in clinical notes — flag as reminder
        case "hqo_10":
            has_cost_mention = bool(_COST_KEYWORDS.search(note_text))
            passed = has_cost_mention
            detail = (
                "Cost/coverage considerations mentioned in note"
                if passed
                else (
                    "No discussion of medication costs or insurance coverage. "
                    "Reminder: assess patient's ability to afford out-of-pocket costs."
                )
            )

        case _:
            passed = False
            detail = f"Unknown checklist item: {item_id}"

    return ChecklistItem(
        id=item_id,
        label=label,
        passed=passed,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_specific_follow_up(extracted: ExtractedData) -> bool:
    """
    Check if there's a SPECIFIC follow-up plan — not just "see your doctor."

    A specific follow-up has:
    - A named provider or specialty
    - A concrete timeframe (not "as needed")
    """
    if not extracted.follow_up_plan:
        return False

    return any(
        item.provider.strip()
        and item.timeframe.strip()
        and not _VAGUE_FOLLOW_UP.search(f"{item.provider} {item.timeframe}")
        for item in extracted.follow_up_plan
    )