# AtlasAI

**Enterprise Knowledge Intelligence Platform**

AtlasAI is an engineering-focused platform for securely ingesting, indexing, retrieving, and reasoning over enterprise knowledge with grounded AI responses, citations, access control, evaluation, and observability.

> 🚧 **Status:** Active development. AtlasAI is currently in the backend/API MVP stage.

---

## Overview

Enterprise knowledge is often scattered across PDFs, documents, policies, research papers, SOPs, meeting notes, and internal systems.

AtlasAI aims to provide a centralized intelligence layer that allows organizations to:

- Search enterprise knowledge efficiently
- Ask questions across internal documents
- Generate grounded AI responses with citations
- Compare document versions
- Discover related knowledge
- Enforce organization and user-level access control
- Evaluate retrieval and answer quality
- Monitor system usage, performance, and AI costs

The project is being built as a production-oriented system rather than a simple chatbot or CRUD application.

---

## Problem

Traditional enterprise knowledge systems often require employees to manually search through large collections of documents.

Generic AI assistants introduce another problem: answers may be difficult to verify and can contain unsupported information.

AtlasAI is designed around the principle:

**Retrieve → Verify → Reason → Cite → Observe**

The goal is to make AI-assisted enterprise knowledge retrieval more useful, traceable, and controllable.

---

## Current Status
The backend currently supports authenticated organization and team access, role-based permissions, versioned document ingestion for text/Markdown/HTML/PDF/DOCX/images with local OCR, durable Celery/Redis processing, local/S3-compatible object storage, PDF/DOCX/image metadata extraction, and organization-scoped keyword, semantic, hybrid, and reranked retrieval. It also provides grounded question answering through a local Ollama model, with citations and insufficient-evidence abstention. No hosted LLM provider is required.

Remaining roadmap work includes metadata enrichment for additional document formats, semantic answer/groundedness evaluation, observability, and production deployment.

---

## Planned Architecture

```text
                    AtlasAI
                       │
                       ▼
             ┌───────────────────┐
             │ Organizations     │
             │ Users / Teams     │
             │ Permissions       │
             └─────────┬─────────┘
                       │
                       ▼
             ┌───────────────────┐
             │ Document          │
             │ Ingestion         │
             └─────────┬─────────┘
                       │
                       ▼
             ┌───────────────────┐
             │ Parsing           │
             │ Chunking          │
             │ Metadata          │
             │ Versioning        │
             └─────────┬─────────┘
                       │
                       ▼
             ┌───────────────────┐
             │ Hybrid Retrieval  │
             │                   │
             │ BM25 + Vector     │
             │ + Reranking       │
             └─────────┬─────────┘
                       │
                       ▼
             ┌───────────────────┐
             │ RAG / LLM Layer   │
             └─────────┬─────────┘
                       │
                       ▼
             ┌───────────────────┐
             │ Citations         │
             │ Groundedness      │
             │ Abstention        │
             └─────────┬─────────┘
                       │
                       ▼
             ┌───────────────────┐
             │ Evaluation        │
             │ Observability     │
             │ Analytics         │
             └───────────────────┘
```

## Technology Stack

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

### Data
- PostgreSQL
- pgvector / vector database (planned)

### AI / ML
- Retrieval-Augmented Generation (RAG)
- Embeddings
- Hybrid search
- Reranking
- LLMs
- Model evaluation (planned)

### Infrastructure
- Docker
- Docker Compose
- Linux / WSL
- GitHub Actions (planned)
- AWS (planned)
- Kubernetes (planned)

### Engineering
- Pytest
- Ruff
- Mypy
- Git
- GitHub pull requests
- Database migrations
- Automated testing and CI/CD

---

## Repository Structure

```text
atlas-ai/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── features/
│   │   └── main.py
│   │
│   ├── migrations/
│   │   └── versions/
│   │
│   ├── tests/
│   ├── .env.example
│   └── alembic.ini
│
├── infrastructure/
│   └── docker/
│       └── docker-compose.yml
│
├── .gitignore
├── LICENSE
└── README.md
```

