# AtlasAI

**Enterprise Knowledge Intelligence Platform**

AtlasAI is a local-first platform for securely ingesting, indexing, retrieving, and reasoning over enterprise knowledge with grounded AI responses, citations, access control, evaluation, and observability.

> ✅ **Status:** Local backend MVP validated. AtlasAI has a working auth, document processing, retrieval, grounded answer generation, and evaluation flow in a local-first WSL/Docker setup.

---

## Overview

AtlasAI is designed to help organizations search, reason over, and answer questions from internal knowledge without depending on hosted AI services. The system keeps the core workflow local-first: ingest documents, index them, retrieve the most relevant evidence, ground the answer with citations, and abstain when evidence is insufficient.

The project is deliberately built as a production-minded local backend rather than a simple chat demo.

---

## Current status

The backend is now functionally mature for a local-first knowledge platform. It supports:

- ✅ Auth, orgs, teams, memberships, and permissions
- ✅ Document ingestion, parsing, lifecycle tracking, and retry flows
- ✅ Hybrid retrieval, reranking, and citation support
- ✅ Grounded local answer generation via Ollama
- ✅ Evaluation harness for retrieval and answer-quality checks
- ✅ Full backend test suite passing

The repo has also been validated against a live local stack: Redis, Postgres, and Ollama are available in WSL, and the backend suite passes. Remaining work is primarily operational validation against representative corpora, observability, and production hardening rather than basic feature implementation.

---

## Architecture

```text
AtlasAI
  ├─ Organizations / Users / Teams / Permissions
  ├─ Document ingestion and versioning
  ├─ Parsing, chunking, OCR, metadata extraction
  ├─ Local embeddings + keyword search + hybrid retrieval
  ├─ Grounded answer generation with citations and abstention
  ├─ Celery + Redis async processing
  └─ Evaluation and observability layer
```

---

## Tech stack

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

### Data
- SQLite (default for local development and tests)
- PostgreSQL (production target)
- pgvector / vector database (planned for larger-scale semantic indexing)

### AI / ML
- Sentence-transformers embeddings
- BM25-style keyword retrieval
- Hybrid search and reranking
- Local Ollama models for grounded generation
- Evaluation metrics for retrieval and answer quality

### Infrastructure
- Docker
- Docker Compose
- Linux / WSL
- Redis
- Celery

---

## Repository structure

```text
atlas-ai/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── features/
│   │   └── main.py
│   ├── migrations/
│   ├── tests/
│   ├── .env.example
│   ├── alembic.ini
│   └── requirements.txt
├── infrastructure/
│   └── docker/
│       └── docker-compose.yml
├── .gitignore
├── LICENSE
├── PROJECT_ANALYSIS_REPORT.md
├── README.md
├── pyproject.toml
└── .venv/
```

---

## Local development

### Prerequisites

- Python 3.12+
- Docker Desktop or Docker Engine
- WSL2 for Linux-based local development
- Git
- Tesseract OCR for scanned PDFs and images (optional for text-based files)

Install Tesseract on Ubuntu/WSL:

```bash
sudo apt-get update && sudo apt-get install -y tesseract-ocr
```

### Setup

```bash
cd /home/abinb/atlas/atlas-ai/backend
python3 -m venv .venv
. .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
cp .env.example .env
```

### Start local services

From the repo root:

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d postgres redis
```

Start a local Ollama service and make sure it is reachable at `http://localhost:11434`.

Example:

```bash
ollama pull llama3.2
```

### Run the API

```bash
cd backend
. .venv/bin/activate
uvicorn app.main:app --reload
```

The API is available at:

- http://127.0.0.1:8000
- http://127.0.0.1:8000/docs

### Run the document worker

In a second terminal:

```bash
cd backend
. .venv/bin/activate
celery -A app.workers.celery_app:celery_app worker --loglevel=INFO
```

The default Redis broker is `redis://localhost:6379/0`.

---

## Key capability areas

### Auth and org access
The app supports authenticated users, organization membership, role-based access, and team-scoped permissions. Viewer/read-only access is enforced at the API layer, while org owners and admins can manage content and membership.

### Document ingestion and processing
Uploads are stored in local or S3-compatible object storage and queued for async processing. Documents move through lifecycle states such as `PENDING`, `PROCESSING`, `READY`, and `FAILED`, with retry and failure handling built in.

### Retrieval
The system supports:

- keyword search
- semantic vector search
- hybrid retrieval
- reranking
- citation-linked retrieval results

### Grounded answer generation
The answer route retrieves the relevant evidence, sends only those excerpts to Ollama, enforces citation validity, and abstains when the evidence is insufficient.

### Evaluation
The repo includes an evaluation runner and example dataset for retrieval metrics and answer-quality checks, including groundedness-focused metrics.

---

## Database and migrations

The project uses SQLAlchemy with Alembic. SQLite is the local default for development and tests, while PostgreSQL is the production target.

Apply migrations:

```bash
cd backend
alembic upgrade head
```

---

## Testing

Run the backend suite:

```bash
cd backend
pytest -q
```

The repo is currently green in the local backend validation flow.

---

## Notes

- No hosted LLM provider is required for the core local workflow.
- Local object storage is intended for development; S3-compatible storage is supported as an option.
- The app is built to remain local-first and operationally robust under WSL and Docker.
