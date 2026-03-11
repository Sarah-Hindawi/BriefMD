"""Tests for Step 3: Connector (comorbidity network). No Ollama needed."""

import pandas as pd
import pytest

from core.connector import Connector
from core.models.network import ComorbidityNetwork


@pytest.fixture
def diagnosis_dict():
    return pd.DataFrame([
        {"icd9_code": "4019", "short_title": "Hypertension NOS", "long_title": "Hypertension NOS"},
        {"icd9_code": "42731", "short_title": "Atrial fibrillation", "long_title": "Atrial fibrillation"},
        {"icd9_code": "4280", "short_title": "CHF NOS", "long_title": "Congestive heart failure"},
        {"icd9_code": "25000", "short_title": "Diabetes mellitus", "long_title": "Diabetes mellitus"},
        {"icd9_code": "5849", "short_title": "Acute kidney injury", "long_title": "Acute kidney failure NOS"},
        {"icd9_code": "41401", "short_title": "Cor ath unsp vessel", "long_title": "Coronary atherosclerosis"},
        {"icd9_code": "486", "short_title": "Pneumonia", "long_title": "Pneumonia organism NOS"},
    ])


@pytest.fixture
def all_diagnoses():
    """Simulated diagnosis table for multiple patients."""
    rows = []
    # Patient 1: hypertension + afib + chf
    for code in ["4019", "42731", "4280"]:
        rows.append({"hadm_id": 100, "subject_id": 1, "icd9_code": code})
    # Patient 2: hypertension + diabetes + aki
    for code in ["4019", "25000", "5849"]:
        rows.append({"hadm_id": 200, "subject_id": 2, "icd9_code": code})
    # Patient 3: hypertension + afib + cad
    for code in ["4019", "42731", "41401"]:
        rows.append({"hadm_id": 300, "subject_id": 3, "icd9_code": code})
    # Patient 4: chf + aki
    for code in ["4280", "5849"]:
        rows.append({"hadm_id": 400, "subject_id": 4, "icd9_code": code})
    return pd.DataFrame(rows)


@pytest.fixture
def connector(all_diagnoses, diagnosis_dict):
    return Connector(all_diagnoses=all_diagnoses, diagnosis_dict=diagnosis_dict)


# ── Basic network building ──

def test_connect_returns_network(connector):
    result = connector.connect(["4019", "42731", "4280"])

    assert isinstance(result, ComorbidityNetwork)
    assert len(result.nodes) == 3
    assert len(result.edges) > 0


def test_nodes_have_labels(connector):
    result = connector.connect(["4019", "42731"])

    labels = {n.label for n in result.nodes}
    assert "Hypertension NOS" in labels
    assert "Atrial fibrillation" in labels


def test_single_code_no_edges(connector):
    result = connector.connect(["486"])

    assert len(result.nodes) == 1
    assert len(result.edges) == 0


def test_empty_codes(connector):
    result = connector.connect([])

    assert len(result.nodes) == 0
    assert len(result.edges) == 0


# ── Co-occurrence weights ──

def test_edge_weights_from_cooccurrence(connector):
    result = connector.connect(["4019", "42731"])

    assert len(result.edges) == 1
    # Hypertension + AFib appears in patients 1 and 3
    assert result.edges[0].weight == 2


# ── Dangerous edges ──

def test_identifies_dangerous_edges(connector):
    """Demo patient cluster: hypertension + afib + chf."""
    result = connector.connect(["4019", "42731", "4280"])

    assert len(result.dangerous_edges) > 0
    dangerous_pairs = {(e.source, e.target) for e in result.dangerous_edges}
    # All three pairs are in KNOWN_DANGEROUS
    assert len(dangerous_pairs) == 3


def test_dangerous_node_flagged(connector):
    result = connector.connect(["4019", "42731", "4280"])

    dangerous_nodes = {n.icd9_code for n in result.nodes if n.is_dangerous}
    assert "4019" in dangerous_nodes
    assert "42731" in dangerous_nodes
    assert "4280" in dangerous_nodes


def test_chf_aki_dangerous(connector):
    """Heart Failure + AKI is a known dangerous pair."""
    result = connector.connect(["4280", "5849"])

    assert len(result.dangerous_edges) == 1
    assert result.dangerous_edges[0].is_dangerous


def test_diabetes_aki_dangerous(connector):
    """Diabetes + AKI flags metformin risk."""
    result = connector.connect(["25000", "5849"])

    assert len(result.dangerous_edges) == 1
    assert "metformin" in result.dangerous_edges[0].description.lower()


def test_no_dangerous_edges_for_safe_pair(connector):
    """Pneumonia + diabetes is not a known dangerous pair."""
    result = connector.connect(["486", "25000"])

    assert len(result.dangerous_edges) == 0


# ── Clusters ──

def test_finds_clusters(connector):
    """Connected codes should form a cluster."""
    result = connector.connect(["4019", "42731", "4280"])

    assert len(result.clusters) >= 1
    cluster_codes = result.clusters[0].icd9_codes
    assert "4019" in cluster_codes
    assert "42731" in cluster_codes
    assert "4280" in cluster_codes


def test_cluster_has_risk_note(connector):
    result = connector.connect(["4019", "42731", "4280"])

    assert result.clusters[0].risk_note != ""


# ── Similar patients ──

def test_finds_similar_patients(connector):
    """Patient with hypertension + afib should find similar patients."""
    result = connector.connect(["4019", "42731"], hadm_id=999)

    assert len(result.similar_patients) > 0
    # Patients 1 and 3 both have hypertension + afib
    similar_hadms = {p.hadm_id for p in result.similar_patients}
    assert 100 in similar_hadms
    assert 300 in similar_hadms


def test_excludes_self_from_similar(connector):
    result = connector.connect(["4019", "42731", "4280"], hadm_id=100)

    similar_hadms = {p.hadm_id for p in result.similar_patients}
    assert 100 not in similar_hadms


def test_similar_patients_sorted_by_score(connector):
    result = connector.connect(["4019", "42731", "4280"], hadm_id=999)

    scores = [p.similarity_score for p in result.similar_patients]
    assert scores == sorted(scores, reverse=True)


# ── Edge cases ──

def test_empty_diagnoses_table(diagnosis_dict):
    empty = pd.DataFrame(columns=["hadm_id", "subject_id", "icd9_code"])
    connector = Connector(all_diagnoses=empty, diagnosis_dict=diagnosis_dict)

    result = connector.connect(["4019", "42731"])

    assert isinstance(result, ComorbidityNetwork)
    assert len(result.edges) == 0
    assert len(result.similar_patients) == 0
