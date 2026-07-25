#!/usr/bin/env python3
"""
Real-world Sarvam AI integration test using FastAPI TestClient (in-process).
Validates actual Sarvam API calls, response formats, input/output validation.
"""

import os
# MUST set before importing app to use SQLite for testing
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_sangam.db"
os.environ["JWT_SECRET"] = "test-secret-for-stress-test"
os.environ["SARVAM_API_KEY"] = "sk_gv50556a_Xj5lc0qeDpsi7QkHbSlNCGFC"
os.environ["RAZORPAY_KEY_ID"] = "rzp_live_TD0msDGLQvTmsJ"
os.environ["RAZORPAY_KEY_SECRET"] = "n3RVOZSoujb8EdlJVxmNhdmC"

import asyncio
import base64
import json
import time
import wave
import io
from typing import Dict, Any

from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import get_session
from sqlalchemy.ext.asyncio import create_async_engine

# Create tables before running tests
engine = create_async_engine("sqlite+aiosqlite:///./test_sangam.db", echo=False)
import asyncio
asyncio.run(asyncio.sleep(0))  # ensure event loop
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


def create_test_audio() -> bytes:
    """Create a minimal WAV file (1 second silence at 16kHz mono)."""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b'\x00\x00' * 16000)
    return buf.getvalue()


def create_test_image() -> bytes:
    """Create a minimal 10x10 white PNG."""
    return base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAFUlEQVR42mP8/5+hnoEIwDiqkL4KAcT9G0AB4ddAeYD+AVaAfgEfgPbwAAAABJRU5ErkJggg==")


def main():
    print("=" * 70)
    print("SARVAM AI REAL INTEGRATION TEST (TestClient)")
    print("=" * 70)

    # 1. Health check
    print("\n[1/16] Health check...")
    test_endpoint("health", "GET", "/health")

    # 2. Register user
    print("\n[2/16] Register user...")
    reg = test_endpoint("register", "POST", "/auth/register", json_body={
        "name": "Sarvam Tester", "email": "sarvam_test@sangam.ai", "password": "test123"
    })

    # 3. Login
    print("\n[3/16] Login...")
    login = test_endpoint("login", "POST", "/auth/login", json_body={
        "email": "sarvam_test@sangam.ai", "password": "test123"
    })
    token = login.get("response", {}).get("access_token") if login.get("success") else None
    if not token:
        print("\n[FAIL] No token, aborting")
        return
    print(f"     Got token: {token[:20]}...")

    # 4. AI Languages
    print("\n[4/16] AI Languages...")
    test_endpoint("ai_languages", "GET", "/ai/languages", token=token)

    # 5. AI Voices
    print("\n[5/16] AI Voices...")
    test_endpoint("ai_voices", "GET", "/ai/voices", token=token)

    # 6. Translate
    print("\n[6/16] Translate (EN -> HI)...")
    test_endpoint("ai_translate", "POST", "/ai/translate", token=token,
        json_body={"text": "Hello, how are you?", "target_language_code": "hi-IN"})

    # 7. Identify Language
    print("\n[7/16] Identify Language (Hindi)...")
    test_endpoint("ai_identify_language", "POST", "/ai/identify-language", token=token,
        json_body={"text": "नमस्ते, आप कैसे हैं?"})

    # 8. Transliterate
    print("\n[8/16] Transliterate...")
    test_endpoint("ai_transliterate", "POST", "/ai/transliterate", token=token,
        json_body={"text": "नमस्ते", "source_language_code": "hi-IN", "target_language_code": "en-IN"})

    # 9. LLM - Short
    print("\n[9/16] LLM (short)...")
    test_endpoint("ai_llm_short", "POST", "/ai/llm", token=token,
        json_body={"messages": [{"role": "user", "content": "Say hello in 3 words"}], "max_tokens": 20})

    # 10. LLM - Longer (tests retry)
    print("\n[10/16] LLM (longer, tests retry)...")
    test_endpoint("ai_llm_long", "POST", "/ai/llm", token=token,
        json_body={"messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write a 2-sentence summary of workflow automation benefits."}
        ], "max_tokens": 100})

    # 11. Text Analytics - SKIPPED (endpoint not available in current API version)
    print("\n[11/16] Text Analytics - SKIPPED (endpoint not available)")
    results["ai_text_analytics"] = {"status": "skipped", "latency_ms": 0, "success": False}

    # 12. Semantic Boundaries
    print("\n[12/16] Semantic Boundaries...")
    test_endpoint("ai_detect_boundaries", "POST", "/ai/detect-boundaries", token=token,
        json_body={"text": "First sentence. Second sentence! Third sentence?", "language_code": "en-IN"})

    # 13. Speech-to-Text
    print("\n[13/16] Speech-to-Text (silence audio)...")
    audio_bytes = create_test_audio()
    files = {"file": ("test.wav", audio_bytes, "audio/wav")}
    test_endpoint("ai_stt", "POST", "/ai/speech-to-text", token=token,
        json_body={"language_code": "hi-IN"}, files=files)

# 14. Text-to-Speech (en-IN)
    print("\n[14/16] Text-to-Speech (en-IN)...")
    test_endpoint("ai_tts_en", "POST", "/ai/text-to-speech", token=token,
        json_body={"text": "Hello, this is a test.", "target_language_code": "en-IN", "speaker": "anushka"})

    # 14b. Text-to-Speech (hi-IN)
    print("\n[14b/16] Text-to-Speech (hi-IN)...")
    test_endpoint("ai_tts_hi", "POST", "/ai/text-to-speech", token=token,
        json_body={"text": "नमस्ते, यह एक परीक्षण है।", "target_language_code": "hi-IN", "speaker": "anushka"})

    # 15. Vision OCR (async)
    print("\n[15/16] Vision OCR (async)...")
    img_bytes = create_test_image()
    files = {"file": ("test.png", img_bytes, "image/png")}
    vision = test_endpoint("ai_vision_extract", "POST", "/ai/vision/extract", token=token,
        json_body={"task": "extract_text"}, files=files)

# 16. Poll vision status - use the actual job_id returned
    print("\n[16/16] Polling vision job...")
    if vision.get("success"):
        job_id = vision.get("response", {}).get("job_id")
        if job_id:
            print(f"     Polling vision job {job_id[:8]}...")
            for i in range(5):
                time.sleep(2)
                status = test_endpoint(f"ai_vision_status_{i}", "GET", f"/ai/vision/status/{job_id}", token=token)
                if status.get("success"):
                    st = status["response"].get("status")
                    print(f"     Job status: {st}")
                    if st in ("completed", "failed"):
                        break
        else:
            print("     No job_id returned, skipping poll")
    else:
        print("     Vision job failed, skipping poll")

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
    with open("sarvam_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nDetailed results saved to sarvam_test_results.json")


if __name__ == "__main__":
    main()