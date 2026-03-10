# CLAUDE.md — BriefMD Codebase Guide

> This file tells Claude Code everything it needs to generate code for this project.
> Read this FIRST before writing any code.

---

## What This Project Is

BriefMD (Clinical Intelligence & Quality) is a **dual-sided clinical decision-support tool** that verifies hospital discharge summaries against structured patient data.

**Two users:**

- **Side A — ED Doctor**: Quality gate that checks the discharge note BEFORE it leaves the hospital. Runs HQO checklist, catches contraindications, flags missing sections, suggests fixes.
- **Side B — PCP (Primary Care Physician)**: Verified report showing what's wrong, missing, and dangerous AFTER the note arrives. Includes actionable to-do list, comorbidity network, and follow-up Q&A.

**One agent, three steps:** Extract → Verify → Connect. Sequential pipeline. Only Step 1 needs the LLM. Steps 2 and 3 are deterministic Python.

**Hackathon project** for the U of T Healthcare AI Hackathon (March 2026). Dataset is MIMIC-III with 2,000 patients from HuggingFace.

---

## Tech Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| Language | Python 3.11 | |
| LLM | **Mistral 7B Instruct** via Ollama | Local only. No cloud APIs. |
| API | FastAPI | Async endpoints |
| Frontend | Streamlit | Two dashboards (ED + PCP) |
| Graph | NetworkX | Comorbidity network |
| Data | Pandas | 6 CSVs from HuggingFace |
| Validation | Pydantic v2 | All models |
| Container | Docker + docker-compose | 4 services |
| Viz | Plotly | Network graph rendering |

### What We Do NOT Use

| Technology | Why Not |
|-----------|---------|
| **ChromaDB** | Dropped. We have ~10 guidelines, not hundreds. Hardcoded checklist logic is more reliable than vector search for this scale. |
| **RAG** | Dropped. Mistral 7B already knows clinical pharmacology. Patient-specific answers come from feeding patient data into the prompt, not retrieval. |
| **OpenAI / Gemini / Groq** | No cloud LLM APIs. Everything runs locally via Ollama. |
| **Embeddings** | No embedding model needed. No vector similarity search. |

---

## LLM — Mistral 7B Instruct via Ollama

### Setup

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull mistral:7b-instruct
ollama list  # verify
```

### How to Call It

```python
import httpx

def call_mistral(prompt: str, system: str = None) -> str:
    full_prompt = f"[INST] {system}\n\n{prompt} [/INST]" if system else f"[INST] {prompt} [/INST]"
    
    response = httpx.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "mistral:7b-instruct",
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 4096,
                "top_p": 0.9,
            }
        },
        timeout=120.0
    )
    return response.json().get("response", "")
