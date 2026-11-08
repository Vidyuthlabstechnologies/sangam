import pytest
import uuid
from uuid import UUID
from httpx import AsyncClient

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
    async def test_register_and_login(self, client: AsyncClient):
        email = f"new-{uuid.uuid4().hex[:8]}@example.com"
        r = await client.post("/auth/register", json={
            "name": "New User", "email": email, "password": "pass123"
        })
        assert r.status_code == 201
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["name"] == "New User"

        r = await client.post("/auth/login", json={
            "email": email, "password": "pass123"
        })
        assert r.status_code == 200
        assert "access_token" in r.json()

    async def test_login_wrong_password(self, client: AsyncClient):
        r = await client.post("/auth/login", json={
            "email": "nonexistent@example.com", "password": "wrong"
        })
        assert r.status_code == 401

    async def test_register_duplicate(self, client: AsyncClient):
        email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
        await client.post("/auth/register", json={
            "name": "A", "email": email, "password": "pass"
        })
        r = await client.post("/auth/register", json={
            "name": "B", "email": email, "password": "pass"
        })
        assert r.status_code == 409

    async def test_token_refresh(self, client: AsyncClient):
        email = f"refresh-{uuid.uuid4().hex[:8]}@example.com"
        r = await client.post("/auth/register", json={
            "name": "Refresh", "email": email, "password": "pass"
        })
        token = r.json()["access_token"]
        r = await client.post("/auth/refresh", json={"token": token})
        assert r.status_code == 200
        assert "access_token" in r.json()


class TestWorkflows:
    async def _register(self, client):
        email = f"wf-{uuid.uuid4().hex[:8]}@example.com"
        r = await client.post("/auth/register", json={
            "name": "WF User", "email": email, "password": "pass"
        })
        data = r.json()
        return data["access_token"], data["actor_id"]

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
        email = f"act-{uuid.uuid4().hex[:8]}@example.com"
        r = await client.post("/auth/register", json={
            "name": "Actor Tester", "email": email, "password": "pass"
        })
        data = r.json()
        return data["access_token"], data["actor_id"]


class TestApprovals:
    async def _auth(self, client):
        email = f"app-{uuid.uuid4().hex[:8]}@example.com"
        r = await client.post("/auth/register", json={
            "name": "Approval Tester", "email": email, "password": "pass"
        })
        data = r.json()
        return data["access_token"], data["actor_id"]

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
        email = f"tmpl-{uuid.uuid4().hex[:8]}@example.com"
        r = await client.post("/auth/register", json={
            "name": "Tmpl Tester", "email": email, "password": "pass"
        })
        return r.json()["access_token"]

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
        email = f"mcp-{uuid.uuid4().hex[:8]}@example.com"
        r = await client.post("/auth/register", json={
            "name": "MCP Tester", "email": email, "password": "pass"
        })
        return r.json()["access_token"]

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
        email = f"cap-{uuid.uuid4().hex[:8]}@example.com"
        r = await client.post("/auth/register", json={
            "name": "Cap Tester", "email": email, "password": "pass"
        })
        return r.json()["access_token"]

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
        email = f"an-{uuid.uuid4().hex[:8]}@example.com"
        r = await client.post("/auth/register", json={"name": "Analyst", "email": email, "password": "pass"})
        token = r.json()["access_token"]
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
