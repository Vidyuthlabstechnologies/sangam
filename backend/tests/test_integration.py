import pytest
import uuid
from uuid import UUID
from httpx import AsyncClient

from tests.identity_tokens import login

pytestmark = pytest.mark.asyncio


class TestHealth:
    async def test_health(self, client: AsyncClient):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    async def test_openapi(self, client: AsyncClient):
        r = await client.get("/openapi.json")
        assert r.status_code == 200
        assert "/health" in r.json()["paths"]


class TestAuth:
    async def test_password_login_and_register_do_not_issue_tokens(self, client: AsyncClient, db_session):
        from sqlalchemy import func, select
        from app.models.actor import Actor

        before = await db_session.scalar(select(func.count()).select_from(Actor))
        email = f"new-{uuid.uuid4().hex[:8]}@example.com"
        registered = await client.post("/auth/register", json={
            "name": "New User", "email": email, "password": "pass123"
        })
        logged_in = await client.post("/auth/login", json={
            "email": email, "password": "pass123"
        })
        refreshed = await client.post("/auth/refresh", json={"token": "pass123"})
        after = await db_session.scalar(select(func.count()).select_from(Actor))
        for response in (registered, logged_in, refreshed):
            assert response.status_code == 410, response.text
            assert "access_token" not in response.json()
        assert before == after

    async def test_jit_actor_from_access_token(self, client: AsyncClient):
        token, actor_id = await login(client, name="New User")
        me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["actor_id"] == actor_id
        assert me.json()["name"] == "New User"
        assert me.json()["organization_id"]