```

### Mistral 7B Constraints

- **Context window: ~8K tokens.** Discharge summaries average ~2,100 tokens. Leaves ~5,900 for prompt + response. Budget carefully.
- **Prompt format:** Always `[INST] ... [/INST]`. Added by `LLMClient`, not in prompt templates.
- **JSON output is unreliable.** ALWAYS validate with try/except. Use `generate_json()` method which strips markdown fences and regex-extracts JSON objects.
- **Temperature:** 0.1 for extraction (reliability), 0.7 for Q&A (fluency).
- **Keep prompts short.** No room for lengthy few-shot examples.

### Where the LLM Is Used (and Where It Isn't)

| Component | Uses LLM? | Why |
|-----------|----------|-----|
| Step 1: Extract | **Yes** | Reads unstructured text, outputs structured JSON |
| Step 2: Verify | **No** | Python compares JSON vs pandas DataFrames |
| Step 3: Connect | **No** | NetworkX builds graph from ICD9 codes |
| HQO Checklist | **No** | Deterministic field checks |
| PCP Preferences | **No** | Deterministic field checks |
| Drug-disease pairs | **No** | Hardcoded lookup in verifier.py |
| PCP Q&A ("Ask") | **Yes** | Patient data + question → Mistral answers |

**Design principle:** Minimize LLM dependency. Only use Mistral where unstructured text understanding is required. Everything else is deterministic Python — faster, cheaper, and always correct.

---

## Project Structure

```
cliniq/
├── CLAUDE.md                    ← YOU ARE HERE
├── README.md                    
├── docker-compose.yml           # 4 services: ollama, api, ed-dashboard, pcp-dashboard
├── .env                         # Local config (gitignored)
├── .env.example                
├── .dockerignore               
├── .gitignore                  
├── Makefile                    
├── requirements.txt            
│
├── core/                        # 🧠 Agent pipeline
│   ├── agent.py                 # Orchestrator: run(), run_ed_check(), run_pcp_report(), ask()
│   ├── extractor.py             # Step 1: LLM reads note → structured JSON
│   ├── verifier.py              # Step 2: Cross-reference JSON vs data + drug-disease pairs
│   ├── connector.py             # Step 3: Build comorbidity network with NetworkX
│   ├── llm_client.py            # Mistral 7B via Ollama (only LLM interface in the project)
│   ├── prompts/
│   │   └── extract_prompt.py    # Extraction prompt optimized for Mistral 7B
│   ├── models/
│   │   ├── extracted.py         # Pydantic: ExtractedData (Step 1 output)
│   │   ├── flags.py             # Pydantic: VerificationFlags (Step 2 output)
│   │   ├── network.py           # Pydantic: ComorbidityNetwork (Step 3 output)
│   │   └── report.py            # Pydantic: FullReport, EDReport, PCPReport
│   └── tests/
│       ├── test_extractor.py
│       ├── test_verifier.py     # Must test: Avandia+CHF, phenytoin+coumadin
│       └── test_connector.py
│
├── data/                        # 📊 HuggingFace dataset (6 CSVs)
│   ├── loader.py                # Load CSVs into pandas DataFrames
│   ├── patient_context.py       # get_patient_context(subject_id) — joins all 6 tables
│   ├── comorbidity.py           # Co-occurrence matrix + similar patient finder
│   └── datasets/                # CSV files (gitignored, volume-mounted in Docker)
│       └── README.md            # Download instructions
│
├── checks/                      # ✅ Deterministic compliance checks (no LLM, no vector DB)
│   ├── hqo_checklist.py         # Ontario HQO Safe Discharge Practices (9 items)
│   └── pcp_preferences.py       # PMC PCP recommendations (6 items)
│
├── api/                         # 🔌 FastAPI gateway
│   ├── main.py                  # App setup, CORS, health endpoint
│   ├── dependencies.py          # Singleton agent + data service
│   ├── routers/
│   │   ├── ed.py                # /api/v1/ed/* — ED doctor endpoints
│   │   ├── pcp.py               # /api/v1/pcp/* — PCP endpoints
│   │   └── patients.py          # /api/v1/patient/* — shared patient data
│   └── schemas/                 # Request/response Pydantic schemas
│
├── frontend/                    # 🖥️ Streamlit dashboards
│   ├── ed_dashboard.py          # Side A — ED quality gate
│   ├── pcp_dashboard.py         # Side B — PCP verified report
│   └── components/
│       ├── patient_selector.py  # Shared patient dropdown
│       ├── flag_cards.py        # Red/yellow/orange flag display
│       ├── comorbidity_graph.py # NetworkX → Plotly visualization
│       ├── checklist_display.py # HQO checklist pass/fail view
│       ├── todo_list.py         # Actionable to-do list for PCP
│       └── chat_box.py          # Q&A interface (Mistral answers directly)
│
├── scripts/
│   ├── load_data.py             # Download 6 CSVs from HuggingFace
│   └── find_demo_patient.py     # Pre-cache demo patient results
│
├── config/
│   ├── settings.py              # Pydantic settings from .env
│   └── logging.py               # Logging config
│
└── docker/
    ├── Dockerfile.api           # API service (multi-stage build)
    └── Dockerfile.frontend      # Streamlit service
