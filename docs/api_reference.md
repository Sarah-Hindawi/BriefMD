# BriefMD API Reference

**Version:** 0.1.0
**Generated:** 2026-03-11 17:40

Clinical intelligence for ED→PCP discharge transitions.

**Base URL:** `http://localhost:8000`

---

## Health

### `GET /api/v1/health`

**Service health check**

Returns status of data loader, agent pipeline, and overall system health.
Call this before demos to verify all services are running.

**Response:**
```json
{
  "data": {"loaded": true, "patient_count": 2000},
  "agent": {"ready": true},
  "status": "healthy"
}
```

---

## Patients

### `GET /api/v1/patients`

**List all patients**

Returns lightweight patient summaries for the dashboard selector.

**Response:** `list[PatientSummary]`

---

### `GET /api/v1/patient/{hadm_id}`

**Full patient context**

Joins all 6 dataset tables for a specific admission. Returns demographics,
discharge summary text, and counts of diagnoses, labs, and prescriptions.

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `hadm_id` | path | integer | Yes | Hospital admission ID |

**Response:** `PatientDetail`

---

### `GET /api/v1/patient/{hadm_id}/network`

**Comorbidity network**

Returns graph data (nodes, edges, clusters) for visualization.

---

## ED Quality Gate

### `GET /api/v1/ed/summaries`

**Browse discharge summaries**

Lists cases with preview text. Supports search and pagination.

**Parameters:**

| Name | In | Type | Required | Description |
|------|----|------|----------|-------------|
| `limit` | query | integer (default: `20`) | No | Max results per page |
| `offset` | query | integer (default: `0`) | No | Pagination offset |
| `search` | query | string | No | Filter by admission diagnosis keyword |

---

### `GET /api/v1/ed/summaries/{hadm_id}`

**View a specific discharge summary**

Returns full note text plus record counts so the ED doctor can gauge
completeness before running analysis.

**Response:**
```json
{
  "hadm_id": 100006,
  "subject_id": 12345,
  "discharge_summary": "...",
  "record_counts": {
    "diagnoses": 12,
    "medications": 8,
    "labs": 420
  }
}
```

---

### `POST /api/v1/ed/analyze`

**Run full quality gate pipeline**

Extraction → Verification → HQO Checklist → Flag generation → Suggestions.

**Request Body:** `EDAnalyzeRequest`
```json
{
  "patient_id": 100006,
  "note_override": null
}
```

**Response:** Full quality gate report with flags, missed diagnoses,
medication issues, HQO checklist results, and fix suggestions.

---

### `POST /api/v1/ed/checklist`

**HQO checklist only**

Quick 9-item compliance check without running the full pipeline.

**Request Body:** `EDAnalyzeRequest`

**Response:**
```json
{
  "patient_id": 100006,
  "items": [{"item": "Medication reconciliation", "passed": true}],
  "passed": 7,
  "total": 9
}
```

---

## PCP Report

### `POST /api/v1/pcp/report`

**Generate verified clinical report**

Same core pipeline as ED /analyze but formatted for the PCP: priority alerts,
actionable to-do list, monitoring plan, documentation gaps.

**Request Body:** `PCPReportRequest`
```json
{
  "patient_id": 100006
}
```

---

## RAG Chat

### `POST /api/v1/chat/ask`

**Ask a question about a patient**

RAG-powered Q&A grounded in patient data + clinical guidelines.
Used by both ED and PCP dashboards.

**Request Body:** `AskRequest`
```json
{
  "patient_id": 100006,
  "question": "Why was metformin stopped?"
}
```

**Response:** `AskResponse`
```json
{
  "patient_id": 100006,
  "question": "Why was metformin stopped?",
  "answer": "Based on the discharge note...",
  "sources": ["patient_data", "guideline"],
  "confidence": "high"
}
```

---

## Schemas

### `PatientSummary`

| Field | Type | Description |
|-------|------|-------------|
| `subject_id` | integer | Anonymized patient ID |
| `hadm_id` | integer | Hospital admission ID |
| `age` | integer | Patient age at admission |
| `gender` | string | Patient sex |
| `admission_diagnosis` | string | Diagnosis at admission |

### `PatientDetail`

Extends PatientSummary with:

| Field | Type | Description |
|-------|------|-------------|
| `discharge_summary` | string | Full discharge note text |
| `diagnosis_count` | integer | Number of coded diagnoses |
| `lab_count` | integer | Number of lab results |
| `prescription_count` | integer | Number of medications |

### `EDAnalyzeRequest`

| Field | Type | Description |
|-------|------|-------------|
| `patient_id` | integer | hadm_id of the patient |
| `note_override` | string (optional) | Custom note text to analyze instead of stored summary |

### `AskRequest`

| Field | Type | Description |
|-------|------|-------------|
| `patient_id` | integer | hadm_id to scope the answer |
| `question` | string | Natural language question |

### `AskResponse`

| Field | Type | Description |
|-------|------|-------------|
| `patient_id` | integer | hadm_id |
| `question` | string | Original question |
| `answer` | string | Generated answer grounded in context |
| `sources` | list[string] | What informed the answer |
| `confidence` | string (optional) | high / medium / low |

### `Flag`

| Field | Type | Description |
|-------|------|-------------|
| `severity` | string | critical / warning / info / monitor |
| `category` | string | medication / diagnosis / lab / documentation / follow_up |
| `title` | string | Short description |
| `detail` | string | Full explanation |
| `suggested_action` | string (optional) | What to do about it |

### `ChecklistItem`

| Field | Type | Description |
|-------|------|-------------|
| `item` | string | Checklist requirement |
| `passed` | boolean | Whether the note meets this requirement |
| `detail` | string (optional) | Evidence or explanation |