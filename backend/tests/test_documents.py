from uuid import uuid4

from app.features.documents.router import CHUNK_SIZE, _split_content
from app.main import app
from fastapi.testclient import TestClient


def register(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": "Test User", "password": "test-password-123"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def test_authentication_and_organization_scoped_document_search() -> None:
    with TestClient(app) as client:
        owner_email = f"{uuid4()}@example.com"
        owner_token = register(client, owner_email)
        login = client.post(
            "/api/v1/auth/login",
            json={"email": owner_email.upper(), "password": "test-password-123"},
        )
        assert login.status_code == 200
        assert login.json()["user"]["email"] == owner_email
        invalid_login = client.post(
            "/api/v1/auth/login",
            json={"email": owner_email, "password": "incorrect-password"},
        )
        assert invalid_login.status_code == 401
        owner_headers = {"Authorization": f"Bearer {owner_token}"}

        organization = client.post(
            "/api/v1/organizations",
            headers=owner_headers,
            json={"name": "Search Test Org", "slug": f"search-{uuid4().hex}"},
        )
        assert organization.status_code == 201
        organization_id = organization.json()["id"]

        document_payload = {
            "title": "Operations Guide",
            "source_name": "operations.md",
            "content_type": "text/markdown",
            "content": "Atlas uses cobalt indexing for grounded enterprise search.",
        }
        document = client.post(
            f"/api/v1/organizations/{organization_id}/documents",
            headers=owner_headers,
            json=document_payload,
        )
        assert document.status_code == 201
        assert "content" not in document.json()
        detail = client.get(
            f"/api/v1/organizations/{organization_id}/documents/{document.json()['id']}",
            headers=owner_headers,
        )
        assert detail.status_code == 200
        assert detail.json()["content"] == document_payload["content"]

        search = client.get(
            f"/api/v1/organizations/{organization_id}/search",
            headers=owner_headers,
            params={"q": "cobalt indexing"},
        )
        assert search.status_code == 200
        assert search.json()["results"][0]["document_id"] == document.json()["id"]
        assert "cobalt" in search.json()["results"][0]["excerpt"]

        retrieval = client.get(
            f"/api/v1/organizations/{organization_id}/retrieve",
            headers=owner_headers,
            params={"q": "cobalt indexing"},
        )
        assert retrieval.status_code == 200
        citation = retrieval.json()["citations"][0]
        assert citation["citation_id"] == "[1]"
        assert citation["document_id"] == document.json()["id"]
        assert citation["chunk_id"]

        duplicate = client.post(
            f"/api/v1/organizations/{organization_id}/documents",
            headers=owner_headers,
            json={**document_payload, "title": "Duplicate"},
        )
        assert duplicate.status_code == 409

        viewer_email = f"{uuid4()}@example.com"
        viewer_token = register(client, viewer_email)
        add_viewer = client.post(
            f"/api/v1/organizations/{organization_id}/members",
            headers=owner_headers,
            json={"email": viewer_email, "role": "VIEWER"},
        )
        assert add_viewer.status_code == 201

        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
        viewer_read = client.get(
            f"/api/v1/organizations/{organization_id}/documents",
            headers=viewer_headers,
        )
        assert viewer_read.status_code == 200
        assert len(viewer_read.json()) == 1

        viewer_write = client.post(
            f"/api/v1/organizations/{organization_id}/documents",
            headers=viewer_headers,
            json={
                **document_payload,
                "title": "Viewer upload",
                "content": "Different content.",
            },
        )
        assert viewer_write.status_code == 403

        other_token = register(client, f"{uuid4()}@example.com")
        other_read = client.get(
            f"/api/v1/organizations/{organization_id}/documents",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert other_read.status_code == 404


def test_invalid_bearer_token_is_rejected() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid.token"},
        )
        assert response.status_code == 401


def test_document_chunking_respects_size_and_overlap() -> None:
    content = "x" * (CHUNK_SIZE * 2 + 100)
    chunks = _split_content(content)

    assert len(chunks) == 3
    assert all(0 < len(chunk) <= CHUNK_SIZE for chunk in chunks)
    assert chunks[0][-100:] == chunks[1][:100]