```



## How the Agent Pipeline Works

```
Discharge Summary (text) + 5 Structured Tables (CSVs)
                    │
                    ▼
            ┌──────────────────────────────┐
            │         BriefMD Agent          │
            │                               │
            │  Step 1: EXTRACT              │
            │  └─ LLM (Mistral 7B)         │
            │     Reads note → JSON         │
            │         │                     │
            │         ▼                     │
            │  Step 2: VERIFY               │
            │  └─ Python (no LLM)           │
            │     JSON vs diagnoses table   │
            │     JSON vs labs table         │
            │     JSON vs prescriptions     │
            │     Drug-disease pairs check  │
            │         │                     │
            │         ▼                     │
            │  Step 3: CONNECT              │
            │  └─ NetworkX (no LLM)         │
            │     Build comorbidity graph   │
            │     Find dangerous edges      │
            │     Find similar patients     │
            └──────────────┬───────────────┘
                           │
                           ▼
            Flags + Gaps + Network + To-Do List
                           │
            ┌──────────────┼──────────────┐
            ▼                             ▼
     Side A: ED Report              Side B: PCP Report
     + HQO checklist                + Actionable to-do
     + Fix suggestions            + Comorbidity graph
     +Comorbidity graphs            + Q&A (Mistral)
```
Comorbidity graph required in ED Report as well because for instance a septic shock is treated differently for a patient with diabities and someone without diabetes
---

## The Dataset (HuggingFace)

**Repo:** `bavehackathon/2026-healthcare-ai`

6 CSV files, relational structure. `hadm_id` is the primary join key.

| File | Records | Key Columns | Join Key |
|------|---------|-------------|----------|
| `clinical_cases.csv.gz` | 2,000 | case_id, subject_id, hadm_id, age, gender, admission_diagnosis, discharge_summary | hadm_id |
| `diagnoses_subset.csv.gz` | ~23,000 | subject_id, hadm_id, seq_num, icd9_code | hadm_id, icd9_code |
| `diagnosis_dictionary.csv.gz` | ~14,000 | icd9_code, short_title, long_title | icd9_code |
| `labs_subset.csv.gz` | 841,507 | hadm_id, itemid, charttime, value, unit | hadm_id, itemid |
| `lab_dictionary.csv.gz` | ~700 | itemid, lab_name, fluid, category | itemid |
| `prescriptions_subset.csv.gz` | varies | subject_id, hadm_id, drug, dose_value, dose_unit, route, startdate, enddate | hadm_id |

**Loading data:**

```python
from huggingface_hub import hf_hub_download
import pandas as pd

