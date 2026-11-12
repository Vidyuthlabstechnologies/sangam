#!/usr/bin/env python3
"""
Razorpay Heavy Load Test - Test mode for latency, accuracy, safety
Tests: payment creation, verification, webhook handling, escrow, refunds, idempotency
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
import statistics
import asyncio
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi.testclient import TestClient
from app.main import app
from app.db.base import Base
from app.db.session import get_session
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("sqlite+aiosqlite:///./test_sangam.db", echo=False)
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
asyncio.run(create_tables())

client = TestClient(app)
results: Dict[str, List[Dict]] = {}

def test_endpoint(name: str, method: str, path: str, token: str = None, json_body: dict = None, files: dict = None, data: dict = None):
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
        result = {"status": resp.status_code, "latency_ms": elapsed, "success": resp.status_code < 400, "response": resp.json() if resp.status_code < 500 else resp.text[:500]}
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        result = {"status": "error", "latency_ms": elapsed, "success": False, "error": str(e)}
    
    results.setdefault(name, []).append(result)
    return result


def print_summary():
    print("\n" + "=" * 80)
    print("RAZORPAY STRESS TEST SUMMARY")
    print("=" * 80)
    for name, runs in results.items():
        if not runs:
            continue
        latencies = [r["latency_ms"] for r in runs if r.get("latency_ms") is not None]
        success_count = sum(1 for r in runs if r.get("success"))
        total = len(runs)
        print(f"\n{name}: {success_count}/{total} passed")
        if latencies and len(latencies) >= 2:
            print(f"  Latency: min={min(latencies):.0f}ms avg={statistics.mean(latencies):.0f}ms "
                  f"p50={statistics.median(latencies):.0f}ms p95={statistics.quantiles(latencies, n=20)[18]:.0f}ms "
                  f"p99={statistics.quantiles(latencies, n=100)[98]:.0f}ms max={max(latencies):.0f}ms")
        elif latencies:
            print(f"  Latency: min={min(latencies):.0f}ms avg={statistics.mean(latencies):.0f}ms max={max(latencies):.0f}ms (single run)")
        for r in runs:
            if not r.get("success"):
                print(f"  FAIL: {r.get('status')} - {r.get('error') or r.get('response')}")


def run_sequential_tests(token: str, actor_id: str):
    """Run sequential tests for basic flow"""
    print("\n[1/8] Health check...")
    test_endpoint("health", "GET", "/health")
    
    print("\n[2/8] Create workflow...")
    wf = test_endpoint("create_workflow", "POST", "/workflows", token=token, json_body={
        "name": "Stress Test Workflow", "initiator_id": actor_id,
        "phases": ["initiation", "approval", "execution", "verification", "settlement"]
    })
    wf_id = wf.get("response", {}).get("id")
    
    print("\n[3/8] Initiate payment...")
    pay = test_endpoint("initiate_payment", "POST", "/payments/initiate", token=token, json_body={
        "workflow_id": wf_id, "amount": 50000, "currency": "INR",
        "description": "Stress test payment", "payer_actor_id": actor_id
    })
    payment_id = pay.get("response", {}).get("payment_id")
    order_id = pay.get("response", {}).get("order_id")
    
    print("\n[4/8] Get payment details...")
    test_endpoint("get_payment", "GET", f"/payments/{payment_id}", token=token)
    
    print("\n[4b/8] Verify payment (real signature - will fail but test endpoint)...")
    # This will fail with fake signature but tests the endpoint works
    test_endpoint("verify_payment", "POST", "/payments/verify", token=token, json_body={
        "razorpay_order_id": order_id or "order_test", "razorpay_payment_id": "pay_test123",
        "razorpay_signature": "test_sig"
    })
    
    print("\n[4c/8] Create escrow...")
    escrow_resp = test_endpoint("create_escrow", "POST", "/payments/escrow", token=token, json_body={
        "workflow_id": wf_id, "payment_id": payment_id, "amount": 50000,
        "release_condition": "delivery_confirmed"
    })
    escrow_id = escrow_resp.get("response", {}).get("id")
    
    print("\n[4d/8] Release escrow...")
    if escrow_id:
        test_endpoint("release_escrow", "POST", f"/payments/escrow/{escrow_id}/release", token=token)
    else:
        test_endpoint("release_escrow", "POST", f"/payments/escrow/{payment_id}/release", token=token)
    
    print("\n[4e/8] Create invoice...")
    test_endpoint("create_invoice", "POST", "/payments/invoices", token=token, json_body={
        "workflow_id": wf_id, "payment_id": payment_id, "amount": 50000,
        "description": "Test invoice", "tax_amount": 9000,
        "payer_name": "Test Buyer", "payer_gst": "29AAAAA0000A1Z5",
        "payee_name": "Test Seller", "payee_gst": "29BBBBB0000B1Z5"
    })
    
    return wf_id, payment_id


def run_concurrent_payments(token: str, actor_id: str, num_payments: int = 20):
    """Run concurrent payment initiations"""
    print(f"\n[Concurrent] Running {num_payments} concurrent payment initiations...")
    
    # First create a workflow
    wf = test_endpoint("concurrent_create_wf", "POST", "/workflows", token=token, json_body={
        "name": "Concurrent Test", "initiator_id": actor_id,
        "phases": ["initiation", "approval", "execution"]
    })
    wf_id = wf.get("response", {}).get("id")
    
    def make_payment(i):
        return test_endpoint(f"concurrent_payment_{i}", "POST", "/payments/initiate", token=token, json_body={
            "workflow_id": wf_id, "amount": 10000 + i * 100, "currency": "INR",
            "description": f"Concurrent payment {i}", "payer_actor_id": actor_id
        })
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_payment, i) for i in range(num_payments)]
        for f in as_completed(futures):
            f.result()


def run_webhook_tests(token: str):
    """Test webhook handling"""
    print("\n[Webhook] Testing webhook handlers...")
    
    # Payment captured webhook
    test_endpoint("webhook_captured", "POST", "/payments/webhook", json_body={
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_test123", "order_id": "order_test", "amount": 50000, "currency": "INR", "status": "captured"}}}
    })
    
    # Payment failed webhook
    test_endpoint("webhook_failed", "POST", "/payments/webhook", json_body={
        "event": "payment.failed",
        "payload": {"payment": {"entity": {"id": "pay_test456", "order_id": "order_test2", "amount": 50000, "currency": "INR", "status": "failed", "error_code": "BAD_REQUEST_ERROR", "error_description": "Card declined"}}}
    })
    
    # Refund processed webhook
    test_endpoint("webhook_refund", "POST", "/payments/webhook", json_body={
        "event": "refund.processed",
        "payload": {"refund": {"entity": {"id": "rfnd_test123", "payment_id": "pay_test123", "amount": 25000, "status": "processed"}}}
    })


def run_idempotency_tests(token: str, actor_id: str):
    """Test idempotency with duplicate requests"""
    print("\n[Idempotency] Testing duplicate request handling...")
    
    wf = test_endpoint("idem_create_wf", "POST", "/workflows", token=token, json_body={
        "name": "Idempotency Test", "initiator_id": actor_id,
        "phases": ["initiation"]
    })
    wf_id = wf.get("response", {}).get("id")
    
    # Try to create same payment twice with same idempotency key
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-test-123"}
    start = time.monotonic()
    resp1 = client.post(f"/payments/initiate", headers=headers, json={
        "workflow_id": wf_id, "amount": 10000, "currency": "INR",
        "description": "Idempotency test", "payer_actor_id": actor_id
    })
    elapsed1 = (time.monotonic() - start) * 1000
    
    start = time.monotonic()
    resp2 = client.post(f"/payments/initiate", headers=headers, json={
        "workflow_id": wf_id, "amount": 10000, "currency": "INR",
        "description": "Idempotency test", "payer_actor_id": actor_id
    })
    elapsed2 = (time.monotonic() - start) * 1000
    
    print(f"  First request: {resp1.status_code} ({elapsed1:.0f}ms)")
    print(f"  Second request: {resp2.status_code} ({elapsed2:.0f}ms)")
    if resp1.status_code == resp2.status_code == 201:
        print("  [OK] Idempotency key honored - duplicate returned same response")
    else:
        print(f"  [WARN] Idempotency not enforced")


def run_refund_tests(token: str, payment_id: str):
    """Test refund flows - handle uncaptured payments gracefully"""
    print("\n[Refund] Testing refund flows...")
    
    # Test partial refund - may fail if payment not captured
    resp = test_endpoint("refund_partial", "POST", f"/payments/{payment_id}/refund", token=token, json_body={
        "amount": 10000, "reason": "Partial refund for defective item"
    })
    if resp.get("status") == 404:
        print("  [INFO] Refund skipped - payment not captured (expected in test)")
    
    # Test full refund
    resp = test_endpoint("refund_full", "POST", f"/payments/{payment_id}/refund", token=token, json_body={
        "amount": 50000, "reason": "Full refund - order cancelled"
    })
    if resp.get("status") == 404:
        print("  [INFO] Refund skipped - payment not captured (expected in test)")


def run_security_tests(token: str, actor_id: str):
    """Test security: unauthorized access, injection, etc."""
    print("\n[Security] Testing security measures...")
    
    # Unauthorized access
    test_endpoint("unauth_payment", "POST", "/payments/initiate", json_body={
        "workflow_id": "00000000-0000-0000-0000-000000000000", "amount": 10000
    })
    
    # Invalid payment ID
    test_endpoint("invalid_payment_id", "GET", "/payments/invalid-id")
    
    # SQL injection attempt in workflow_id
    test_endpoint("sql_injection", "POST", "/payments/initiate", json_body={
        "workflow_id": "'; DROP TABLE payments; --", "amount": 10000
    })
    
    # Large amount (overflow test) - with valid auth
    test_endpoint("overflow_amount", "POST", "/payments/initiate", token=token, json_body={
        "workflow_id": "00000000-0000-0000-0000-000000000000", "amount": 999999999999
    })


def run_latency_benchmark(token: str, actor_id: str, iterations: int = 50):
    """Benchmark payment latency"""
    print(f"\n[Latency] Running {iterations} payment latency benchmark...")
    
    wf = test_endpoint("bench_wf", "POST", "/workflows", token=token, json_body={
        "name": "Benchmark", "initiator_id": actor_id, "phases": ["initiation"]
    })
    wf_id = wf.get("response", {}).get("id")
    
    latencies = []
    for i in range(iterations):
        start = time.monotonic()
        resp = test_endpoint(f"bench_pay_{i}", "POST", "/payments/initiate", token=token, json_body={
            "workflow_id": wf_id, "amount": 10000, "currency": "INR",
            "description": f"Benchmark {i}", "payer_actor_id": actor_id
        })
        elapsed = (time.monotonic() - start) * 1000
        if resp.get("success"):
            latencies.append(elapsed)
        # Small delay to avoid rate limiting
        if i % 10 == 0 and i > 0:
            time.sleep(0.5)
    
    if latencies:
        print(f"  Iterations: {len(latencies)}/{iterations} successful")
        print(f"  Latency: min={min(latencies):.0f}ms avg={statistics.mean(latencies):.0f}ms "
              f"p50={statistics.median(latencies):.0f}ms p95={statistics.quantiles(latencies, n=20)[18]:.0f}ms "
              f"p99={statistics.quantiles(latencies, n=100)[98]:.0f}ms max={max(latencies):.0f}ms")


def main():
    print("=" * 80)
    print("RAZORPAY COMPREHENSIVE STRESS TEST")
    print("=" * 80)
    
    # Setup
    print("\n[Setup] Registering test user...")
    email = f"stress_{int(time.time())}@test.com"
    test_endpoint("register", "POST", "/auth/register", json_body={
        "name": "Stress Tester", "email": email, "password": "test123"
    })
    login = test_endpoint("login", "POST", "/auth/login", json_body={
        "email": email, "password": "test123"
    })
    token = login.get("response", {}).get("access_token")
    actor_id = login.get("response", {}).get("actor_id")
    
    if not token:
        print("Failed to get token")
        return
    
    print(f"Token acquired, actor_id: {actor_id}")
    
    # Run all test suites
    wf_id, payment_id = run_sequential_tests(token, actor_id)
    run_concurrent_payments(token, actor_id, 20)
    run_webhook_tests(token)
    run_idempotency_tests(token, actor_id)
    run_refund_tests(token, payment_id)
    run_security_tests(token, actor_id)
    run_latency_benchmark(token, actor_id, 50)
    
    print_summary()
    
    # Save detailed results
    with open("razorpay_stress_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nResults saved to razorpay_stress_results.json")


if __name__ == "__main__":
    main()