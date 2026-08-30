from __future__ import annotations

from uuid import uuid4

from app.services import project_repository as proj_repo


def test_compare_rejects_fewer_than_two_papers(client, monkeypatch):
    project_id = uuid4()

    async def fake_get_project(pid):
        return {"id": project_id}

    monkeypatch.setattr(proj_repo, "get_project", fake_get_project)

    response = client.post(
        f"/api/projects/{project_id}/compare", json={"document_ids": [str(uuid4())]}
    )
    # pydantic min_length=2 on CompareRequest.document_ids rejects this before
    # any service logic runs
    assert response.status_code == 422


def test_compare_rejects_unindexed_papers(client, monkeypatch):
    project_id = uuid4()
    doc_a, doc_b = uuid4(), uuid4()

    async def fake_get_project(pid):
        return {"id": project_id}

    async def fake_get_indexed_ids(pid):
        return [doc_a]  # doc_b is not indexed yet

    monkeypatch.setattr(proj_repo, "get_project", fake_get_project)
    monkeypatch.setattr(proj_repo, "get_indexed_document_ids", fake_get_indexed_ids)

    response = client.post(
        f"/api/projects/{project_id}/compare",
        json={"document_ids": [str(doc_a), str(doc_b)]},
    )
    assert response.status_code == 422
    assert "indexed" in response.json()["detail"].lower()


def test_gap_analysis_requires_at_least_two_indexed_papers(client, monkeypatch):
    project_id = uuid4()

    async def fake_get_project(pid):
        return {"id": project_id}

    async def fake_get_indexed_ids(pid):
        return [uuid4()]  # only one indexed paper

    monkeypatch.setattr(proj_repo, "get_project", fake_get_project)
    monkeypatch.setattr(proj_repo, "get_indexed_document_ids", fake_get_indexed_ids)

    response = client.post(f"/api/projects/{project_id}/gap-analysis", json={})
    assert response.status_code == 422
