"""Tests for Step 1: Extractor. Must work without Ollama running — mock the LLM."""

import json
from unittest.mock import MagicMock

import pytest

from core.extractor import Extractor
from core.llm_client import LLMClient
from core.models.extracted import ExtractedData


@pytest.fixture
def mock_llm():
    return MagicMock(spec=LLMClient)


@pytest.fixture
def extractor(mock_llm):
    return Extractor(llm_client=mock_llm)


VALID_JSON = json.dumps({
    "chief_complaint": "pneumonia",
    "admission_diagnosis": "pneumosepsis",
    "discharge_diagnosis": "pneumonia with sepsis",
    "diagnoses_mentioned": ["pneumonia", "sepsis", "heart failure", "diabetes"],
    "allergies": ["penicillin"],
    "medications_discharge": [
        {"name": "avandia", "dose": "4mg", "route": "oral", "frequency": "daily",
         "is_new": False, "is_changed": False, "is_stopped": False, "change_reason": ""},
        {"name": "coumadin", "dose": "5mg", "route": "oral", "frequency": "daily",
         "is_new": False, "is_changed": False, "is_stopped": False, "change_reason": ""},
    ],
    "medications_stopped": [],
    "lab_results_discussed": ["INR 7.0"],
    "pending_tests": [{"test_name": "blood culture", "reason": "pending at discharge"}],
    "follow_up_plan": [
        {"provider": "Dr. Smith", "specialty": "cardiology", "timeframe": "2 weeks", "reason": "CHF follow-up"}
    ],
    "pcp_name": "Dr. Jones",
    "discharge_instructions": "Take medications as prescribed. Return if fever returns.",
    "clinical_assessment": "Improving pneumonia, stable CHF.",
})


def test_extract_valid_json(extractor, mock_llm):
    mock_llm.generate_json.return_value = json.loads(VALID_JSON)

    result = extractor.extract("Sample discharge note text")

    assert isinstance(result, ExtractedData)
    assert result.chief_complaint == "pneumonia"
    assert len(result.diagnoses_mentioned) == 4
    assert len(result.medications_discharge) == 2
    assert result.allergies == ["penicillin"]
    assert result.pcp_name == "Dr. Jones"
    assert len(result.follow_up_plan) == 1
    assert result.follow_up_plan[0].timeframe == "2 weeks"


def test_extract_json_none_falls_back_to_regex(extractor, mock_llm):
    mock_llm.generate_json.return_value = None
    mock_llm.generate.return_value = '"chief_complaint": "chest pain", "allergies": ["sulfa", "codeine"]'

    result = extractor.extract("Sample discharge note text")

    assert isinstance(result, ExtractedData)
    assert result.chief_complaint == "chest pain"
    assert "sulfa" in result.allergies


def test_extract_invalid_pydantic_falls_back(extractor, mock_llm):
    mock_llm.generate_json.return_value = {"chief_complaint": 12345, "medications_discharge": "not a list"}

    result = extractor.extract("Sample discharge note text")

    assert isinstance(result, ExtractedData)


def test_extract_empty_note(extractor, mock_llm):
    mock_llm.generate_json.return_value = {}

    result = extractor.extract("")

    assert isinstance(result, ExtractedData)
    assert result.chief_complaint == ""
    assert result.diagnoses_mentioned == []


def test_extract_preserves_medication_flags(extractor, mock_llm):
    mock_llm.generate_json.return_value = {
        "medications_discharge": [
            {"name": "metformin", "dose": "500mg", "route": "oral",
             "frequency": "bid", "is_new": True, "is_changed": False,
             "is_stopped": False, "change_reason": "new diabetes dx"},
        ],
        "medications_stopped": [
            {"name": "glyburide", "dose": "5mg", "change_reason": "switched to metformin"},
        ],
    }

    result = extractor.extract("Sample note")

    assert result.medications_discharge[0].is_new is True
    assert result.medications_discharge[0].change_reason == "new diabetes dx"
    assert result.medications_stopped[0].name == "glyburide"
