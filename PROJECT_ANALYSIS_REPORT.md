## Current implementation update - 2026-10-01
The backend has advanced from the initial snapshot to include account registration and login with scrypt password hashes and signed expiring bearer tokens; organization membership and OWNER/ADMIN/MEMBER/VIEWER access controls; organization-scoped document, team, keyword-search, and retrieval APIs; bounded text/Markdown/HTML/PDF/DOCX ingestion, local Tesseract OCR for scanned PDFs/images, and extracted PDF/DOCX/image properties; deduplication, overlapping chunks, processing status/errors, retries, Celery/Redis asynchronous processing, local/S3-compatible object storage, and source-name version history; local sentence-transformer semantic search; and grounded, citation-validated answer generation with a local Ollama model.

Semantic vector search now uses local CPU sentence-transformer embeddings (default `sentence-transformers/all-MiniLM-L6-v2`). Chunk vectors and their model names are stored as portable JSON columns. Ingestion indexes chunks, members can search only within their organization, and owners/admins can rebuild an organization's index after a model change. The API exposes `/api/v1/organizations/{organization_id}/vector-search`, `/api/v1/organizations/{organization_id}/hybrid-search` (keyword/semantic reciprocal-rank fusion followed by local CPU cross-encoder reranking), and `/api/v1/organizations/{organization_id}/vector-index/rebuild`; set `EMBEDDING_MODEL_NAME` to configure the model. Migration `9b71d0c84e26` adds vector fields to chunks. Migration `a4ce92f0017d` adds portable JSON metadata to documents (PDF page count and available properties, DOCX core properties, and image/EXIF properties). Migration `b5d71c2e40af` adds external storage keys while retaining legacy database blobs for existing documents.

Latest validation: `pytest -q` reports 37 passed; Ruff lint and format checks pass; all migrations apply to a fresh SQLite database through head `b5d71c2e40af`. The evaluation harness scores Recall@k, MRR@k, nDCG@k, citation precision/recall, unsupported citations, and abstention behavior against JSON gold cases; its synthetic fixture and HTTP client behavior are covered without external services. It does not automatically assess semantic answer correctness, which remains a human/model-judge evaluation step. Answer generation is covered with deterministic Ollama HTTP/API tests; a live Ollama model was not available for integration validation. OCR behavior is covered using a deterministic test adapter; a real Tesseract smoke test was unavailable because the system executable is not installed in this WSL environment. Remaining roadmap work includes metadata enrichment for additional document formats, semantic answer/groundedness evaluation, observability, and production deployment. Vector search currently scans an organization's indexed chunks in application memory, which is suitable only for modest corpora; a dedicated vector index is needed to scale.

The rest of this report records the original repository snapshot and its findings at the time it was first created.

---

# AtlasAI Project Analysis Report

## Executive summary
AtlasAI is an enterprise knowledge intelligence platform in the early backend foundation stage. The repository is organized around a Python/FastAPI backend, SQLAlchemy data models, Alembic migrations, Docker-based Postgres setup, and a small test suite. The codebase already establishes a solid structure for future enterprise features, but it does not yet implement core platform capabilities such as authentication, permissions, document ingestion, retrieval, or LLM-backed reasoning.

## Repository snapshot
The current project root contains:
- README.md — product vision, roadmap, and architecture overview
- pyproject.toml — Ruff linting and formatting configuration
- backend/ — application code, environment config, migrations, and tests
- infrastructure/docker/docker-compose.yml — PostgreSQL container definition
- LICENSE — MIT license

## Technology stack
- Backend: Python, FastAPI, Pydantic, SQLAlchemy, Alembic
- Database: PostgreSQL
- Infrastructure: Docker Compose for local Postgres
- Quality: Pytest and Ruff
- Planned future stack: vector database, hybrid retrieval, RAG, LLM evaluation, observability, and cloud deployment

## Backend architecture
The backend is organized as a clean modular FastAPI app:

- backend/app/main.py
  - creates the FastAPI app
  - registers the API router
  - exposes the root endpoint
  - sets app metadata such as title and version

- backend/app/api/router.py
  - defines the shared /api/v1 prefix
  - includes the health router

- backend/app/core/config.py
  - uses pydantic-settings for app configuration
  - reads environment variables from .env
  - provides shared settings for app name, version, environment, debug level, and database URL

- backend/app/core/dependencies.py
  - provides a simple settings dependency used by the health endpoint

- backend/app/core/logging.py
  - configures INFO-level logging to stdout

- backend/app/db/base.py
  - defines the SQLAlchemy declarative base class

