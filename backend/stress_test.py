"""
Sangam Stress Test — standalone, no locust required.
Hammers all major endpoints concurrently and reports p50/p95/p99 latencies.
"""

import asyncio
import json
import time
import statistics
import sys
from typing import Dict, List
from urllib.parse import urljoin

import httpx

BASE = "http://localhost:8000"
CONCURRENCY = 20
REQUESTS_PER_USER = 30
USERS = 10

results: Dict[str, List[float]] = {}
errors: Dict[str, int] = {}


async def worker(
    client: httpx.AsyncClient,
    name: str,
    endpoint: str,
    method: str = "GET",
    json_body: dict = None,
    token: str = None,
    timeout: float = 30,
):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    for _ in range(REQUESTS_PER_USER):
        start = time.monotonic()
        try:
            if method == "GET":
                resp = await client.get(
                    urljoin(BASE, endpoint), headers=headers, timeout=timeout
                )
            else:
                resp = await client.post(
                    urljoin(BASE, endpoint),
                    headers=headers,
                    json=json_body or {},
                    timeout=timeout,
                )
            elapsed = (time.monotonic() - start) * 1000
            results.setdefault(name, []).append(elapsed)
            if resp.status_code >= 500:
                errors[name] = errors.get(name, 0) + 1
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            results.setdefault(name, []).append(elapsed)
            errors[name] = errors.get(name, 0) + 1


async def register_users(client: httpx.AsyncClient, count: int) -> List[str]:
    tokens = []
    for i in range(count):
        try:
            resp = await client.post(
                urljoin(BASE, "/auth/register"),
                json={
                    "name": f"stress_user_{i}",
                    "email": f"stress{i}@sangam.ai",
                    "password": "test123",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                tokens.append(resp.json()["access_token"])
        except Exception:
            try:
                resp = await client.post(
                    urljoin(BASE, "/auth/login"),
                    json={"email": f"stress{i}@sangam.ai", "password": "test123"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    tokens.append(resp.json()["access_token"])
            except Exception:
                pass
    return tokens


def print_report():
    print("\n" + "=" * 70)
    print(f"{'ENDPOINT':<35} {'COUNT':>6} {'p50(ms)':>8} {'p95(ms)':>8} {'p99(ms)':>8} {'ERRORS':>7}")
    print("=" * 70)
    for name in sorted(results.keys()):
        vals = sorted(results[name])
        if not vals:
            continue
        p50 = statistics.median(vals)
        p95 = vals[int(len(vals) * 0.95)]
        p99 = vals[int(len(vals) * 0.99)]
        errs = errors.get(name, 0)
        print(
            f"{name:<35} {len(vals):>6} {p50:>8.1f} {p95:>8.1f} {p99:>8.1f} {errs:>7}"
        )


async def main():
    print(f"Stress Testing Sangam at {BASE}")
    print(f"Concurrency: {CONCURRENCY}, Users: {USERS}, Requests/user: {REQUESTS_PER_USER}")
    print(f"Total requests: ~{CONCURRENCY * REQUESTS_PER_USER * 8}")
    print()

    async with httpx.AsyncClient() as client:
        health = await client.get(urljoin(BASE, "/health"))
        print(f"Health: {health.json()}")

        print("Registering users...")
        tokens = await register_users(client, USERS)
        print(f"Got {len(tokens)} tokens")

        if not tokens:
            print("ERROR: No tokens. Is the backend running?")
            return

        token = tokens[0]

        # Create a workflow for detail endpoint
        wf_resp = await client.post(
            urljoin(BASE, "/workflows"),
            json={"name": "Stress Test Workflow", "phases": ["INITIATION", "APPROVAL", "SETTLEMENT"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        wf_id = ""
        if wf_resp.status_code == 200:
            wf_id = wf_resp.json()["id"]
            print(f"Created workflow: {wf_id[:8]}...")

        endpoints = [
            ("health", "GET", "/health", None, False, 5),
            ("auth_analytics", "GET", "/analytics/summary", None, False, 5),
            ("list_workflows", "GET", "/workflows", None, True, 10),
            ("list_actors", "GET", "/actors", None, True, 10),
            ("ai_languages", "GET", "/ai/languages", None, True, 10),
            ("ai_translate", "POST", "/ai/translate",
             {"text": "Hello world", "target_language_code": "hi-IN"}, True, 30),
            ("ai_identify_language", "POST", "/ai/identify-language",
             {"text": "नमस्ते, आप कैसे हैं?"}, True, 15),
            ("ai_llm_short", "POST", "/ai/llm",
             {"messages": [{"role": "user", "content": "Say hello in 3 words"}], "max_tokens": 20},
             True, 30),
        ]

        sem = asyncio.Semaphore(CONCURRENCY)

        async def limited_worker(*args, **kwargs):
            async with sem:
                await worker(*args, **kwargs)

        tasks = []
        async with httpx.AsyncClient() as client:
            for name, method, path, body, needs_auth, timeout in endpoints:
                t = tokens[0] if needs_auth else None
                for _ in range(REQUESTS_PER_USER * USERS // len(endpoints)):
                    tasks.append(
                        limited_worker(
                            client, name, path, method, body, t, timeout
                        )
                    )

            print(f"Executing {len(tasks)} requests...")
            start_all = time.monotonic()
            await asyncio.gather(*tasks, return_exceptions=True)
            total_time = time.monotonic() - start_all

        print(f"\nCompleted in {total_time:.1f}s")
        print(f"Throughput: {len(tasks) / total_time:.0f} req/s")
        print_report()

        # Try AI LLM with retries for longer test
        if token:
            print("\n--- AI LLM heavy test (5 requests, with retry) ---")
            ai_times = []
            for i in range(5):
                start = time.monotonic()
                try:
                    async with httpx.AsyncClient() as c:
                        resp = await c.post(
                            urljoin(BASE, "/ai/llm"),
                            json={
                                "messages": [{"role": "user", "content": "Write a 2-sentence summary of workflow automation."}],
                                "max_tokens": 100,
                            },
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=60,
                        )
                    elapsed = (time.monotonic() - start) * 1000
                    ai_times.append(elapsed)
                    status = "OK" if resp.status_code == 200 else f"ERR{resp.status_code}"
                    print(f"  LLM #{i+1}: {elapsed:.0f}ms {status}")
                except Exception as e:
                    elapsed = (time.monotonic() - start) * 1000
                    ai_times.append(elapsed)
                    print(f"  LLM #{i+1}: {elapsed:.0f}ms FAILED ({e})")

            if ai_times:
                print(f"  LLM avg: {statistics.mean(ai_times):.0f}ms")

        # Cleanup
        if wf_id:
            await client.delete(
                urljoin(BASE, f"/workflows/{wf_id}"),
                headers={"Authorization": f"Bearer {token}"},
            )

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
