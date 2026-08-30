from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.services import project_repository as proj_repo
from app.services.project_repository import ProjectNotFoundError


def _fake_project_row(project_id, name="Transformer-Based Medical Image Analysis"):
    now = datetime.now(timezone.utc)
    return {
        "id": project_id,
        "name": name,
        "description": "A test project",
        "document_count": 0,
        "indexed_count": 0,
        "created_at": now,
        "updated_at": now,
    }


def test_create_project(client, monkeypatch):
    project_id = uuid4()

    async def fake_create_project(name, description):
        assert name == "Transformer-Based Medical Image Analysis"
        return project_id

    async def fake_get_project(pid):
        assert pid == project_id
        return _fake_project_row(project_id)

    monkeypatch.setattr(proj_repo, "create_project", fake_create_project)
    monkeypatch.setattr(proj_repo, "get_project", fake_get_project)

    response = client.post(
        "/api/projects",
        json={"name": "Transformer-Based Medical Image Analysis", "description": "A test project"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(project_id)
    assert body["document_count"] == 0


def test_create_project_rejects_empty_name(client):
    response = client.post("/api/projects", json={"name": ""})
    assert response.status_code == 422


def test_get_project_success(client, monkeypatch):
    project_id = uuid4()

    async def fake_get_project(pid):
        return _fake_project_row(project_id)

    monkeypatch.setattr(proj_repo, "get_project", fake_get_project)

    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(project_id)


def test_get_project_not_found(client, monkeypatch):
    project_id = uuid4()

    async def fake_get_project(pid):
        raise ProjectNotFoundError(f"No research project with id {pid}")

    monkeypatch.setattr(proj_repo, "get_project", fake_get_project)

    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 404


def test_list_projects(client, monkeypatch):
    p1, p2 = uuid4(), uuid4()

    async def fake_list_projects():
        return [_fake_project_row(p1, "Project A"), _fake_project_row(p2, "Project B")]

    monkeypatch.setattr(proj_repo, "list_projects", fake_list_projects)

    response = client.get("/api/projects")
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert names == ["Project A", "Project B"]
