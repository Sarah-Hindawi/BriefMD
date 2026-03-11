"""Tests for Step 2: Verifier. Must test: Avandia+CHF, phenytoin+coumadin.
No Ollama needed — verifier is fully deterministic."""

import pandas as pd
import pytest

from core.models.extracted import ExtractedData, MedicationItem, FollowUpItem
from core.models.flags import Severity
from core.verifier import Verifier


@pytest.fixture
def verifier():
    return Verifier()


@pytest.fixture
def empty_labs():
    return pd.DataFrame(columns=["hadm_id", "itemid", "value", "unit"])


@pytest.fixture
def empty_prescriptions():
    return pd.DataFrame(columns=["hadm_id", "drug", "dose_value", "dose_unit"])


def _make_diagnoses(codes: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"hadm_id": 1, "icd9_code": code, "short_title": title} for code, title in codes]
    )


def _make_prescriptions(drugs: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"hadm_id": 1, "drug": drug, "dose_value": "1", "dose_unit": "mg"} for drug in drugs]
    )


def _make_extracted(
    diagnoses: list[str] | None = None,
    meds: list[str] | None = None,
    allergies: list[str] | None = None,
    follow_ups: list[FollowUpItem] | None = None,
    lab_results: list[str] | None = None,
) -> ExtractedData:
    return ExtractedData(
        chief_complaint="test",
        diagnoses_mentioned=diagnoses or [],
        medications_discharge=[
            MedicationItem(name=m) for m in (meds or [])
        ],
        allergies=allergies or [],
        follow_up_plan=follow_ups or [],
        lab_results_discussed=lab_results or [],
    )


# ── Demo patient showstopper: Avandia + CHF ──

def test_catches_avandia_chf(verifier, empty_labs):
    """FDA black box: rosiglitazone (Avandia) + heart failure. MUST always pass."""
    extracted = _make_extracted(
        diagnoses=["heart failure", "diabetes"],
        meds=["avandia"],
    )
    diagnoses = _make_diagnoses([("4280", "Heart failure"), ("25000", "Diabetes")])
    prescriptions = _make_prescriptions(["avandia"])

    flags = verifier.verify(extracted, diagnoses, empty_labs, prescriptions)

    assert len(flags.contraindications) > 0
    ci = flags.contraindications[0]
    assert "heart failure" in ci.condition
    assert ci.severity_label == "FDA black box"


def test_catches_rosiglitazone_chf(verifier, empty_labs):
    """Same check with generic name instead of brand."""
    extracted = _make_extracted(meds=["rosiglitazone"])
    diagnoses = _make_diagnoses([("4280", "Heart failure")])
    prescriptions = _make_prescriptions(["rosiglitazone"])

    flags = verifier.verify(extracted, diagnoses, empty_labs, prescriptions)

    assert len(flags.contraindications) > 0
    assert flags.has_critical


# ── Demo patient showstopper: Phenytoin + Coumadin ──

def test_catches_phenytoin_coumadin(verifier, empty_labs):
    """Drug-drug interaction: phenytoin displaces warfarin. MUST always pass."""
    extracted = _make_extracted(meds=["phenytoin", "coumadin"])
    diagnoses = _make_diagnoses([("4280", "Heart failure")])
    prescriptions = _make_prescriptions(["phenytoin", "coumadin"])

    flags = verifier.verify(extracted, diagnoses, empty_labs, prescriptions)

    assert len(flags.drug_interactions) > 0
    di = flags.drug_interactions[0]
    assert "phenytoin" in di.drug_a or "phenytoin" in di.drug_b
    assert "coumadin" in di.drug_a or "coumadin" in di.drug_b


def test_catches_dilantin_warfarin(verifier, empty_labs):
    """Same interaction with alternate drug names."""
    extracted = _make_extracted(meds=["dilantin", "warfarin"])
    diagnoses = _make_diagnoses([])
    prescriptions = _make_prescriptions(["dilantin", "warfarin"])

    flags = verifier.verify(extracted, diagnoses, empty_labs, prescriptions)

    assert len(flags.drug_interactions) > 0


# ── Metformin + AKI ──

