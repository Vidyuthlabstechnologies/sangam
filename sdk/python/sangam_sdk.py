"""
Sangam Python SDK — AI-Native Coordination Platform

Usage:
    from sangam_sdk import SangamClient

    client = SangamClient(api_key="...", base_url="https://api.sangam.ai")

    # Create a workflow
    workflow = client.workflows.create(
        name="Procurement Request",
        description="Order IT equipment",
        initiator_id="actor-uuid",
    )

    # List workflows
    workflows = client.workflows.list()

    # Approve
    client.approvals.approve("approval-uuid")
"""

import os
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx


class SangamClientError(Exception):
    pass


class WorkflowsAPI:
    def __init__(self, client: "SangamClient"):
        self._client = client

    def create(
        self,
        name: str,
        initiator_id: str,
        description: Optional[str] = None,
        phases: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._client._post(
            "/workflows",
            json={
                "name": name,
                "initiator_id": initiator_id,
                "description": description,
                "phases": phases,
                "metadata": metadata,
            },
        )

    def list(
        self,
        page: int = 1,
        page_size: int = 20,
        state: Optional[str] = None,
        phase: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = {"page": page, "page_size": page_size}
        if state:
            params["state"] = state
        if phase:
            params["current_phase"] = phase
        return self._client._get("/workflows", params=params)

    def get(self, workflow_id: str) -> Dict[str, Any]:
        return self._client._get(f"/workflows/{workflow_id}")

    def update(self, workflow_id: str, **kwargs) -> Dict[str, Any]:
        return self._client._patch(f"/workflows/{workflow_id}", json=kwargs)

    def pause(self, workflow_id: str) -> Dict[str, Any]:
        return self._client._post(f"/workflows/{workflow_id}/pause")

    def resume(self, workflow_id: str) -> Dict[str, Any]:
        return self._client._post(f"/workflows/{workflow_id}/resume")

    def cancel(self, workflow_id: str) -> Dict[str, Any]:
        return self._client._post(f"/workflows/{workflow_id}/cancel")

    def delete(self, workflow_id: str) -> None:
        self._client._delete(f"/workflows/{workflow_id}")


class ActorsAPI:
    def __init__(self, client: "SangamClient"):
        self._client = client

    def create(
        self,
        type: str,
        name: str,
        email: Optional[str] = None,
        roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._client._post(
            "/actors",
            json={
                "type": type,
                "name": name,
                "email": email,
                "roles": roles or [],
                "permissions": permissions or [],
                "metadata": metadata,
            },
        )

    def list(self) -> List[Dict[str, Any]]:
        return self._client._get("/actors")

    def get(self, actor_id: str) -> Dict[str, Any]:
        return self._client._get(f"/actors/{actor_id}")


class ApprovalsAPI:
    def __init__(self, client: "SangamClient"):
        self._client = client

    def get(self, approval_id: str) -> Dict[str, Any]:
        return self._client._get(f"/approvals/{approval_id}")

    def approve(self, approval_id: str) -> Dict[str, Any]:
        return self._client._post(f"/approvals/{approval_id}/approve")

    def reject(self, approval_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        return self._client._post(f"/approvals/{approval_id}/reject", json={"reason": reason})


class SangamClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.sangam.ai/v1",
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key or os.environ.get("SANGAM_API_KEY")
        if not self._api_key:
            raise SangamClientError(
                "API key required. Set SANGAM_API_KEY env var or pass api_key."
            )
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        self.workflows = WorkflowsAPI(self)
        self.actors = ActorsAPI(self)
        self.approvals = ApprovalsAPI(self)

    def _request(self, method: str, path: str, **kwargs) -> Any:
        response = self._client.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise SangamClientError(
                f"API error {response.status_code}: {response.text}"
            )
        if response.status_code == 204:
            return None
        return response.json()

    def _get(self, path: str, **kwargs) -> Any:
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs) -> Any:
        return self._request("POST", path, **kwargs)

    def _patch(self, path: str, **kwargs) -> Any:
        return self._request("PATCH", path, **kwargs)

    def _delete(self, path: str, **kwargs) -> Any:
        return self._request("DELETE", path, **kwargs)

    def close(self):
        self._client.close()