- backend/app/db/session.py
  - creates the SQLAlchemy engine and session factory using settings.database_url

- backend/app/db/mixins.py
  - adds common created_at and updated_at timestamps to database models

## Domain model and schema
The current core domain model focuses on multi-organization access:

- backend/app/features/organizations/models.py
  - Organization model with UUID primary key, name, and unique slug

- backend/app/features/users/models.py
  - User model with UUID ID, unique email, full name, password hash, and active flag

- backend/app/features/organization_memberships/models.py
  - OrganizationMembership creates a many-to-many relationship between users and organizations
  - uses the MembershipRole enum with OWNER, ADMIN, MEMBER, and VIEWER
  - uses a composite primary key (user_id, organization_id)

This indicates the project has already adopted a role-aware enterprise identity model appropriate for future authorization and permission logic.

## API surface
The current API is minimal but coherent:

- backend/app/features/health/router.py
  - exposes the health endpoint at /api/v1/health
  - returns status and environment metadata

The root path / also returns a simple project status payload.

## Database migrations
The repository contains Alembic migrations that reflect stepwise schema evolution:

- 77a979508d86_create_organizations_table.py
  - creates the organizations table with a unique slug index

- 69edeb326f62_add_organization_timestamp_defaults.py
  - adds server defaults for timestamps

- d053d9ee1eb9_add_users_table.py
  - creates the users table with a unique email index

- 3d6c2e2905a7_add_organization_memberships.py
  - creates the organization_membership join table and foreign keys

This is a mature-enough migration history for a small backend foundation and shows intentional schema growth.

## Test coverage and quality checks
The test suite is small but relevant:

- backend/tests/test_database.py
  - verifies the database connection by executing SELECT 1

- backend/tests/test_organization_memberships.py
  - verifies that a user can join organizations
  - verifies that a user can join multiple organizations
  - verifies duplicate memberships are rejected via database integrity constraints

The project also includes Ruff configuration in pyproject.toml, so linting and style checks are part of the intended engineering workflow.

## Validation status (initial report snapshot)
I ran the backend test suite from the project environment:

- Command: cd ~/atlas/atlas-ai/backend && . .venv/bin/activate && pytest -q
- Result: the test suite currently fails because the PostgreSQL service is not running or unavailable in the current environment.

I also attempted to start the project database through Docker with:

- Command: docker compose -f infrastructure/docker/docker-compose.yml up -d
- Result: Docker is not available inside the current WSL environment because Docker Desktop/WLS integration is not active.

This means the repository is structurally sound, but local runtime validation is blocked by missing database infrastructure.

## Strengths
- Clear product vision and roadmap
- Solid backend structure with feature-based layout
- Strong separation between app config, DB layer, and domain models
- Use of migration-based schema changes rather than ad hoc schema edits
- Includes environment config and Docker local setup
- Minimal but meaningful test coverage for the current domain model

## Gaps and risks (initial report snapshot)
- Authentication and authorization are not implemented yet
- No document ingestion or storage pipeline exists yet
- No retrieval, vector storage, or RAG layer is present yet
- No permission model beyond the membership role enum
- No API endpoints beyond a health check exist yet
- No CI/CD or deployment workflow is configured yet
- No UI or frontend application has been added yet

## Overall assessment
AtlasAI is at an early but thoughtful backend foundation stage. The repository demonstrates good engineering discipline for a greenfield enterprise platform: modular structure, migrations, typed models, and a logical path toward richer features. It is not yet a production-ready knowledge platform, but it is a credible starting point for the next phase of development.

## Recommended next steps
1. Bring up PostgreSQL locally through Docker Desktop or another supported environment.
2. Expand the app with a real authentication layer and org-scoped permissions.
3. Add document ingestion and metadata models.
4. Add retrieval and indexing components.
5. Introduce LLM integration with grounded citation logic.
6. Add richer API tests and CI checks.

## File references
Key files reviewed:
- README.md
- pyproject.toml
- backend/app/main.py
- backend/app/core/config.py
- backend/app/core/dependencies.py
- backend/app/core/logging.py
- backend/app/api/router.py
- backend/app/db/base.py
- backend/app/db/session.py
- backend/app/db/mixins.py
- backend/app/features/organizations/models.py
- backend/app/features/users/models.py
- backend/app/features/organization_memberships/models.py
- backend/app/features/health/router.py
- backend/migrations/versions/*.py
- backend/tests/test_database.py
- backend/tests/test_organization_memberships.py
- infrastructure/docker/docker-compose.yml