repo_id = "bavehackathon/2026-healthcare-ai"
clinical_cases = pd.read_csv(
    hf_hub_download(repo_id=repo_id, filename="clinical_cases.csv.gz", repo_type="dataset")
)
```

**Key stats from EDA:**
- 2,000 cases, 1,968 unique patients
- Average 11.8 diagnoses per patient (98% have 3+)
- Average 420 lab results per admission
- Discharge summaries: avg 1,560 words
- 64% missing follow-up plan
- 81% don't discuss lab results
- 92% no clinical assessment section

---

## Demo Patient

79-year-old female admitted with pneumosepsis. Use to find: patients with most diagnoses + dangerous interactions + documented allergies.

**Findings ClinIQ must catch:**

1. **Avandia (rosiglitazone) + CHF** — FDA black box. Drug on discharge list, patient has heart failure. NOT flagged in note.
2. **Phenytoin + Coumadin** — Drug interaction. INR spiked to 7.0.
3. **Vague follow-up:** "Call and schedule an appointment with your PCP" — no date, no name.
4. **4 coded diagnoses** not mentioned anywhere in the note.
5. **Cardiometabolic-renal cluster:** Hypertension + AFib + CHF + AKI + Diabetes.

If any code change breaks these 5 findings, the demo is dead. Always test against this patient.

---

## Deterministic Checks (checks/ folder)

### HQO Checklist — 9 Items

Ontario Safe Discharge Practices. Each is a pass/fail check on extracted data. No LLM.

| ID | Item | How to Check |
|----|------|-------------|
| hqo_01 | Discharge summary completed | Is raw text present? |
| hqo_02 | Diagnosis documented | Are diagnoses in the note text? |
| hqo_03 | Medication reconciliation | Are meds listed with changes? |
| hqo_04 | Follow-up plan specified | Specific date/doctor/clinic? "Call your PCP" = FAIL |
| hqo_05 | Pending tests documented | Any outstanding labs identified? |
| hqo_06 | Patient education provided | Discharge instructions present? |
| hqo_07 | PCP identified | PCP name/contact in note? |
| hqo_08 | Allergies documented | Allergies listed? |
| hqo_09 | Summary sent within 48h | Timestamp check |

### PCP Preferences — 6 Items

From Walke et al. (2024, PMC11169121). What PCPs actually want.

| ID | Item | Description |
|----|------|-------------|
| pcp_01 | Actionable to-do list | Pending labs, referrals, follow-ups |
| pcp_02 | Incidental findings flagged | Imaging/lab findings needing follow-up |
| pcp_03 | Medication change justification | Why was each drug changed/stopped? |
| pcp_04 | Duration of therapy | Antibiotic end dates, anticoagulation duration |
| pcp_05 | No hospital-specific orders | No IV protocols in discharge plan |
| pcp_06 | Summary not day-by-day | True summary, not timeline |

---

## Drug-Disease Pairs (in core/verifier.py)

Hardcoded. Deterministic. No LLM. Must always catch these:

```python
DANGEROUS_PAIRS = [
    {"drug": "rosiglitazone", "alt_names": ["avandia"],
     "condition": "heart failure", "icd9": ["4280"],
     "severity": "FDA black box"},
     
    {"drug": "metformin", "alt_names": ["glucophage"],
     "condition": "acute kidney injury", "icd9": ["5849"],
     "severity": "contraindicated"},
     
    {"drug": "nsaid", "alt_names": ["ibuprofen", "naproxen"],
     "condition": "chronic kidney disease", "icd9": ["585"],
     "severity": "caution"},
     
    {"drug": "phenytoin", "alt_names": ["dilantin"],
     "interacts_with": ["warfarin", "coumadin"],
     "severity": "drug-drug interaction"},
]
```

To add a new pair: add to this list in `core/verifier.py`, add a test in `core/tests/test_verifier.py`.

---

## Comorbidity Network (in core/connector.py)

Known dangerous co-occurrence pairs from the dataset:

```python
KNOWN_DANGEROUS = {
    ("4019", "41401"): "Hypertension + CAD (228 patients)",
    ("4019", "42731"): "Hypertension + AFib (219 patients)",
    ("42731", "4280"): "AFib + Heart Failure (198 patients)",
    ("4019", "4280"):  "Hypertension + CHF (188 patients)",
    ("25000", "4019"): "Diabetes + Hypertension (181 patients)",
    ("4280", "5849"):  "Heart Failure + AKI (137 patients)",
    ("25000", "5849"): "Diabetes + AKI (metformin risk)",
}
```

Graph built with NetworkX. Nodes = patient's ICD9 codes. Edges = co-occurrence weight from 2,000-patient dataset. Clusters detected via connected components.

---

## API Endpoints

### ED Doctor (`/api/v1/ed/`)

```
POST /api/v1/ed/analyze?patient_id=123
  → Full pipeline: extraction + verification + HQO checklist + PCP prefs + fix suggestions

POST /api/v1/ed/checklist?patient_id=123
  → Just HQO checklist compliance (9 items, pass/fail)