---

## Local Development

### Prerequisites
- Python 3.12+
- Docker
- Git
- Tesseract OCR system binary for scanned PDFs and image uploads (optional for text-based documents)
  - On Ubuntu/WSL, install it with `sudo apt-get update && sudo apt-get install -y tesseract-ocr`.

### Clone

```bash
git clone <repository-url>
cd atlas-ai
```

### Backend environment

```bash
cd backend

python -m venv .venv
source .venv/bin/activate
```

For CPU-only local inference on Linux/WSL, install the CPU PyTorch wheel first, then the backend dependencies:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

### Environment configuration

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Update the database configuration for your local environment.

### Start PostgreSQL

From the repository root:

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d postgres redis
```

### Run the API

From `backend/`:

```bash
uvicorn app.main:app --reload
```

### Run the document worker

In a second terminal, use the same backend environment and `DATABASE_URL` as the API:

```bash
cd backend
source .venv/bin/activate
celery -A app.workers.celery_app:celery_app worker --loglevel=INFO
```

Configure the broker with `REDIS_URL` (default `redis://localhost:6379/0`). Document uploads return while processing is `PENDING` (or `PROCESSING`); poll the document detail/list endpoints for `READY` or `FAILED`. Failed documents include a processing error and can be retried by organization owners/admins. Redis broker delivery is durable and the worker acknowledges jobs only after completion. If Redis is unavailable at enqueue time, the upload remains stored, is marked `FAILED`, and the API reports `503` so an administrator can retry it.

Uploads are stored in `LOCAL_DOCUMENT_STORAGE_PATH` (default `backend/document_uploads`) for development. API and worker processes must share that directory. For S3-compatible storage, set `DOCUMENT_STORAGE_BACKEND=s3`, `S3_BUCKET`, `S3_ENDPOINT_URL` (omit for AWS), `S3_REGION`, and credentials via `S3_ACCESS_KEY_ID`/`S3_SECRET_ACCESS_KEY` or the AWS credential chain. Keep credentials out of source control. Existing database-resident upload bytes remain readable for legacy documents; new uploads store only a storage key in the database.

Grounded answer generation uses a local Ollama server; no hosted LLM provider is called. Install/start Ollama separately, pull the configured model (default `llama3.2`), and set `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and `OLLAMA_TIMEOUT_SECONDS` in `backend/.env`. For example, run `ollama pull llama3.2` and ensure the server is reachable at `http://localhost:11434` from the API process.

The API will be available at:

http://127.0.0.1:8000


API documentation:

http://127.0.0.1:8000/docs

### Implemented API foundation
Authenticated endpoints use `Authorization: Bearer <access_token>`.

- `POST /api/v1/auth/register` and `POST /api/v1/auth/login`
- `GET /api/v1/users/me`
- `GET /api/v1/organizations` and `POST /api/v1/organizations`
- `GET /api/v1/organizations/{organization_id}`
- Organization membership list/add/update/remove endpoints under `/members`
- Text document upload/list/detail/delete under `/organizations/{organization_id}/documents`
- Multipart upload at `/organizations/{organization_id}/documents/upload` for text/Markdown/HTML/PDF/DOCX and PNG/JPEG/TIFF images. Scanned PDF pages and image files use local Tesseract OCR (`OCR_LANGUAGE`, default `eng`); PDFs with selectable text keep the native text extraction path. OCR is limited to 25 scanned pages and 30 seconds per page. Install the Tesseract system binary for scanned documents.
- Document versions at `/organizations/{organization_id}/documents/{document_id}/versions`; failed processing state and retry at `/organizations/{organization_id}/documents/{document_id}/retry`
- Extracted document properties are exposed as `extracted_metadata`: PDF page count and available title/author/subject/keywords/creator/timestamps, DOCX core properties, and image dimensions/format plus available EXIF properties. Metadata strings are capped at 500 characters.
- Team list/create and member list/add/remove under `/organizations/{organization_id}/teams` (organization members only; owner/admin manage teams)
- `GET /api/v1/organizations/{organization_id}/search?q=...` for organization-scoped keyword retrieval
- `GET /api/v1/organizations/{organization_id}/vector-search?q=...` for local sentence-transformer semantic retrieval
- `GET /api/v1/organizations/{organization_id}/hybrid-search?q=...` for keyword and semantic retrieval fused by reciprocal rank fusion
  - Hybrid results are reranked with a local CPU cross-encoder (`RERANKER_MODEL_NAME`).
