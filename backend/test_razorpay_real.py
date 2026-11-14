#!/usr/bin/env python3
"""
Real-world Razorpay payment integration test using FastAPI TestClient (in-process).
Validates actual Razorpay API calls, order creation, payment verification, escrow.
"""

import os
# MUST set before importing app to use SQLite for testing
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

# Create tables before running tests
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
    print("RAZORPAY REAL INTEGRATION TEST (TestClient)")
    print("=" * 70)

    # 1. Health check
    print("\n[1/12] Health check...")
    test_endpoint("health", "GET", "/health")

    # 2. Register user
    print("\n[2/12] Register user...")
    reg = test_endpoint("register", "POST", "/auth/register", json_body={
        "name": "Payment Tester", "email": "payment_test@sangam.ai", "password": "test123"
    })

    # 3. Login
    print("\n[3/12] Login...")
    login = test_endpoint("login", "POST", "/auth/login", json_body={
        "email": "payment_test@sangam.ai", "password": "test123"
    })
    token = login.get("response", {}).get("access_token") if login.get("success") else None
    actor_id = login.get("response", {}).get("actor_id") if login.get("success") else None
    if not token:
        print("\n[FAIL] No token, aborting")
        return
    print(f"     Got token: {token[:20]}...")
    print(f"     Actor ID: {actor_id}")

    # 4. Create workflow (with proper UUID and lowercase phases)
    print("\n[4/12] Create workflow...")
    wf = test_endpoint("create_workflow", "POST", "/workflows", token=token, json_body={
        "name": "Payment Test Workflow",
        "description": "Test workflow for Razorpay integration",
        "initiator_id": actor_id,  # Use the logged-in actor's UUID
        "phases": ["initiation", "approval", "execution", "verification", "settlement"]
    })
    wf_id = wf.get("response", {}).get("id") if wf.get("success") else None
    print(f"     Workflow ID: {wf_id}")

    if not wf_id:
        print("\n[FAIL] No workflow ID, aborting payment tests")
        return

    # 5. Initiate Razorpay payment
    print("\n[5/12] Initiate Razorpay payment...")
    pay = test_endpoint("initiate_payment", "POST", "/payments/initiate", token=token, json_body={
        "workflow_id": wf_id,
        "amount": 50000,  # 500 INR in paise
        "currency": "INR",
        "description": "Test payment for workflow",
        "payer_actor_id": actor_id,
    })
    order_id = pay.get("response", {}).get("order_id") if pay.get("success") else None
    payment_id = pay.get("response", {}).get("payment_id") if pay.get("success") else None
    print(f"     Order ID: {order_id}")
    print(f"     Payment ID: {payment_id}")

    # 6. Get payment details
    if payment_id:
        print("\n[6/12] Get payment details...")
        test_endpoint("get_payment", "GET", f"/payments/{payment_id}", token=token)

    # 7. Verify payment (simulated - in real flow this comes from frontend callback)
    # We'll use a test signature since we can't actually complete Razorpay checkout
    print("\n[7/12] Verify payment (test signature)...")
    test_endpoint("verify_payment", "POST", "/payments/verify", token=token, json_body={
        "razorpay_order_id": order_id or "order_test",
        "razorpay_payment_id": "pay_test123",
        "razorpay_signature": "test_signature",
    })

    # 8. Create escrow
    print("\n[8/12] Create escrow...")
    escrow_resp = test_endpoint("create_escrow", "POST", "/payments/escrow", token=token, json_body={
        "workflow_id": wf_id,
        "payment_id": payment_id,
        "amount": 50000,
        "release_condition": "delivery_confirmed",
    })
    escrow_id = escrow_resp.get("response", {}).get("id") if escrow_resp.get("success") else None
    print(f"     Escrow ID: {escrow_id}")

    # 9. Release escrow
    if escrow_id:
        print("\n[9/12] Release escrow...")
        test_endpoint("release_escrow", "POST", f"/payments/escrow/{escrow_id}/release", token=token)

    # 10. Create invoice
    print("\n[10/12] Create invoice...")
    test_endpoint("create_invoice", "POST", "/payments/invoices", token=token, json_body={
        "workflow_id": wf_id,
        "payment_id": payment_id,
        "amount": 50000,
        "description": "Test invoice",
        "tax_amount": 9000,
        "payer_name": "Test Buyer",
        "payer_gst": "29AAAAA0000A1Z5",
        "payee_name": "Test Seller",
        "payee_gst": "29BBBBB0000B1Z5",
    })

    # 11. Get invoice
    # (need invoice ID from previous step - skip for now)

    # 12. Refund payment
    if payment_id:
        print("\n[11/12] Refund payment...")
        test_endpoint("refund_payment", "POST", f"/payments/{payment_id}/refund", token=token, json_body={
            "amount": 50000,
            "reason": "Test refund",
        })

    # 13. Webhook test (simulate Razorpay webhook)
    print("\n[12/12] Test webhook handler...")
    test_endpoint("webhook", "POST", "/payments/webhook", json_body={
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test123",
                    "order_id": order_id or "order_test",
                    "amount": 50000,
                    "currency": "INR",
                    "status": "captured",
                }
            }
        }
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

    # Save detailed results
    with open("razorpay_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nDetailed results saved to razorpay_test_results.json")


if __name__ == "__main__":
    main()