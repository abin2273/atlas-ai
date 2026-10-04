from uuid import UUID, uuid4

from app.db.session import SessionLocal
from app.features.documents import processing_service
from app.features.documents import router as documents_router
from app.features.documents.embeddings import EmbeddingError
from app.features.documents.models import DocumentChunk
from app.features.documents.reranking import RerankingError
from app.features.documents.schemas import SearchResponse
from app.main import app
from fastapi.testclient import TestClient


def _register(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": "Vector Test", "password": "vector-pass-123"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _create_organization(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/organizations",
        headers=headers,
        json={"name": "Vector Org", "slug": f"vector-{uuid4().hex}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _test_embeddings(texts: list[str]) -> list[list[float]]:
    vectors = []
    for text in texts:
        lowered = text.lower()
        if "orbit" in lowered or "space" in lowered:
            vectors.append([1.0, 0.0, 0.0])
        elif "ocean" in lowered:
            vectors.append([0.0, 1.0, 0.0])
        else:
            vectors.append([0.0, 0.0, 1.0])
    return vectors


def test_vector_search_ranks_semantically_and_requires_org_membership(
    monkeypatch,
) -> None:
    monkeypatch.setattr(documents_router, "embed_texts", _test_embeddings)
    monkeypatch.setattr(processing_service, "embed_texts", _test_embeddings)
    with TestClient(app) as client:
        owner_headers = {
            "Authorization": f"Bearer {_register(client, f'{uuid4()}@example.com')}"
        }
        organization_id = _create_organization(client, owner_headers)
        base_url = f"/api/v1/organizations/{organization_id}"

        unrelated = client.post(
            f"{base_url}/documents",
            headers=owner_headers,
            json={
                "title": "Ocean memo",
                "source_name": "ocean.txt",
                "content": "ocean currents influence shipping lanes",
            },
        )
        relevant = client.post(
            f"{base_url}/documents",
            headers=owner_headers,
            json={
                "title": "Orbital guide",
                "source_name": "orbital.txt",
                "content": "orbit planning supports satellite navigation",
            },
        )
        assert unrelated.status_code == relevant.status_code == 201

        response = client.get(
            f"{base_url}/vector-search",
            headers=owner_headers,
            params={"q": "space navigation"},
        )
        assert response.status_code == 200
        result = SearchResponse.model_validate(response.json()).results[0]
        assert result.document_id == UUID(relevant.json()["id"])
        assert result.score == 1.0
        assert result.citation_id == "[1]"

        outsider_headers = {
            "Authorization": f"Bearer {_register(client, f'{uuid4()}@example.com')}"
        }
        denied = client.get(
            f"{base_url}/vector-search",
            headers=outsider_headers,
            params={"q": "space navigation"},
        )
        assert denied.status_code == 404


def test_hybrid_search_fuses_keyword_and_semantic_rankings(monkeypatch) -> None:
    def hybrid_embeddings(texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            lowered = text.lower()
            if lowered == "hybrid query" or "shared" in lowered:
                vectors.append([1.0, 0.0])
            elif "semantic first" in lowered:
                vectors.append([0.9, 0.43589])
            elif "semantic second" in lowered:
                vectors.append([0.8, 0.6])
            else:
                vectors.append([0.0, 1.0])
        return vectors

    monkeypatch.setattr(documents_router, "embed_texts", hybrid_embeddings)
    monkeypatch.setattr(processing_service, "embed_texts", hybrid_embeddings)

    def test_reranker(query: str, passages: list[str]) -> list[float]:
        assert query == "hybrid query"
        return [0.95 if "keyword evidence" in passage else 0.2 for passage in passages]

    monkeypatch.setattr(documents_router, "rerank_texts", test_reranker)
    with TestClient(app) as client:
        owner_headers = {
            "Authorization": f"Bearer {_register(client, f'{uuid4()}@example.com')}"
        }
        organization_id = _create_organization(client, owner_headers)
        base_url = f"/api/v1/organizations/{organization_id}"

        shared = client.post(
            f"{base_url}/documents",
            headers=owner_headers,
            json={
                "title": "Z Shared result",
                "source_name": "shared.txt",
                "content": "hybrid query shared evidence",
            },
        )
        keyword_only = client.post(
            f"{base_url}/documents",
            headers=owner_headers,
            json={
                "title": "A Keyword-only result",
                "source_name": "keyword.txt",
                "content": "hybrid query hybrid query keyword evidence",
            },
        )
        semantic_first = client.post(
            f"{base_url}/documents",
            headers=owner_headers,
            json={
                "title": "Semantic first filler",
                "source_name": "semantic-first.txt",
                "content": "semantic first related context",
            },
        )
        semantic_second = client.post(
            f"{base_url}/documents",
            headers=owner_headers,
            json={
                "title": "Semantic second filler",
                "source_name": "semantic-second.txt",
                "content": "semantic second related context",
            },
        )
        assert (
            shared.status_code
            == keyword_only.status_code
            == semantic_first.status_code
            == semantic_second.status_code
            == 201
        )

        response = client.get(
            f"{base_url}/hybrid-search",
            headers=owner_headers,
            params={"q": "hybrid query"},
        )
        assert response.status_code == 200
        results = SearchResponse.model_validate(response.json()).results
        assert results[0].document_id == UUID(keyword_only.json()["id"])
        assert results[0].citation_id == "[1]"
        assert results[0].score == 0.95
        assert results[0].score > results[1].score
        keyword_result = next(
            result
            for result in results
            if result.document_id == UUID(keyword_only.json()["id"])
        )
        assert results[0].score == keyword_result.score

        outsider_headers = {
            "Authorization": f"Bearer {_register(client, f'{uuid4()}@example.com')}"
        }
        denied = client.get(
            f"{base_url}/hybrid-search",
            headers=outsider_headers,
            params={"q": "hybrid query"},
        )
        assert denied.status_code == 404


def test_hybrid_search_surfaces_local_reranker_failures(monkeypatch) -> None:
    def fail_reranking(query: str, passages: list[str]) -> list[float]:
        raise RerankingError("Test reranker failure")

    monkeypatch.setattr(documents_router, "rerank_texts", fail_reranking)
    with TestClient(app) as client:
        owner_headers = {
            "Authorization": f"Bearer {_register(client, f'{uuid4()}@example.com')}"
        }
        organization_id = _create_organization(client, owner_headers)
        response = client.get(
            f"/api/v1/organizations/{organization_id}/hybrid-search",
            headers=owner_headers,
            params={"q": "semantic query"},
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Test reranker failure"


def test_vector_index_rebuild_is_admin_only(monkeypatch) -> None:
    monkeypatch.setattr(documents_router, "embed_texts", _test_embeddings)
    monkeypatch.setattr(processing_service, "embed_texts", _test_embeddings)
    with TestClient(app) as client:
        owner_headers = {
            "Authorization": f"Bearer {_register(client, f'{uuid4()}@example.com')}"
        }
        member_email = f"{uuid4()}@example.com"
        member_headers = {"Authorization": f"Bearer {_register(client, member_email)}"}
        organization_id = _create_organization(client, owner_headers)
        response = client.post(
            f"/api/v1/organizations/{organization_id}/members",
            headers=owner_headers,
            json={"email": member_email, "role": "MEMBER"},
        )
        assert response.status_code == 201

        indexed = client.post(
            f"/api/v1/organizations/{organization_id}/documents",
            headers=owner_headers,
            json={
                "title": "Indexable",
                "source_name": "indexable.txt",
                "content": "orbit and satellite references",
            },
        )
        assert indexed.status_code == 201
        with SessionLocal() as db:
            chunk = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == UUID(indexed.json()["id"]))
                .one()
            )
            chunk.embedding = None
            chunk.embedding_model = None
            db.commit()

        endpoint = f"/api/v1/organizations/{organization_id}/vector-index/rebuild"
        denied = client.post(endpoint, headers=member_headers)
        assert denied.status_code == 403
        rebuilt = client.post(endpoint, headers=owner_headers)
        assert rebuilt.status_code == 200
        assert rebuilt.json()["indexed_chunks"] == 1


def test_embedding_failure_is_saved_as_document_processing_failure(monkeypatch) -> None:
    def fail_embeddings(_: list[str]) -> list[list[float]]:
        raise EmbeddingError("Test embedding model failure")

    monkeypatch.setattr(documents_router, "embed_texts", fail_embeddings)
    monkeypatch.setattr(processing_service, "embed_texts", fail_embeddings)
    with TestClient(app) as client:
        owner_headers = {
            "Authorization": f"Bearer {_register(client, f'{uuid4()}@example.com')}"
        }
        organization_id = _create_organization(client, owner_headers)
        response = client.post(
            f"/api/v1/organizations/{organization_id}/documents",
            headers=owner_headers,
            json={
                "title": "Failed index",
                "source_name": "failed.txt",
                "content": "an embedding failure should persist",
            },
        )
        assert response.status_code == 201
        assert response.json()["processing_status"] == "FAILED"
        assert response.json()["processing_error"] == "Test embedding model failure"
