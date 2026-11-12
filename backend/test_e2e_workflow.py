#!/usr/bin/env python3
"""
Complete end-to-end workflow test: register -> login -> create workflow -> 
add actors -> create approval -> approve -> transition phases -> handoff -> complete
"""

import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_sangam.db"
os.environ["JWT_SECRET"] = "test-secret-for-stress-test"
os.environ.setdefault("SARVAM_API_KEY", "")  # set in your shell or backend/.env; never commit keys
os.environ.setdefault("RAZORPAY_KEY_ID", "")  # set in your shell or backend/.env; never commit keys
os.environ.setdefault("RAZORPAY_KEY_SECRET", "")  # set in your shell or backend/.env; never commit keys

import json
import time
import uuid
from typing import Dict, Any

from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_session
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("sqlite+aiosqlite:///./test_sangam.db", echo=False)
import asyncio
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
asyncio.run(create_tables())


client = TestClient(app)
results: Dict[str, Dict[str, Any]] = {}

def test_endpoint(
    name: str,
    method: str,
    path: str,
    token: str = None,
    json_body: dict = None,
    files: dict = None,
    data: dict = None,
) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    start = time.monotonic()
    try:
        if method == "GET":
            resp = client.get(path, headers=headers)
        elif method == "POST":
            if files:
                resp = client.post(path, headers=headers, files=files, data=data)
            else:
                resp = client.post(path, headers=headers, json=json_body)
        elif method == "PATCH":
            resp = client.patch(path, headers=headers, json=json_body)
        elif method == "DELETE":
            resp = client.delete(path, headers=headers)
        elapsed = (time.monotonic() - start) * 1000
        result = {
            "status": resp.status_code,
            "latency_ms": elapsed,
            "success": resp.status_code < 400,
            "response": resp.json() if resp.status_code < 500 else resp.text[:500],
        }
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        result = {"status": "error", "latency_ms": elapsed, "success": False, "error": str(e)}
    results[name] = result
    status_icon = "[OK]" if result.get("success") else "[FAIL]"
    print(f"  {status_icon} {name}: {result.get('status')} ({result.get('latency_ms', 0):.0f}ms)")
    if not result.get("success"):
        print(f"     Error: {result.get('error') or result.get('response')}")
    return result


