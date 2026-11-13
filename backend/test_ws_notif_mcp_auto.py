#!/usr/bin/env python3
"""
Test WebSocket, Notifications, MCP, and Autonomous features
"""

import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_sangam.db"
os.environ["JWT_SECRET"] = "test-secret-for-stress-test"
os.environ.setdefault("SARVAM_API_KEY", "")  # set in your shell or backend/.env; never commit keys
os.environ.setdefault("RAZORPAY_KEY_ID", "")  # set in your shell or backend/.env; never commit keys
os.environ.setdefault("RAZORPAY_KEY_SECRET", "")  # set in your shell or backend/.env; never commit keys
os.environ["EMAIL_API_KEY"] = "test_email_key"
os.environ["SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/test"

import json
import time
import uuid
from typing import Dict, Any

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

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
    results[name] = result
    status = "[OK]" if result.get("success") else "[FAIL]"
    print(f"  {status} {name}: {result.get('status')} ({result.get('latency_ms', 0):.0f}ms)")
    if not result.get("success"):
        print(f"     Error: {result.get('error') or result.get('response')}")
    return result


def test_websocket(token: str):
    """Test WebSocket connection and message flow"""
    print("\n--- WEBSOCKET TESTS ---")
    
    # Test /ws endpoint
    print("\n[WS1] Connect to /ws...")
    try:
        with client.websocket_connect(f"/ws?token={token}") as ws:
            results["ws_connect"] = {"status": "connected", "latency_ms": 0, "success": True}
            print("  [OK] ws_connect: connected")
            
            # Send ping
            ws.send_text(json.dumps({"type": "ping"}))
            msg = ws.receive_text()
            print(f"     Received: {msg}")
            
            # Subscribe to workflow
            ws.send_text(json.dumps({"type": "subscribe_workflow", "workflow_id": "test-wf"}))
            msg = ws.receive_text()
            print(f"     Subscribe response: {msg}")
            
            # Send voice chunk
            ws.send_text(json.dumps({"type": "voice_chunk", "audio": "base64data"}))
            msg = ws.receive_text()
            print(f"     Voice chunk response: {msg}")
            
    except Exception as e:
        results["ws_connect"] = {"status": "error", "success": False, "error": str(e)}
        print(f"  [FAIL] ws_connect: {e}")

    # Test /ws/voice endpoint
    print("\n[WS2] Connect to /ws/voice...")
    try:
        with client.websocket_connect(f"/ws/voice?token={token}") as ws:
            results["ws_voice_connect"] = {"status": "connected", "latency_ms": 0, "success": True}
            print("  [OK] ws_voice_connect: connected")
            
            ws.send_text(json.dumps({"type": "voice_chunk", "audio": "base64data", "language": "hi-IN"}))
            msg = ws.receive_text()
            print(f"     Voice response: {msg}")
            
    except Exception as e:
        results["ws_voice_connect"] = {"status": "error", "success": False, "error": str(e)}
        print(f"  [FAIL] ws_voice_connect: {e}")


def test_notifications(token: str, actor_id: str):
    """Test push notifications, email, Slack"""
    print("\n--- NOTIFICATION TESTS ---")
    
    # Register FCM token
    print("\n[NOTIF1] Register FCM token...")
    test_endpoint("fcm_register", "POST", "/notifications/fcm/register", token=token, json_body={
        "token": "fake_fcm_token_123", "device_type": "android"
    })
    
    # List devices
    print("\n[NOTIF2] List devices...")
    test_endpoint("list_devices", "GET", "/notifications/devices", token=token)
    
    # Send test notification
    print("\n[NOTIF3] Send test notification...")
    test_endpoint("test_notification", "POST", "/notifications/test", token=token, json_body={
        "actor_id": actor_id,
        "title": "Test", "body": "Hello from Sangam", "data": {"workflow_id": "test"}
    })


def test_mcp(token: str):
    """Test MCP server execution"""
    print("\n--- MCP TESTS ---")
    
    # List MCP servers
    print("\n[MCP1] List MCP servers...")
    test_endpoint("mcp_list", "GET", "/mcp/servers", token=token)
    
    # Get Slack manifest
    print("\n[MCP2] Get Slack manifest...")
    test_endpoint("mcp_slack_manifest", "GET", "/mcp/servers/slack/manifest", token=token)
    
    # Execute Slack action
    print("\n[MCP3] Execute Slack action...")
    test_endpoint("mcp_execute_slack", "POST", "/mcp/execute", token=token, json_body={
        "server": "slack",
        "tool": "send_message",
        "params": {"channel": "general", "text": "Test from Sangam MCP"}
    })


def test_autonomous(token: str, wf_id: str):
    """Test autonomous endpoints"""
    print("\n--- AUTONOMOUS TESTS ---")
    
    # Auto-retry workflow
    print("\n[AUTO1] Auto-retry workflow...")
    test_endpoint("auto_retry", "POST", f"/autonomous/retry", token=token, json_body={
        "workflow_id": wf_id
    })
    
    # Auto-execute
    print("\n[AUTO2] Auto-execute workflow...")
    test_endpoint("auto_execute", "POST", f"/autonomous/execute/{wf_id}", token=token)
    
    # Auto-approve (need an approval ID - skip for now)
    print("\n[AUTO3] Auto-approve...")
    test_endpoint("auto_approve", "POST", "/autonomous/auto-approve/some_approval_id", token=token)


def main():
    print("=" * 70)
    print("WEBSOCKET / NOTIFICATIONS / MCP / AUTONOMOUS TESTS")
    print("=" * 70)

    # Setup: register, login, create workflow
    email = f"ws_test_{int(time.time())}@sangam.ai"
    test_endpoint("register", "POST", "/auth/register", json_body={
        "name": "WS Tester", "email": email, "password": "test123"
    })
    login = test_endpoint("login", "POST", "/auth/login", json_body={
        "email": email, "password": "test123"
    })
    token = login.get("response", {}).get("access_token") if login.get("success") else None
    
    if not token:
        print("[FAIL] No token")
        return
    print(f"Token: {token[:20]}...")

    # Create workflow for autonomous tests
    wf = test_endpoint("create_workflow", "POST", "/workflows", token=token, json_body={
        "name": "Test Workflow", "initiator_id": login["response"]["actor_id"],
        "phases": ["initiation", "approval", "execution"]
    })
    wf_id = wf.get("response", {}).get("id") if wf.get("success") else "test-wf"
    print(f"Workflow ID: {wf_id}")

    # Run test suites
    actor_id = login["response"]["actor_id"]
    test_websocket(token)
    test_notifications(token, actor_id)
    test_mcp(token)
    test_autonomous(token, wf_id)

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

    with open("ws_notif_mcp_auto_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nResults saved to ws_notif_mcp_auto_test_results.json")


if __name__ == "__main__":
    main()