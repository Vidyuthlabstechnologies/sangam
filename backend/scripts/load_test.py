"""Load test for the Sangam backend with real Firebase-shaped auth.

Runs a mix of the requests the Android app makes, at a fixed number of
concurrent virtual users, and prints throughput, latency percentiles and
errors per endpoint.

It never calls Sarvam or Samvaad: run the server with USE_FIXTURES=true (or
without provider keys) so AI and voice endpoints return canned replies. Do not
point this at production with live keys.

Two ways to authenticate:

1. Local server (default). This script writes a throwaway RSA key and JWKS,
   serves the JWKS on --jwks-port, and mints Firebase-style ID tokens for
   --users distinct accounts. Start the server with:

       FIREBASE_PROJECT_ID=loadtest \
       FIREBASE_JWKS_URL=http://127.0.0.1:9911/jwks.json \
       USE_FIXTURES=true RATE_LIMIT_ENABLED=false \
       uvicorn app.main:app --port 8000

2. A deployed staging server: pass --token with a real Firebase ID token.
   Every virtual user then shares that one account.

Examples:

    python -m scripts.load_test --users 200 --duration 60
    python -m scripts.load_test --base https://staging.example --token "$TOKEN" --users 50
    python -m scripts.load_test --ws 100        # also hold 100 live voice WebSockets
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import random
import statistics
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import httpx

PROJECT_ID = "loadtest"
ISSUER = f"https://securetoken.google.com/{PROJECT_ID}"

# (weight, name, method, path, body). Weights follow how often the app makes each call.
MIX: list[tuple[int, str, str, str, dict | None]] = [
    (10, "auth_me", "GET", "/auth/me", None),
    (8, "wallet_me", "GET", "/onboarding/wallet/me", None),
    (8, "list_workflows", "GET", "/workflows", None),
    (4, "plans", "GET", "/onboarding/plans", None),
    (4, "categories", "GET", "/onboarding/categories", None),
    (4, "voice_calls", "GET", "/voice-agents/calls", None),
    (3, "create_workflow", "POST", "/workflows", {"name": "Load test workflow", "phases": ["initiation", "execution"]}),
    (2, "health", "GET", "/health", None),
]


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_keys(key_file: str) -> tuple[Any, dict]:
    """Load the signing key from key_file, or create it there.

    Reusing one key across runs matters: the server caches the JWKS, so a new
    key per run would be rejected until that cache expires.
    """
    import os

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    if os.path.exists(key_file):
        with open(key_file, "rb") as fh:
            key = serialization.load_pem_private_key(fh.read(), password=None)
    else:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with open(key_file, "wb") as fh:
            fh.write(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ))
    numbers = key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": "loadtest-key",
        "use": "sig",
        "alg": "RS256",
        "n": _b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
        "e": _b64(numbers.e.to_bytes(3, "big")),
    }
    return key, {"keys": [jwk]}


def mint_token(key: Any, uid: str) -> str:
    import jwt

    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": PROJECT_ID,
        "sub": uid,
        "user_id": uid,
        "auth_time": now - 10,
        "iat": now - 10,
        "exp": now + 3600,
        "email": f"{uid}@loadtest.invalid",
        "email_verified": True,
        "name": f"Load {uid}",
        "firebase": {"sign_in_provider": "google.com"},
    }
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "loadtest-key"})


def serve_jwks(jwks: dict, port: int) -> None:
    body = json.dumps(jwks).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: Any) -> None:
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


class Stats:
    def __init__(self) -> None:
        self.latency: dict[str, list[float]] = defaultdict(list)
        self.status: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.exceptions: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def report(self, elapsed: float) -> dict:
        rows = {}
        total = 0
        total_ok = 0
        for name in sorted(set(self.latency) | set(self.exceptions)):
            lat = sorted(self.latency.get(name, []))
            n = len(lat) + sum(self.exceptions[name].values())
            ok = sum(c for s, c in self.status[name].items() if s < 400)
            total += n
            total_ok += ok

            def pct(p: float) -> float:
                return round(lat[min(len(lat) - 1, int(len(lat) * p))] * 1000, 1) if lat else 0.0

            rows[name] = {
                "requests": n,
                "ok": ok,
                "status": dict(self.status[name]),
                "exceptions": dict(self.exceptions[name]),
                "p50_ms": pct(0.50),
                "p95_ms": pct(0.95),
                "p99_ms": pct(0.99),
                "mean_ms": round(statistics.mean(lat) * 1000, 1) if lat else 0.0,
            }
        return {
            "elapsed_s": round(elapsed, 1),
            "requests": total,
            "ok": total_ok,
            "rps": round(total / elapsed, 1) if elapsed else 0,
            "error_rate": round(1 - total_ok / total, 4) if total else 0,
            "endpoints": rows,
        }


async def user_loop(client: httpx.AsyncClient, token: str, stats: Stats, stop_at: float, think: float) -> None:
    weights = [m[0] for m in MIX]
    headers = {"Authorization": f"Bearer {token}"}
    while time.monotonic() < stop_at:
        _, name, method, path, body = random.choices(MIX, weights=weights)[0]
        started = time.monotonic()
        try:
            resp = await client.request(method, path, json=body, headers=headers)
            stats.latency[name].append(time.monotonic() - started)
            stats.status[name][resp.status_code] += 1
        except Exception as exc:  # timeouts, refused connections
            stats.exceptions[name][type(exc).__name__] += 1
        if think:
            await asyncio.sleep(random.uniform(0, think * 2))


async def hold_voice_socket(base: str, token: str, stats: Stats, stop_at: float) -> None:
    """Open the live voice proxy and stream silence until the test ends."""
    import websockets

    url = base.replace("http", "ws", 1) + "/voice-agents/ws/loadtest-app?token=" + token
    started = time.monotonic()
    try:
        async with websockets.connect(url, open_timeout=30) as ws:
            stats.latency["ws_connect"].append(time.monotonic() - started)
            stats.status["ws_connect"][101] += 1
            silence = b"\x00" * 640  # 20 ms of 16 kHz 16-bit mono
            while time.monotonic() < stop_at:
                await ws.send(silence)
                try:
                    await asyncio.wait_for(ws.recv(), timeout=0.02)
                except TimeoutError:
                    pass
    except Exception as exc:
        code = getattr(getattr(exc, "rcvd", None), "code", None)
        key = f"{type(exc).__name__}{'/' + str(code) if code else ''}"
        stats.exceptions["ws_connect"][key] += 1


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--users", type=int, default=100, help="concurrent virtual users")
    parser.add_argument("--accounts", type=int, default=0, help="distinct accounts (default: one per user)")
    parser.add_argument("--duration", type=float, default=30.0, help="seconds")
    parser.add_argument("--think", type=float, default=0.0, help="mean seconds between a user's requests")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--token", default="", help="real Firebase ID token for a deployed server")
    parser.add_argument("--jwks-port", type=int, default=9911)
    parser.add_argument("--key-file", default=".loadtest_key.pem", help="throwaway signing key, reused across runs")
    parser.add_argument("--ws", type=int, default=0, help="live voice WebSockets to hold open")
    parser.add_argument("--json", default="", help="write the report to this file")
    args = parser.parse_args()

    if args.token:
        tokens = [args.token]
    else:
        key, jwks = make_keys(args.key_file)
        serve_jwks(jwks, args.jwks_port)
        accounts = args.accounts or args.users
        tokens = [mint_token(key, f"lt{i:06d}") for i in range(accounts)]

    limits = httpx.Limits(max_connections=args.users + 10, max_keepalive_connections=args.users + 10)
    async with httpx.AsyncClient(base_url=args.base, timeout=args.timeout, limits=limits) as client:
        # Warm up: first request per account creates its actor row.
        warm = Stats()
        sem = asyncio.Semaphore(50)

        async def warmup(tok: str) -> None:
            async with sem:
                try:
                    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"})
                    warm.status["auth_me"][r.status_code] += 1
                except Exception as exc:
                    warm.exceptions["auth_me"][type(exc).__name__] += 1

        t0 = time.monotonic()
        await asyncio.gather(*(warmup(t) for t in tokens))
        print(f"warm-up: {len(tokens)} accounts in {time.monotonic() - t0:.1f}s -> "
              f"{dict(warm.status['auth_me'])} {dict(warm.exceptions['auth_me'])}")

        stats = Stats()
        start = time.monotonic()
        stop_at = start + args.duration
        tasks = [
            user_loop(client, tokens[i % len(tokens)], stats, stop_at, args.think) for i in range(args.users)
        ]
        tasks += [hold_voice_socket(args.base, tokens[i % len(tokens)], stats, stop_at) for i in range(args.ws)]
        await asyncio.gather(*tasks)
        report = stats.report(time.monotonic() - start)
        report["users"] = args.users
        report["ws"] = args.ws

    print(json.dumps({k: v for k, v in report.items() if k != "endpoints"}))
    print(f"{'endpoint':18} {'reqs':>7} {'ok':>7} {'p50':>8} {'p95':>8} {'p99':>8}  status / errors")
    for name, row in report["endpoints"].items():
        print(f"{name:18} {row['requests']:>7} {row['ok']:>7} {row['p50_ms']:>8} {row['p95_ms']:>8} "
              f"{row['p99_ms']:>8}  {row['status']} {row['exceptions'] or ''}")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(report, fh, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