def main():
    print("=" * 70)
    print("END-TO-END WORKFLOW TEST")
    print("=" * 70)

    # 1. Health
    print("\n[1/20] Health check...")
    test_endpoint("health", "GET", "/health")

    # 2. Register + Login
    email = f"e2e_test_{int(time.time())}@sangam.ai"
    print("\n[2/20] Register user...")
    test_endpoint("register", "POST", "/auth/register", json_body={
        "name": "E2E Tester", "email": email, "password": "test123"
    })

    print("\n[3/20] Login...")
    login = test_endpoint("login", "POST", "/auth/login", json_body={
        "email": email, "password": "test123"
    })
    token = login.get("response", {}).get("access_token") if login.get("success") else None
    actor_id = login.get("response", {}).get("actor_id") if login.get("success") else None
    if not token:
        print("\n[FAIL] No token, aborting")
        return
    print(f"     Actor ID: {actor_id}")

    # 4. Create second actor (approver)
    print("\n[4/20] Create approver actor...")
    appr = test_endpoint("create_approver", "POST", "/actors", token=token, json_body={
        "name": "Approver", "email": "approver@sangam.ai", "type": "human",
        "roles": ["approver"], "permissions": ["read:workflow", "approve"]
    })
    approver_id = appr.get("response", {}).get("id") if appr.get("success") else None
    print(f"     Approver ID: {approver_id}")

    # 5. Create workflow
    print("\n[5/20] Create workflow...")
    wf = test_endpoint("create_workflow", "POST", "/workflows", token=token, json_body={
        "name": "Procurement Approval",
        "description": "Full procurement workflow with approvals",
        "initiator_id": actor_id,
        "phases": ["initiation", "approval", "execution", "verification", "settlement"]
    })
    wf_id = wf.get("response", {}).get("id") if wf.get("success") else None
    print(f"     Workflow ID: {wf_id}")

    if not wf_id:
        print("\n[FAIL] No workflow ID, aborting")
        return

    # 6. List workflows
    print("\n[6/20] List workflows...")
    test_endpoint("list_workflows", "GET", "/workflows", token=token)

    # 7. Get workflow detail
    print("\n[7/20] Get workflow detail...")
    test_endpoint("get_workflow", "GET", f"/workflows/{wf_id}", token=token)

    # 8. Create approval (requires approver)
    print("\n[8/20] Create approval...")
    appr_req = test_endpoint("create_approval", "POST", "/approvals/", token=token, json_body={
        "workflow_id": wf_id,
        "strategy": "all",  # all must approve
        "required_actors": [approver_id, actor_id] if approver_id else [actor_id],
        "description": "Approve procurement request"
    })
    approval_id = appr_req.get("response", {}).get("id") if appr_req.get("success") else None
    print(f"     Approval ID: {approval_id}")

    # 9. Get approval detail
    if approval_id:
        print("\n[9/20] Get approval detail...")
        test_endpoint("get_approval", "GET", f"/approvals/{approval_id}", token=token)

        # 10. Approve
        print("\n[10/20] Approve (as approver - need to login as approver)...")
        # For simplicity, use same token (initiator can also approve if in required_actors)
        appr_result = test_endpoint("approve", "POST", f"/approvals/{approval_id}/approve", token=token, json_body={
            "comments": "Approved for procurement"
        })

        # 11. Transition workflow to next phase
        print("\n[11/20] Transition workflow to approval phase...")
        test_endpoint("transition_approval", "POST", f"/workflows/{wf_id}/transition", token=token, json_body={
            "to_phase": "approval",
            "triggered_by": actor_id,
            "comments": "Moving to approval phase"
        })

    # 12. Create handoff
    print("\n[12/20] Create handoff...")
    handoff = test_endpoint("create_handoff", "POST", "/coordination/handoffs", token=token, json_body={
        "workflow_id": wf_id,
        "from_actor_id": actor_id,
        "to_actor_id": approver_id,
        "artifact": "Purchase Order #PO-2024-001",
        "notes": "Please review and approve the purchase order"
    })
    handoff_id = handoff.get("response", {}).get("id") if handoff.get("success") else None

    # 13. Verify handoff
    if handoff_id:
        print("\n[13/20] Verify handoff...")
        test_endpoint("verify_handoff", "POST", f"/coordination/handoffs/{handoff_id}/verify", token=token, json_body={
            "verified": True,
            "notes": "Purchase order verified"
        })

    # 14. Transition to execution
    print("\n[14/20] Transition to execution...")
    test_endpoint("transition_execution", "POST", f"/workflows/{wf_id}/transition", token=token, json_body={
        "to_phase": "execution",
        "triggered_by": actor_id,
        "comments": "Starting execution"
    })

    # 15. Transition to verification
    print("\n[15/20] Transition to verification...")
    test_endpoint("transition_verification", "POST", f"/workflows/{wf_id}/transition", token=token, json_body={
        "to_phase": "verification",
        "triggered_by": actor_id,
        "comments": "Work complete, verifying"
    })

    # 16. Transition to settlement
    print("\n[16/20] Transition to settlement...")
    test_endpoint("transition_settlement", "POST", f"/workflows/{wf_id}/transition", token=token, json_body={
        "to_phase": "settlement",
        "triggered_by": actor_id,
        "comments": "Verified, settling payment"
    })

    # 17. Create waiting event (exception)
    print("\n[17/20] Create waiting event...")
    test_endpoint("create_waiting_event", "POST", "/coordination/waiting-events", token=token, json_body={
        "workflow_id": wf_id,
        "event_type": "payment_pending",
        "description": "Waiting for vendor payment confirmation",
        "actor_id": actor_id,
    })

    # 18. Get audit logs
    print("\n[18/20] Get audit logs...")
    test_endpoint("audit_logs", "GET", f"/coordination/audit-logs?workflow_id={wf_id}", token=token)

    # 19. Get analytics
    print("\n[19/20] Get analytics...")
    test_endpoint("analytics", "GET", "/analytics/summary", token=token)

    # 20. Complete workflow
    print("\n[20/20] Complete workflow...")
    test_endpoint("complete_workflow", "POST", f"/workflows/{wf_id}/transition", token=token, json_body={
        "to_phase": "settlement",
        "triggered_by": actor_id,
        "comments": "Workflow completed successfully"
    })

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    ok = sum(1 for r in results.values() if r.get("success"))
    total = len(results)
    print(f"Passed: {ok}/{total}")
    for name, r in results.items():
        status = "[OK]" if r.get("success") else "[FAIL]"
        print(f"  {status} {name:30s} {r.get('latency_ms', 0):>8.0f}ms  {r.get('status')}")

    with open("e2e_workflow_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nDetailed results saved to e2e_workflow_test_results.json")


if __name__ == "__main__":
    main()