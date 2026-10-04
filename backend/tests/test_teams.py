from uuid import uuid4

from app.main import app
from fastapi.testclient import TestClient


def register(client: TestClient, email: str) -> tuple[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "name": "Team Test User",
            "password": "test-password-123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    return data["access_token"], data["user"]["id"]


def test_team_management_requires_org_membership_and_cleans_up() -> None:
    with TestClient(app) as client:
        owner_email = f"{uuid4()}@example.com"
        owner_token, _ = register(client, owner_email)
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        outsider_email = f"{uuid4()}@example.com"
        outsider_token, outsider_id = register(client, outsider_email)
        outsider_headers = {"Authorization": f"Bearer {outsider_token}"}

        organization = client.post(
            "/api/v1/organizations",
            headers=owner_headers,
            json={"name": "Team Test Org", "slug": f"team-org-{uuid4().hex}"},
        )
        assert organization.status_code == 201
        organization_id = organization.json()["id"]
        teams_url = f"/api/v1/organizations/{organization_id}/teams"

        assert client.get(teams_url, headers=outsider_headers).status_code == 404
        assert (
            client.post(
                teams_url,
                headers=outsider_headers,
                json={"name": "Unauthorized", "slug": "unauthorized"},
            ).status_code
            == 404
        )

        created = client.post(
            teams_url,
            headers=owner_headers,
            json={"name": "Research", "slug": "Research-Team"},
        )
        assert created.status_code == 201
        team = created.json()
        assert team["slug"] == "research-team"
        assert team["organization_id"] == organization_id

        duplicate_slug = client.post(
            teams_url,
            headers=owner_headers,
            json={"name": "Another Research", "slug": "research-team"},
        )
        assert duplicate_slug.status_code == 409

        members_url = f"{teams_url}/{team['id']}/members"
        non_org_member = client.post(
            members_url,
            headers=owner_headers,
            json={"email": outsider_email},
        )
        assert non_org_member.status_code == 409

        added_to_org = client.post(
            f"/api/v1/organizations/{organization_id}/members",
            headers=owner_headers,
            json={"email": outsider_email, "role": "MEMBER"},
        )
        assert added_to_org.status_code == 201
        member_cannot_create_team = client.post(
            teams_url,
            headers=outsider_headers,
            json={"name": "Forbidden Team", "slug": "forbidden-team"},
        )
        assert member_cannot_create_team.status_code == 403

        added_to_team = client.post(
            members_url,
            headers=owner_headers,
            json={"email": outsider_email.upper()},
        )
        assert added_to_team.status_code == 201
        assert added_to_team.json()["user_id"] == outsider_id
        assert (
            client.post(
                members_url,
                headers=owner_headers,
                json={"email": outsider_email},
            ).status_code
            == 409
        )
        assert len(client.get(members_url, headers=outsider_headers).json()) == 1

        removed_from_org = client.delete(
            f"/api/v1/organizations/{organization_id}/members/{outsider_id}",
            headers=owner_headers,
        )
        assert removed_from_org.status_code == 204
        assert client.get(teams_url, headers=outsider_headers).status_code == 404
        assert client.get(members_url, headers=owner_headers).json() == []

        deleted = client.delete(
            f"{teams_url}/{team['id']}",
            headers=owner_headers,
        )
        assert deleted.status_code == 204
        assert client.get(members_url, headers=owner_headers).status_code == 404