def test_catches_metformin_aki(verifier, empty_labs):
    """Metformin contraindicated in acute kidney injury."""
    extracted = _make_extracted(meds=["metformin"])
    diagnoses = _make_diagnoses([("5849", "Acute kidney injury")])
    prescriptions = _make_prescriptions(["metformin"])

    flags = verifier.verify(extracted, diagnoses, empty_labs, prescriptions)

    assert len(flags.contraindications) > 0
    assert flags.contraindications[0].severity_label == "contraindicated"


# ── Diagnosis gaps ──

def test_finds_diagnosis_gaps(verifier, empty_labs, empty_prescriptions):
    """Coded diagnoses not mentioned in note should be flagged."""
    extracted = _make_extracted(diagnoses=["pneumonia"])
    diagnoses = _make_diagnoses([
        ("486", "Pneumonia"),
        ("4280", "Heart failure"),
        ("25000", "Diabetes"),
        ("42731", "Atrial fibrillation"),
    ])

    flags = verifier.verify(extracted, diagnoses, empty_labs, empty_prescriptions)

    assert len(flags.diagnosis_gaps) >= 3
    gap_names = [g.diagnosis.lower() for g in flags.diagnosis_gaps]
    assert any("heart failure" in n for n in gap_names)
    assert any("diabetes" in n for n in gap_names)


def test_no_gaps_when_all_mentioned(verifier, empty_labs, empty_prescriptions):
    """No gaps when all coded diagnoses are mentioned in note."""
    extracted = _make_extracted(diagnoses=["heart failure", "diabetes"])
    diagnoses = _make_diagnoses([("4280", "Heart failure"), ("25000", "Diabetes")])

    flags = verifier.verify(extracted, diagnoses, empty_labs, empty_prescriptions)

    assert len(flags.diagnosis_gaps) == 0


# ── Follow-up checks ──

def test_flags_missing_follow_up(verifier, empty_labs, empty_prescriptions):
    extracted = _make_extracted()
    diagnoses = _make_diagnoses([])

    flags = verifier.verify(extracted, diagnoses, empty_labs, empty_prescriptions)

    follow_up_flags = [f for f in flags.flags if f.category == "follow-up"]
    assert len(follow_up_flags) > 0


def test_flags_vague_follow_up(verifier, empty_labs, empty_prescriptions):
    extracted = _make_extracted(
        follow_ups=[FollowUpItem(provider="", timeframe="", reason="general")]
    )
    diagnoses = _make_diagnoses([])

    flags = verifier.verify(extracted, diagnoses, empty_labs, empty_prescriptions)

    follow_up_flags = [f for f in flags.flags if f.category == "follow-up"]
    assert len(follow_up_flags) > 0


# ── Allergy checks ──

def test_flags_missing_allergies(verifier, empty_labs, empty_prescriptions):
    extracted = _make_extracted(allergies=[])
    diagnoses = _make_diagnoses([])

    flags = verifier.verify(extracted, diagnoses, empty_labs, empty_prescriptions)

    allergy_flags = [f for f in flags.flags if f.category == "allergies"]
    assert len(allergy_flags) > 0


def test_no_allergy_flag_when_documented(verifier, empty_labs, empty_prescriptions):
    extracted = _make_extracted(allergies=["penicillin"])
    diagnoses = _make_diagnoses([])

    flags = verifier.verify(extracted, diagnoses, empty_labs, empty_prescriptions)

    allergy_flags = [f for f in flags.flags if f.category == "allergies"]
    assert len(allergy_flags) == 0


# ── No false positives ──

def test_no_contraindication_without_matching_diagnosis(verifier, empty_labs):
    """Avandia without CHF should NOT flag."""
    extracted = _make_extracted(meds=["avandia"])
    diagnoses = _make_diagnoses([("25000", "Diabetes")])
    prescriptions = _make_prescriptions(["avandia"])

    flags = verifier.verify(extracted, diagnoses, empty_labs, prescriptions)

    assert len(flags.contraindications) == 0


def test_no_interaction_with_single_drug(verifier, empty_labs):
    """Phenytoin alone should NOT flag drug interaction."""
    extracted = _make_extracted(meds=["phenytoin"])
    diagnoses = _make_diagnoses([])
    prescriptions = _make_prescriptions(["phenytoin"])

    flags = verifier.verify(extracted, diagnoses, empty_labs, prescriptions)

    assert len(flags.drug_interactions) == 0
