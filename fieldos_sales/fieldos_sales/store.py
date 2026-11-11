"""SQLite storage. One local file (data/sales.db, gitignored).

Holds prospect contact details, research, drafts, approvals, opt-outs, DND
scrub results and a log of every call and message. It never leaves the
machine it runs on.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY,
    firm TEXT NOT NULL,
    segment TEXT, size TEXT, priority TEXT, suggested_plan TEXT,
    website TEXT, phones TEXT NOT NULL DEFAULT '[]', emails TEXT,
    contact_page TEXT, source TEXT, owner_notes TEXT,
    contact_name TEXT, language TEXT NOT NULL DEFAULT 'en',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
    prospect_id INTEGER PRIMARY KEY REFERENCES prospects(id),
    profile TEXT NOT NULL, confidence TEXT, sources TEXT,
    researched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    prospect_id INTEGER NOT NULL REFERENCES prospects(id),
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (prospect_id, kind)
);
CREATE TABLE IF NOT EXISTS approvals (
    prospect_id INTEGER NOT NULL REFERENCES prospects(id),
    channel TEXT NOT NULL CHECK (channel IN ('call', 'whatsapp')),
    approved_at TEXT NOT NULL,
    PRIMARY KEY (prospect_id, channel)
);
CREATE TABLE IF NOT EXISTS suppressions (
    phone TEXT PRIMARY KEY,
    reason TEXT NOT NULL, source TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dnd (
    phone TEXT PRIMARY KEY,
    registered INTEGER NOT NULL,
    checked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS touches (
    id INTEGER PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    channel TEXT NOT NULL, direction TEXT NOT NULL,
    phone TEXT, text TEXT, outcome TEXT, meta TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS touches_prospect ON touches(prospect_id, channel, created_at);
CREATE TABLE IF NOT EXISTS calls (
    call_sid TEXT PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id),
    phone TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wa_outbox (
    id INTEGER PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id),
    phone TEXT NOT NULL, text TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'opener',
    status TEXT NOT NULL DEFAULT 'queued',
    error TEXT, created_at TEXT NOT NULL, sent_at TEXT
);
CREATE TABLE IF NOT EXISTS wa_chats (
    phone TEXT PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    mode TEXT NOT NULL DEFAULT 'ai',
    ai_disclosed INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS llm_usage (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL, purpose TEXT,
    input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
    usd REAL NOT NULL
);
"""


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).astimezone(UTC).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---- low level -------------------------------------------------------
    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self.conn.execute(sql, tuple(params))
            self.conn.commit()
            return cur

    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self.conn.execute(sql, tuple(params)).fetchone()

    def all(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self.conn.execute(sql, tuple(params)).fetchall()

    # ---- prospects ---------------------------------------------------------
    def upsert_prospect(self, p: dict[str, Any]) -> int:
        row = self.one("SELECT id FROM prospects WHERE id = ?", (p["id"],))
        cols = ["firm", "segment", "size", "priority", "suggested_plan", "website",
                "phones", "emails", "contact_page", "source", "owner_notes", "contact_name"]
        values = [json.dumps(p.get(c) or []) if c == "phones" else p.get(c) for c in cols]
        if row:
            sets = ", ".join(f"{c} = ?" for c in cols)
            self.execute(f"UPDATE prospects SET {sets} WHERE id = ?", (*values, p["id"]))
        else:
            self.execute(
                f"INSERT INTO prospects (id, {', '.join(cols)}, created_at) VALUES (?, {', '.join('?' * len(cols))}, ?)",
                (p["id"], *values, iso()),
            )
        return int(p["id"])

    def prospect(self, prospect_id: int) -> dict[str, Any] | None:
        row = self.one("SELECT * FROM prospects WHERE id = ?", (prospect_id,))
        return _prospect(row) if row else None

    def prospects(self, priority: str | None = None) -> list[dict[str, Any]]:
        if priority:
            rows = self.all("SELECT * FROM prospects WHERE priority LIKE ? ORDER BY id", (f"{priority}%",))
        else:
            rows = self.all("SELECT * FROM prospects ORDER BY id")
        return [_prospect(r) for r in rows]

    def prospect_by_phone(self, phone: str) -> dict[str, Any] | None:
        for r in self.all("SELECT * FROM prospects WHERE phones LIKE ?", (f'%"{phone}"%',)):
            return _prospect(r)
        return None

    # ---- research and drafts ---------------------------------------------
    def save_profile(self, prospect_id: int, profile: dict[str, Any]) -> None:
        self.execute(
            "INSERT OR REPLACE INTO profiles (prospect_id, profile, confidence, sources, researched_at) VALUES (?, ?, ?, ?, ?)",
            (prospect_id, json.dumps(profile, ensure_ascii=False), profile.get("confidence"),
             json.dumps(profile.get("sources", [])), iso()),
        )

    def profile(self, prospect_id: int) -> dict[str, Any] | None:
        row = self.one("SELECT profile FROM profiles WHERE prospect_id = ?", (prospect_id,))
        return json.loads(row["profile"]) if row else None

    def save_draft(self, prospect_id: int, kind: str, text: str) -> None:
        self.execute(
            "INSERT OR REPLACE INTO drafts (prospect_id, kind, text, created_at) VALUES (?, ?, ?, ?)",
            (prospect_id, kind, text, iso()),
        )
        # A changed draft needs a fresh look before it can go out.
        channel = {"wa_opener": "whatsapp", "call_brief": "call"}.get(kind)
        if channel:
            self.execute("DELETE FROM approvals WHERE prospect_id = ? AND channel = ?", (prospect_id, channel))

    def draft(self, prospect_id: int, kind: str) -> str | None:
        row = self.one("SELECT text FROM drafts WHERE prospect_id = ? AND kind = ?", (prospect_id, kind))
        return row["text"] if row else None

    # ---- approvals ---------------------------------------------------------
    def approve(self, prospect_id: int, channel: str) -> None:
        self.execute(
            "INSERT OR REPLACE INTO approvals (prospect_id, channel, approved_at) VALUES (?, ?, ?)",
            (prospect_id, channel, iso()),
        )

    def revoke(self, prospect_id: int, channel: str) -> None:
        self.execute("DELETE FROM approvals WHERE prospect_id = ? AND channel = ?", (prospect_id, channel))

    def is_approved(self, prospect_id: int, channel: str) -> bool:
        return self.one(
            "SELECT 1 FROM approvals WHERE prospect_id = ? AND channel = ?", (prospect_id, channel)
        ) is not None

    # ---- opt-outs and DND --------------------------------------------------
    def suppress(self, phone: str, reason: str, source: str = "") -> None:
        self.execute(
            "INSERT OR IGNORE INTO suppressions (phone, reason, source, created_at) VALUES (?, ?, ?, ?)",
            (phone, reason, source, iso()),
        )
        # Nothing already queued may go out after an opt-out.
        self.execute(
            "UPDATE wa_outbox SET status = 'blocked', error = 'opted out' WHERE phone = ? AND status = 'queued'",
            (phone,),
        )

    def is_suppressed(self, phone: str) -> bool:
        return self.one("SELECT 1 FROM suppressions WHERE phone = ?", (phone,)) is not None

    def set_dnd(self, phone: str, registered: bool, checked_at: datetime | None = None) -> None:
        self.execute(
            "INSERT OR REPLACE INTO dnd (phone, registered, checked_at) VALUES (?, ?, ?)",
            (phone, 1 if registered else 0, iso(checked_at)),
        )

    def dnd(self, phone: str) -> sqlite3.Row | None:
        return self.one("SELECT registered, checked_at FROM dnd WHERE phone = ?", (phone,))

    # ---- log ---------------------------------------------------------------
    def log(self, channel: str, direction: str, *, prospect_id: int | None = None,
            phone: str | None = None, text: str | None = None,
            outcome: str | None = None, meta: dict[str, Any] | None = None) -> None:
        self.execute(
            "INSERT INTO touches (prospect_id, channel, direction, phone, text, outcome, meta, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (prospect_id, channel, direction, phone, text, outcome,
             json.dumps(meta or {}, ensure_ascii=False), iso()),
        )

    def touches(self, prospect_id: int, channel: str | None = None) -> list[sqlite3.Row]:
        if channel:
            return self.all("SELECT * FROM touches WHERE prospect_id = ? AND channel = ? ORDER BY id", (prospect_id, channel))
        return self.all("SELECT * FROM touches WHERE prospect_id = ? ORDER BY id", (prospect_id,))

    # ---- LLM spend ---------------------------------------------------------
    def add_llm_usage(self, purpose: str, input_tokens: int, output_tokens: int, usd: float) -> None:
        self.execute(
            "INSERT INTO llm_usage (day, purpose, input_tokens, output_tokens, usd) VALUES (?, ?, ?, ?, ?)",
            (utcnow().date().isoformat(), purpose, input_tokens, output_tokens, usd),
        )

    def llm_spend_today(self) -> float:
        row = self.one("SELECT COALESCE(SUM(usd), 0) AS s FROM llm_usage WHERE day = ?", (utcnow().date().isoformat(),))
        return float(row["s"]) if row else 0.0


def _prospect(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["phones"] = json.loads(d.get("phones") or "[]")
    return d