```

### PCP (`/api/v1/pcp/`)

```
POST /api/v1/pcp/report?patient_id=123
  → Full verified report: flags + gaps + network + actionable to-do list

POST /api/v1/pcp/ask?patient_id=123&question=What is the phenytoin interaction?
  → Mistral answers using patient data as context (no RAG, no vector DB)
```

### Shared (`/api/v1/`)

```
GET /api/v1/patients
  → List all patients [{subject_id, age, gender, admission_diagnosis}]

GET /api/v1/patient/{id}
  → Full patient context (all 6 tables joined)

GET /api/v1/patient/{id}/network
  → Comorbidity graph data (nodes, edges, clusters)

GET /health
  → {"status": "ok"}
```

---

## Docker Architecture (4 Containers)

```
┌──────────┐  ┌──────────┐
│ :8501    │  │ :8502    │
│ ED Dash  │  │ PCP Dash │
│(Streamlit)│ │(Streamlit)│
└────┬─────┘  └────┬─────┘
     └──────┬───────┘
            ▼
      ┌──────────┐
      │ :8000    │
      │ FastAPI  │
      └────┬─────┘
           ▼
      ┌──────────┐
      │ :11434   │
      │ Ollama   │
      │ Mistral  │
      │ 7B       │
      └──────────┘
```

**No ChromaDB container.** No vector database. No embedding service.

Services communicate via `cliniq-net` bridge network using container names:
- Dashboards call `http://api:8000`
- API calls `http://ollama:11434`

Data is volume-mounted from host, not baked into images.

---

## Environment Variables (.env)

```bash
# LLM — Mistral via Ollama
OLLAMA_HOST=http://localhost:11434    # becomes http://ollama:11434 in Docker
OLLAMA_MODEL=mistral:7b-instruct
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4096

# Data
DATA_DIR=./data/datasets

# API
API_HOST=0.0.0.0
API_PORT=8000

# Features
DEMO_MODE=false
```

---

## Coding Conventions

### Python Style
- Python 3.11+ features (match/case, `X | Y` unions)
- Type hints on all function signatures
- Pydantic v2 for data models
- f-strings only
- `pathlib.Path` not `os.path`
- Async for API endpoints, sync for agent pipeline

### Import Order
```python
# Standard library
import json
import re
from pathlib import Path

# Third party
import pandas as pd
import networkx as nx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

# Local
from core.models.extracted import ExtractedData
from core.llm_client import LLMClient
from config.settings import settings
```

### Error Handling for LLM
```python
# ALWAYS wrap LLM calls — Mistral 7B returns malformed JSON regularly
try:
    data = json.loads(llm_response)
    result = ExtractedData(**data)
except (json.JSONDecodeError, TypeError, ValidationError) as e:
    logger.warning(f"LLM JSON parse failed: {e}")
    result = ExtractedData.from_regex_fallback(llm_response)
```

### Prompt Templates
```python
# Keep SHORT — Mistral has ~8K context, note is ~2K tokens
# Demand JSON only — Mistral adds explanations otherwise
# [INST] tags added by LLMClient, don't add in templates

EXTRACT_PROMPT = """Extract data from this discharge summary into JSON.
Return ONLY valid JSON. No explanation. No markdown.

JSON schema:
{{"chief_complaint": "str", "allergies": ["str"], "diagnoses_mentioned": ["str"], ...}}

DISCHARGE SUMMARY:
{note_text}"""
```

### Testing
```python
# Tests MUST work without Ollama running — mock the LLM
# The Avandia+CHF test MUST always pass — it's the demo showstopper

def test_catches_avandia_chf():
    verifier = Verifier(llm_client=None)
    # ... mock data ...
    flags = verifier.verify(extracted, diagnoses, labs, prescriptions, allergies)
    assert len(flags.contraindications) > 0
    assert "heart failure" in flags.contraindications[0]["condition"]
```

---

## Common Tasks

