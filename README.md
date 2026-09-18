# AtlasAI

**Enterprise Knowledge Intelligence Platform**

AtlasAI is an engineering-focused platform for securely ingesting, indexing, retrieving, and reasoning over enterprise knowledge with grounded AI responses, citations, access control, evaluation, and observability.

> 🚧 **Status:** Active development. AtlasAI is currently in the backend foundation stage.

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

The project is currently focused on establishing a reliable backend and engineering foundation.

### Implemented

- FastAPI backend
- Application configuration management
- PostgreSQL database
- SQLAlchemy ORM
- Alembic database migrations
- Organization database model
- Reusable timestamp model
- Health check API
- Application logging
- Docker-based PostgreSQL development environment
- Pytest test setup
- Ruff linting and formatting

### In Progress

- Organizations and users
- Authentication and authorization
- Permission model
- Document ingestion pipeline
- Document metadata
- Document versioning
- Document processing

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

Install the project dependencies according to the current development setup.

### Environment configuration

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Update the database configuration for your local environment.

### Start PostgreSQL

From the repository root:

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
```

### Run the API

From `backend/`:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

http://127.0.0.1:8000


API documentation:

http://127.0.0.1:8000/docs


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

### Phase 2 — Identity & Access
- [ ] Users
- [ ] Organizations
- [ ] Teams
- [ ] Authentication
- [ ] Authorization
- [ ] Role-based access control
- [ ] Resource-level permissions

### Phase 3 — Knowledge Ingestion
- [ ] PDF ingestion
- [ ] DOCX ingestion
- [ ] Markdown / HTML ingestion
- [ ] OCR
- [ ] Metadata extraction
- [ ] Document chunking
- [ ] Document versioning
- [ ] Processing pipeline

### Phase 4 — Retrieval
- [ ] Keyword search
- [ ] Vector search
- [ ] Hybrid retrieval
- [ ] Reranking
- [ ] Permission-aware retrieval

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
- [ ] Retrieval evaluation
- [ ] Answer evaluation
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

AtlasAI is designed with enterprise security requirements in mind.

Planned security capabilities include:

- Environment-based secret management
- Authentication and authorization
- Organization isolation
- Permission-aware retrieval
- Input validation
- Rate limiting
- Audit logging
- Secure document access
- Observability and monitoring

Never commit credentials, API keys, passwords, private keys, or other secrets to the repository.

---

## License

See LICENSE for the project's license.

---

## Project Status

AtlasAI is an active personal engineering project focused on building a production-oriented enterprise AI platform while exploring modern backend engineering, information retrieval, RAG, machine learning evaluation, MLOps, cloud infrastructure, and distributed systems.
