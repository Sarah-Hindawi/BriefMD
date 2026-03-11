# Brief MD Codebase — Architecture Layer Map

> **Framework:** Three-Layer AI System Architecture  
> **Project:** BriefMd— Clinical Intelligence Assistant  
> **Mapped:** March 2026

---

## 🟦 Layer 3 — Application Development
> *Where users interact with the system: prompts, context construction, RAG, and agentic orchestration*

| Folder / File | Role | Why It's Here |
|---|---|---|
| `frontend/` | AI Interface | Streamlit dashboards for ED and PCP users; components include flag cards, comorbidity graph, and chat box — all application-layer UI |
| `api/` | API Gateway | Routers for ED, PCP, and patient endpoints with request/response schemas — the application's API surface between users and intelligence |
| `core/prompts/` | Prompt Engineering | Extraction, verification, and RAG prompt templates — the core of application-layer AI work |
| `core/agent.py` | Agentic Orchestration | 3-step pipeline (extract → verify → connect); decides what context to gather, what prompts to send, and how to chain steps |
| `knowledge/rag.py` | RAG Pipeline | Query → retrieve → generate cycle; context construction is a defining application-layer responsibility |
| `knowledge/hqo_checklist.py` | Context Construction | Provides the model with domain-specific checklists to ground its outputs |
| `knowledge/pcp_preferences.py` | Context Construction | Structured context that shapes model output for the PCP-facing side |
| `knowledge/drug_interactions.py` | Grounding Context | Curated knowledge that prevents hallucinated drug interactions |

---

## 🟨 Layer 2 — Model Development
> *Thinner here because API-hosted models are used (no training from scratch), but this layer still exists through model configuration, output schema enforcement, and embedding management*

| Folder / File | Role | Why It's Here |
|---|---|---|
| `core/llm_client.py` | Model Abstraction | Selects, configures, and manages model providers (Groq, Mistral, Gemini); handles temperature, fallback logic, and inference optimization |
| `core/extractor.py` | Schema-Constrained Extraction | Defines how the model should extract (schema enforcement, constrained output) — straddles application and model layers |
| `core/verifier.py` | Model Behavior Shaping | Verification logic defines what the model must check against, directly shaping model behavior |
| `core/connector.py` | Relationship Representation | Comorbidity network generation involves model-level decisions about relationship structure |
| `core/models/` | Output Contract | Pydantic schemas (`extracted.py`, `flags.py`, `network.py`, `report.py`) define structured output that constrains model behavior |
| `knowledge/chroma_store.py` | Embedding Model Management | ChromaDB chunking, embedding, and indexing strategy — how documents are represented in vector space |
| `scripts/load_knowledge.py` | Data Curation | Ingests and prepares clinical guidelines for the vector store — dataset engineering |
| `scripts/find_demo_patient.py` | Evaluation Dataset Engineering | Identifies the right evaluation/demo cases |
| `scripts/eda.py` | Data Exploration | Exploratory analysis that informs model and prompt decisions |

---

## 🟥 Layer 1 — Infrastructure
> *The compute, data management, serving, and monitoring foundation everything else runs on*

| Folder / File | Role | Why It's Here |
|---|---|---|
| `docker/` | Compute Management | Dockerfiles for API, frontend, and knowledge services — defines how everything is deployed and served |
| `docker-compose.yml` | Service Orchestration | Manages how containers interact — core infrastructure coordination |
| `config/settings.py` | Environment Configuration | API keys, file paths, service URLs — resource and environment config |
| `config/logging.py` | Monitoring | Tracks system activity and errors across all services |
| `data/loader.py` | Data Management | Loads and manages MIMIC CSV datasets |
| `data/patient_context.py` | Data Pipeline | Joins across 6 tables to build patient context — a data engineering concern |
| `data/datasets/` | Raw Data Storage | Source data before processing |
| `knowledge/guidelines/` | Document Storage | Raw PDFs before they become embeddings in ChromaDB |
| `.env.example` | Infrastructure Config | Secrets, API keys, and environment variable templates |
| `Makefile` | Build Automation | Build and deployment automation scripts |

---

## Architecture at a Glance
─────────────────────────────────────────────────────────┐
│ LAYER 3 — APPLICATION DEVELOPMENT │
│ frontend/ · api/ · core/prompts/ · core/agent.py │
│ knowledge/rag.py · hqo_checklist.py · drug_interactions│
├─────────────────────────────────────────────────────────┤
│ LAYER 2 — MODEL DEVELOPMENT │
│ core/llm_client.py · extractor.py · verifier.py │
│ connector.py · core/models/ · chroma_store.py │
│ scripts/load_knowledge.py · eda.py │
├─────────────────────────────────────────────────────────┤
│ LAYER 1 — INFRASTRUCTURE │
│ docker/ · docker-compose.yml · config/ │
│ data/loader.py · data/patient_context.py │
│ data/datasets/ · knowledge/guidelines/ · Makefile │
└─────────────────────────────────────────────────────────┘

text

---

> **Key insight:** BriefMd is overwhelmingly an **Application Development** project — your primary engineering value is in prompt design, RAG pipelines, agentic orchestration, and clinical context construction. The Model and Infrastructure layers are deliberately thin, which is the right trade-off for a prototype demonstrating clinical AI workflows.
