# BriefMD

Dual-sided clinical intelligence for hospital discharge transitions. Aligned with Ontario's HQO Quality Standard (10 Quality Statements).

- **Side A (ED Quality Gate):** Checks discharge notes *before* they leave the hospital — catches missing diagnoses, drug contraindications, HQO compliance gaps.
- **Side B (PCP Verified Report):** Analyzes notes *after* the PCP receives them — generates actionable to-do lists, flags, monitoring plans.

Built for the Clinical AI Hackathon using ~2000 MIMIC hospital admissions.

---

## Quick Start

### Prerequisites

- Python 3.11+
- At least ONE LLM API key (free tier):
  - [Groq](https://console.groq.com) (primary — fastest)
  - [Mistral](https://console.mistral.ai) (fallback)
  - [Google Gemini](https://aistudio.google.com) (emergency)

### Setup

```bash
git clone https://github.com/your-team/BriefMD.git
cd BriefMD
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

### Configure API keys

```bash
cp .env.example .env
```

Open `.env` and add your key(s):

```
GROQ_API_KEY=gsk_your_key_here
MISTRAL_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
```

You only need ONE key to run. All three gives you fallback redundancy.

### Prepare the vector store

```bash
python3 rag/ingest.py
```

Creates `qdrant_db/` with embedded discharge summaries. Only needs to run once.

### Start the API server

```bash
uvicorn api.main:app --reload --port 8000
```

Verify: `curl http://localhost:8000/api/v1/health`

### Start the dashboards (separate terminals)

```bash
streamlit run frontend/ed_dashboard.py --server.port 8501
streamlit run frontend/pcp_dashboard.py --server.port 8502
```

| Service | URL |
|---------|-----|
| API Docs | http://localhost:8000/docs |
| ED Dashboard | http://localhost:8501 |
| PCP Dashboard | http://localhost:8502 |

---

## Docker

```bash
docker compose up --build
```

Same URLs as above.

---

## Project Structure

```
BriefMD/
├── api/                    ← FastAPI gateway
│   ├── main.py             ← App config, CORS, router registration
│   ├── dependencies.py     ← Singleton manager (data, agent, LLM)
│   ├── routers/            ← ed.py, pcp.py, patients.py, chat.py, health.py
│   └── schemas/            ← Pydantic request/response models
│
├── core/                   ← Agent pipeline
│   ├── agent.py            ← Orchestrates extract → verify → connect
│   ├── extractor.py        ← LLM → structured JSON
│   ├── verifier.py         ← DETERMINISTIC Python — no LLM
│   ├── connector.py        ← Comorbidity co-occurrence network
│   ├── llm_client.py       ← Multi-provider: Groq → Mistral → Gemini
│   ├── prompts/            ← extract_prompt.py
│   └── models/             ← extracted.py, flags.py, network.py, report.py
│
├── knowledge/              ← Clinical knowledge (deterministic lookups)
│   ├── hqo_checklist.py    ← 10 HQO Quality Statements
│   ├── drug_interactions.py ← Drug-disease contraindication table
│   └── lab_ranges.py       ← Statistical reference ranges from dataset
│
├── rag/                    ← Retrieval-Augmented Generation
│   ├── ingest.py           ← Loads data into Qdrant
│   ├── vector_store.py     ← Qdrant connection + embedding
│   └── retriever.py        ← Interface for agent.py
│
├── data/                   ← Data loading
│   ├── loader.py           ← Reads compressed CSVs into memory
│   ├── patient_context.py  ← Joins 6 tables per patient
│   └── datasets/           ← MIMIC CSV files
│
├── frontend/               ← Streamlit dashboards
│   ├── ed_dashboard.py     ← Side A — ED Quality Gate
│   ├── pcp_dashboard.py    ← Side B — PCP Verified Report
│   └── components/         ← Shared UI components
│
├── config/                 ← settings.py, logging.py
├── docker-compose.yml
├── requirements.txt
└── CLAUDE.md
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Service status check |
| GET | `/api/v1/patients` | List all patients |
| GET | `/api/v1/patient/{hadm_id}` | Full patient context |
| GET | `/api/v1/patient/{hadm_id}/network` | Comorbidity graph |
| GET | `/api/v1/ed/summaries` | Browse discharge summaries |
| GET | `/api/v1/ed/summaries/{hadm_id}` | View summary + record counts |
| POST | `/api/v1/ed/analyze` | Full ED quality gate pipeline |
| POST | `/api/v1/ed/checklist` | HQO checklist only (10 items) |
| POST | `/api/v1/pcp/report` | PCP verified report |
| POST | `/api/v1/chat/ask` | RAG Q&A (both sides) |

---

## Dataset

~2000 MIMIC hospital admissions with discharge summaries, diagnoses (ICD-9), labs, and prescriptions.

## Tech Stack

- **Backend:** Python, FastAPI, Pydantic v2
- **LLM:** Groq (Llama 3.3 70B), Mistral, Google Gemini — no GPU required
- **Vector Store:** Qdrant + sentence-transformers (all-MiniLM-L6-v2)
- **Frontend:** Streamlit
- **Clinical Standard:** Ontario HQO "Transitions Between Hospital and Home"

---

## Team

Built for the Clinical AI Hackathon, March 2026.
