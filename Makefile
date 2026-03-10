.PHONY: install dev data ollama test lint docker-up docker-down docker-build clean

# ── Local development ──

install:
	pip install -r requirements.txt

dev: ollama
	uvicorn api.main:app --reload --port 8000

ollama:
	ollama pull mistral:7b-instruct

data:
	python scripts/load_data.py

ed:
	streamlit run frontend/ed_dashboard.py --server.port 8501

pcp:
	streamlit run frontend/pcp_dashboard.py --server.port 8502

# ── Testing ──

test:
	pytest core/tests/ -v

lint:
	ruff check .

# ── Docker (demo day) ──

docker-build:
	docker compose build

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-ollama-pull:
	docker exec briefmd-ollama ollama pull mistral:7b-instruct

# ── Utilities ──

demo-cache:
	python scripts/find_demo_patient.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