### "Add a new drug-disease pair"
→ Add to `DANGEROUS_PAIRS` in `core/verifier.py`
→ Add test in `core/tests/test_verifier.py`

### "Add a new HQO checklist item"
→ Add to `HQO_CHECKLIST` in `checks/hqo_checklist.py`
→ Add check logic in `_check_item()` in same file

### "Add a new API endpoint"
→ Add to appropriate router in `api/routers/`
→ Add Pydantic schema in `api/schemas/`
→ Wire through `core/agent.py` if pipeline is needed

### "Improve extraction quality"
→ Edit `core/prompts/extract_prompt.py`
→ Remember: `[INST]` tags added by LLMClient, keep prompt under ~800 tokens
→ Test on demo patient first

### "Wire Streamlit dashboard to API"
→ Use `httpx` to call `http://api:8000/api/v1/...` (Docker) or `http://localhost:8000/api/v1/...` (local)
→ Parse response, render with Streamlit

### "Add demo mode"
→ Check `settings.demo_mode` in `core/agent.py`
→ If true, load `data/demo_cache.json` instead of running pipeline
→ Generate cache with `scripts/find_demo_patient.py`

### "Visualize comorbidity network"
→ `frontend/components/comorbidity_graph.py`
→ NetworkX graph → Plotly figure → `st.plotly_chart()`

---

## Things to NEVER Do

1. **Never call OpenAI, Gemini, Groq, or any cloud API.** Mistral 7B via Ollama only.
2. **Never use ChromaDB, vector embeddings, or RAG.** Not in this project.
3. **Never put API keys or secrets in code.** Use `.env` + `config/settings.py`.
4. **Never copy CSV data into Docker images.** Mount as volumes.
5. **Never use `--reload` in Dockerfiles.** Only for local dev.
6. **Never make the system diagnose patients.** It flags, it doesn't diagnose.
7. **Never make the system recommend drugs.** It catches contraindications, it doesn't prescribe.
8. **Never skip JSON validation on LLM output.** Mistral 7B WILL return bad JSON.
9. **Never send full note + long prompt.** Budget: ~2K note + ~800 prompt + ~5K response max.
10. **Never hardcode `localhost` in Docker services.** Use container names (`http://api:8000`, `http://ollama:11434`).
11. **Never run containers as root.** Dockerfiles use non-root `cliniq` user.
12. **Never create a `knowledge/` folder.** Checklists live in `checks/`. Clinical knowledge comes from Mistral natively.

---

## Running the Project

```bash
# ── Local development ──
ollama pull mistral:7b-instruct
ollama serve                          # start Ollama in background
pip install -r requirements.txt
python scripts/load_data.py           # download 6 CSVs from HuggingFace
uvicorn api.main:app --reload --port 8000
streamlit run frontend/ed_dashboard.py --server.port 8501
streamlit run frontend/pcp_dashboard.py --server.port 8502

# ── Docker (demo day) ──
docker-compose up --build
docker exec cliniq-ollama ollama pull mistral:7b-instruct   # first time only
# ED:       http://localhost:8501
# PCP:      http://localhost:8502
# API docs: http://localhost:8000/docs

# ── Tests (no Ollama needed) ──
pytest core/tests/ -v
```

---

## Research Context

Use this when generating clinically accurate code or comments:

- **Tsai (2018)**: Diseases should be modeled as "reciprocally reinforcing nodes in an association network" — why we build the comorbidity graph
- **Mills et al. (2016)**: 64-66% medication info is inaccurate in discharge letters — why Step 2 cross-references
- **Schwarz et al. (2019)**: 60% of discharge letters missing essential info — the problem ClinIQ solves
- **HQO Ontario**: Discharge summaries must reach PCP within 48 hours. Safe Discharge Practices Checklist.
- **Walke et al. (2024, PMC11169121)**: PCPs want actionable to-do lists, medication change justifications, and incidental findings — not day-by-day timelines