- `POST /api/v1/organizations/{organization_id}/vector-index/rebuild` for owner/admin reindexing after changing the embedding model
- `GET /api/v1/organizations/{organization_id}/retrieve?q=...` for ranked retrieval with stable citation IDs and document/chunk references
- `POST /api/v1/organizations/{organization_id}/answer` with `{"question": "...", "limit": 8}` for hybrid-retrieved, locally generated answers with source citations; organization membership is required

Answer generation passes only retrieved excerpts to Ollama, treats those excerpts as untrusted input, requires the answer to cite supplied citation IDs, and returns only sources actually cited. It abstains without calling the model when retrieval finds no evidence, and returns `503` if Ollama is unavailable or produces invalid citations. The model can be changed with `OLLAMA_MODEL`; configure its endpoint and timeout with `OLLAMA_BASE_URL` and `OLLAMA_TIMEOUT_SECONDS`.

Ingestion extracts UTF-8 text/Markdown/HTML and parses PDF/DOCX files (up to 5 MB by default), filters HTML scripts/styles, deduplicates content within an organization, records processing state/errors, tracks versions by source filename, and creates overlapping chunks. Original uploads are retained in local or S3-compatible object storage for administrator retries. Processing runs in Celery workers through Redis; the API persists a queued status before dispatch. Local filesystem storage is for development and requires a shared path between API and workers. The development database defaults to SQLite; PostgreSQL remains the intended production database. Set a unique `AUTH_SECRET_KEY` (at least 32 characters) outside development. The embedding model defaults to `sentence-transformers/all-MiniLM-L6-v2` and is downloaded by sentence-transformers on first use; override it with `EMBEDDING_MODEL_NAME`. Hybrid search fuses the top keyword and semantic rankings with reciprocal rank fusion (RRF, rank constant 60), then reranks up to 100 candidates with a local CPU cross-encoder (default `cross-encoder/ms-marco-MiniLM-L-6-v2`; configure using `RERANKER_MODEL_NAME`). The reranker downloads its model on first hybrid-search use. Keyword retrieval is capped at 500 matching chunks and each hybrid source contributes up to 50 candidates; semantic search scans indexed organization chunks in application memory, so a dedicated vector database/index is still needed for large corpora.

---

## Database & Migrations

AtlasAI uses PostgreSQL with SQLAlchemy and Alembic.

Apply migrations:

```bash
cd backend
alembic upgrade head
```

Check the current migration:

```bash
alembic current
```

Create a new migration:

```bash
alembic revision --autogenerate -m "describe change"
```

Review generated migrations before applying them.

---

## Testing

Run the test suite:

```bash
cd backend
pytest -q
```

Run Ruff:

```bash
ruff check .
ruff format --check .
```

The project uses automated checks to keep the codebase consistent as development progresses.

### Retrieval and answer evaluation

The evaluation runner scores hybrid retrieval with Recall@k, MRR@k, and nDCG@k, and checks answer abstention plus citation precision/recall against expected relevant document IDs. It uses a JSON dataset; see [`backend/evaluation/synthetic_dataset.example.json`](backend/evaluation/synthetic_dataset.example.json) for the format. Replace its placeholder organization/document IDs with IDs from an isolated evaluation organization and populate cases with representative questions. Answerable cases need at least one relevant document ID; expected-abstention cases must have none. `reference_answer` is optional and included in per-case output for human review.

After starting the API, logging in, and making sure Ollama and the retrieval models are available, run from `backend/`:

```bash
export ATLAS_EVAL_TOKEN="<bearer-token>"
python -m app.evaluation.runner \
  --dataset evaluation/my_dataset.json \
  --base-url http://localhost:8000 \
  --k 10
```