class TestWorkflows:
    async def _register(self, client):
        return await login(client, name="WF User")

    async def test_create_workflow(self, client):
        token, actor_id = await self._register(client)
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.post("/workflows/", json={
            "name": "Test Procurement",
            "description": "Integration test workflow",
            "initiator_id": actor_id,
            "phases": ["initiation", "approval", "execution"],
        }, headers=headers)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Test Procurement"
        assert data["state"] == "draft"
        assert "id" in data

    async def test_workflow_lifecycle(self, client):
        token, actor_id = await self._register(client)
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.post("/workflows/", json={
            "name": "Lifecycle Test", "initiator_id": actor_id,
        }, headers=headers)
        wf_id = r.json()["id"]

        await client.patch(f"/workflows/{wf_id}", json={
            "state": "active"
        }, headers=headers)

        r = await client.post(f"/workflows/{wf_id}/pause", headers=headers)
        assert r.status_code == 200
        assert r.json()["state"] == "paused"

        r = await client.post(f"/workflows/{wf_id}/resume", headers=headers)
        assert r.status_code == 200
        assert r.json()["state"] == "active"

        r = await client.post(f"/workflows/{wf_id}/cancel", headers=headers)
        assert r.status_code == 200
        assert r.json()["state"] == "failed"

    async def test_list_get_update_delete(self, client):
        token, actor_id = await self._register(client)
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.post("/workflows/", json={
            "name": "CRUD Test", "initiator_id": actor_id,
        }, headers=headers)
        wf_id = r.json()["id"]

        r = await client.get("/workflows/", headers=headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1

        r = await client.get(f"/workflows/{wf_id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["id"] == wf_id

        r = await client.patch(f"/workflows/{wf_id}", json={
            "name": "Updated Name"
        }, headers=headers)
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Name"

        r = await client.delete(f"/workflows/{wf_id}", headers=headers)
        assert r.status_code == 204


class TestActors:
    async def test_crud(self, client):
        token, actor_id = await self._auth(client)
        headers = {"Authorization": f"Bearer {token}"}

        r = await client.post("/actors/", json={
            "type": "agent", "name": "ProcurementBot", "roles": ["executor"],
        }, headers=headers)
        assert r.status_code == 201
        assert r.json()["name"] == "ProcurementBot"
        agent_id = r.json()["id"]

        r = await client.get("/actors/", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

        r = await client.get(f"/actors/{agent_id}", headers=headers)
        assert r.status_code == 200

        r = await client.patch(f"/actors/{agent_id}", json={"name": "BotV2"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["name"] == "BotV2"

        r = await client.delete(f"/actors/{agent_id}", headers=headers)
        assert r.status_code == 204

    async def _auth(self, client):
        return await login(client, name="Actor Tester")


class TestApprovals:
    async def _auth(self, client):
        return await login(client, name="Approval Tester")

    async def test_approval_lifecycle(self, client):
        token, actor_id = await self._auth(client)
        headers = {"Authorization": f"Bearer {token}"}
        wf = await client.post("/workflows/", json={
            "name": "Approval Test", "initiator_id": actor_id,
        }, headers=headers)
        wf_id = wf.json()["id"]

        r = await client.post("/approvals/", json={
            "workflow_id": wf_id,
            "required_actors": [actor_id],
            "strategy": "all",
        }, headers=headers)
        assert r.status_code == 201
        approval_id = r.json()["id"]

        r = await client.post(f"/approvals/{approval_id}/approve", headers=headers)
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

    async def test_approval_reject(self, client):
        token, actor_id = await self._auth(client)
        headers = {"Authorization": f"Bearer {token}"}
        wf = await client.post("/workflows/", json={
            "name": "Reject Test", "initiator_id": actor_id,
        }, headers=headers)
        wf_id = wf.json()["id"]
        r = await client.post("/approvals/", json={
            "workflow_id": wf_id,
            "required_actors": [actor_id],
            "strategy": "all",
        }, headers=headers)
        approval_id = r.json()["id"]

        r = await client.post(f"/approvals/{approval_id}/reject", headers=headers)
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"

    async def test_approval_escalate_delegate(self, client):
        token, actor_id = await self._auth(client)
        headers = {"Authorization": f"Bearer {token}"}
        wf = await client.post("/workflows/", json={
            "name": "Escalate Test", "initiator_id": actor_id,
        }, headers=headers)
        wf_id = wf.json()["id"]
        r = await client.post("/approvals/", json={
            "workflow_id": wf_id,
            "required_actors": [actor_id],
            "strategy": "any",
        }, headers=headers)
        approval_id = r.json()["id"]
        other_id = uuid.uuid4()

        r = await client.post(f"/approvals/{approval_id}/escalate", json={
            "escalated_to": str(other_id),
        }, headers=headers)
        assert r.status_code == 200
        assert r.json()["escalated_to"] == str(other_id)


class TestTemplates:
    async def _auth(self, client):
        token, _actor_id = await login(client, name="Tmpl Tester")
        return token

    async def test_list_and_get(self, client):
        token = await self._auth(client)
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.get("/templates/", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

        r = await client.get("/templates/categories", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

        templates = (await client.get("/templates/", headers=headers)).json()
        if templates:
            tid = templates[0]["id"]
            r = await client.get(f"/templates/{tid}", headers=headers)
            assert r.status_code == 200
            assert r.json()["id"] == tid


class TestMCP:
    async def _auth(self, client):
        token, _actor_id = await login(client, name="MCP Tester")
        return token

    async def test_list_and_manifest(self, client):
        token = await self._auth(client)
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.get("/mcp/servers", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

        servers = r.json()
        if servers:
            name = servers[0]["name"]
            r = await client.get(f"/mcp/servers/{name}/manifest", headers=headers)
            assert r.status_code == 200


class TestCapabilities:
    async def _auth(self, client):
        token, _actor_id = await login(client, name="Cap Tester")
        return token

    @pytest.mark.skip(reason="Requires Qdrant running on localhost:6333")
    async def test_register_search_delete(self, client):
        token = await self._auth(client)
        headers = {"Authorization": f"Bearer {token}"}

        r = await client.post("/capabilities/register", json={
            "name": "Purchase Order API",
            "description": "Create and manage POs",
            "service_type": "api",
            "tags": ["purchase", "order"],
        }, headers=headers)
        assert r.status_code == 201
        cap_id = r.json()["id"]

        r = await client.get("/capabilities/search?q=purchase&limit=10", headers=headers)
        assert r.status_code == 200

        r = await client.get("/capabilities/", headers=headers)
        assert r.status_code == 200

        r = await client.delete(f"/capabilities/{cap_id}", headers=headers)
        assert r.status_code == 204


class TestAnalytics:
    async def _headers(self, client):
        token, _actor_id = await login(client, name="Analyst")
        return {"Authorization": f"Bearer {token}"}

    async def test_summary(self, client: AsyncClient):
        headers = await self._headers(client)
        r = await client.get("/analytics/summary", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "total_workflows" in data
        assert "active_workflows" in data
        assert "total_actors" in data

    async def test_workflows_by_state(self, client: AsyncClient):
        headers = await self._headers(client)
        r = await client.get("/analytics/workflows-by-state", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