The token is sent only to the configured AtlasAI API. Each case calls both hybrid search and answer generation, so this evaluates the running system end to end. Metrics are macro-averaged across answerable cases; abstention accuracy includes every case. Citation relevance is judged against the gold document IDs, not semantic answer correctness. Review the answers and citations against domain-specific reference facts as a separate human or model-judge step; a high retrieval or citation score alone does not establish factual correctness. Results include generated answers, so store or redirect output according to your data-handling policy. The synthetic runner tests require no live API, Ollama, or real documents.

---

## Engineering Practices

AtlasAI is being developed using a production-oriented workflow.

The project emphasizes:

- Feature branches
- Pull requests
- Small, focused commits
- Conventional commit messages
- Automated tests
- Static analysis
- Code formatting
- Database migrations
- Configuration through environment variables
- Separation of application concerns
- API versioning
- Structured logging
- Reproducible development environments

The architecture currently follows a modular monolith approach. Services will only be separated when there is a clear technical reason to do so.

---

## Roadmap

### Phase 1 — Backend Foundation
- [x] FastAPI application
- [x] Configuration management
- [x] PostgreSQL
- [x] SQLAlchemy
- [x] Alembic
- [x] Organization model
- [x] Health endpoint
- [x] Testing foundation
- [x] Ruff tooling

### Phase 2 - Identity & Access
- [x] Users
- [x] Organizations
- [x] Teams
- [x] Authentication
- [x] Authorization
- [x] Role-based access control
- [x] Organization-scoped resource access

### Phase 3 - Knowledge Ingestion
- [x] PDF ingestion
- [x] DOCX ingestion
- [x] Plain text / Markdown / HTML ingestion
- [x] Local Tesseract OCR for scanned PDFs and images
- [x] PDF/DOCX core-property and image/EXIF metadata extraction
- [x] Document chunking
- [x] Document versioning
- [x] Durable asynchronous Celery/Redis processing with status, error persistence, and retry
- [x] Local filesystem and S3-compatible object storage

### Phase 4 — Retrieval
- [x] Keyword search
- [x] Vector search (local sentence-transformer embeddings)
- [x] Hybrid retrieval
- [x] Local cross-encoder reranking for hybrid search
- [x] Permission-aware retrieval with source/chunk citations

### Phase 5 — AI Knowledge Layer
- [ ] RAG pipeline
- [ ] Source citations
- [ ] Citation validation
- [ ] Groundedness checks
- [ ] Document comparison
- [ ] Summarization
- [ ] Related-document discovery
- [ ] Abstention / human review mechanisms

### Phase 6 — Evaluation & Observability
- [x] Retrieval-ranking evaluation harness (Recall@k, MRR@k, nDCG@k)
- [x] Citation and abstention evaluation harness
- [ ] Semantic answer correctness evaluation
- [ ] Hallucination / groundedness evaluation
- [ ] Model tracking
- [ ] Usage analytics
- [ ] AI cost tracking
- [ ] Application metrics
- [ ] Distributed tracing
- [ ] Production monitoring

### Phase 7 — Production Infrastructure
- [ ] CI/CD
- [ ] Containerized deployment
- [ ] AWS deployment
- [ ] Infrastructure automation
- [ ] Kubernetes deployment
- [ ] Production security hardening

---

## Security

AtlasAI uses scrypt password hashes, signed expiring bearer tokens, environment-based secret configuration, validated inputs, organization-scoped access, role checks, and permission-aware document search. Production startup requires a non-default `AUTH_SECRET_KEY` of at least 32 characters.

Rate limiting, audit logging, security monitoring, and production hardening remain planned work.

Never commit credentials, API keys, passwords, private keys, or other secrets to the repository.

---

## License

See LICENSE for the project's license.

---

## Project Status

AtlasAI is an active personal engineering project focused on building a production-oriented enterprise AI platform while exploring modern backend engineering, information retrieval, RAG, machine learning evaluation, MLOps, cloud infrastructure, and distributed systems.
