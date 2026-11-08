"""Tool catalog, per-tenant tool connections (persisted) and the post-call action chain.

HONESTY NOTE: no Composio API credentials are configured, so nothing here talks to
WhatsApp, Google, Zoho etc. Connections are stored as SIMULATED and every execution is
logged with status SIMULATED and live=False. Replace the logging in
`execute_post_call_chain` with a real Composio call once an API key and per-user OAuth
exist; the rest of the flow stays the same.
Real delivery today happens only via app/core/agent_forwarders.py (Sheets webhook + WhatsApp Cloud API).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sangamitra_release import ComposioConnectionModel, ComposioExecutionLogModel

COMPOSIO_TOOL_CATALOG: Dict[str, Dict[str, Any]] = {
    "WHATSAPP": {
        "app": "WHATSAPP",
        "title": "WhatsApp Business Cloud",
        "actions": ["WHATSAPP_SEND_TEMPLATE_MESSAGE", "WHATSAPP_SEND_LOCATION", "WHATSAPP_SEND_BROCHURE"],
        "description": "Sends instant lead briefs to the business owner and confirmation/brochures + VCard to the caller.",
        "auth_mode": "OAUTH2_ONE_TAP",
    },
    "GOOGLESHEETS": {
        "app": "GOOGLESHEETS",
        "title": "Google Sheets Live CRM Ledger",
        "actions": ["GOOGLESHEETS_APPEND_ROW", "GOOGLESHEETS_LOOKUP_PRICE_ROW"],
        "description": "Appends every caller's name, phone, requirement, quantity, and language into a live Google Sheet.",
        "auth_mode": "GOOGLE_ONE_TAP_SCOPE",
    },
    "GOOGLECALENDAR": {
        "app": "GOOGLECALENDAR",
        "title": "Google Calendar & Slot Scheduler",
        "actions": ["GOOGLECALENDAR_FIND_FREE_SLOTS", "GOOGLECALENDAR_CREATE_EVENT"],
        "description": "Checks availability and books appointments, factory visits, or callback slots automatically.",
        "auth_mode": "GOOGLE_ONE_TAP_SCOPE",
    },
    "GMAIL": {
        "app": "GMAIL",
        "title": "Gmail Quotation & Summary Dispatcher",
        "actions": ["GMAIL_SEND_EMAIL", "GMAIL_CREATE_DRAFT"],
        "description": "Sends formal PDF quotations and daily call summaries via email.",
        "auth_mode": "GOOGLE_ONE_TAP_SCOPE",
    },
    "ZOHO_CRM": {
        "app": "ZOHO_CRM",
        "title": "Zoho CRM & Zoho Books India",
        "actions": ["ZOHOCRM_UPSERT_LEAD", "ZOHOCRM_ADD_CALL_NOTE"],
        "description": "Creates or updates B2B/MSME leads inside Zoho CRM with full call transcript.",
        "auth_mode": "OAUTH2_ONE_TAP",
    },
    "HUBSPOT": {
        "app": "HUBSPOT",
        "title": "HubSpot CRM Pipeline",
        "actions": ["HUBSPOT_CREATE_CONTACT", "HUBSPOT_CREATE_DEAL"],
        "description": "Syncs high-ticket real estate, clinic, or B2B manufacturing enquiries to HubSpot.",
        "auth_mode": "OAUTH2_ONE_TAP",
    },
    "NOTION": {
        "app": "NOTION",
        "title": "Notion Personal Assistant Workspace",
        "actions": ["NOTION_APPEND_PAGE", "NOTION_CREATE_TASK"],
        "description": "Logs screened calls, tasks, and executive summaries for individuals and founders.",
        "auth_mode": "OAUTH2_ONE_TAP",
    },
    "RAZORPAY": {
        "app": "RAZORPAY",
        "title": "Razorpay Instant UPI Payment Links",
        "actions": ["RAZORPAY_CREATE_PAYMENT_LINK"],
        "description": "Texts an instant UPI payment link to the caller to collect booking deposits or advance payments.",
        "auth_mode": "API_KEY_OR_OAUTH",
    },
    "TALLY_PRIME": {
        "app": "TALLY_PRIME",
        "title": "Tally Prime / ERP 9 B2B Voucher Sync",
        "actions": ["TALLY_CREATE_SALES_ORDER", "TALLY_LOOKUP_PARTY_LEDGER"],
        "description": "Pushes B2B sales inquiries and draft proforma orders into Tally Prime.",
        "auth_mode": "CONNECTOR_TOKEN",
    },
    "SHOPIFY": {
        "app": "SHOPIFY",
        "title": "Shopify D2C Order & COD Verifier",
        "actions": ["SHOPIFY_GET_ORDER_STATUS", "SHOPIFY_TAG_COD_CONFIRMED"],
        "description": "Verifies Cash-on-Delivery (COD) orders by voice and reduces D2C Return-to-Origin (RTO).",
        "auth_mode": "OAUTH2_ONE_TAP",
    },
    "SHIPROCKET": {
        "app": "SHIPROCKET",
        "title": "Shiprocket / Delhivery Parcel Tracker",
        "actions": ["SHIPROCKET_TRACK_AWB", "SHIPROCKET_UPDATE_NDR"],
        "description": "Fetches real-time courier tracking status and logs Non-Delivery Report (NDR) re-attempt instructions.",
        "auth_mode": "API_KEY_OR_OAUTH",
    },
    "INDIAMART": {
        "app": "INDIAMART",
        "title": "IndiaMART Lead Manager Auto-Caller",
        "actions": ["INDIAMART_FETCH_BUY_LEADS", "INDIAMART_LOG_CALL_OUTCOME"],
        "description": "Syncs B2B wholesale inquiries from IndiaMART and logs qualification status.",
        "auth_mode": "CRM_KEY_ONE_TAP",
    },
    "TELEGRAM": {
        "app": "TELEGRAM",
        "title": "Telegram Instant Sales Desk Bot",
        "actions": ["TELEGRAM_SEND_ALERT"],
        "description": "Dispatches instant call alerts with 1-tap Call Back buttons to a team Telegram group.",
        "auth_mode": "BOT_LINK_ONE_TAP",
    },
}


LIVE = False  # flips to True only when a real Composio integration is wired in
STATUS_CONNECTED = "SIMULATED_CONNECTED"
STATUS_EXECUTED = "SIMULATED"

_ALWAYS_ON_ACTIONS = {
    "WHATSAPP": "WHATSAPP_SEND_TEMPLATE_MESSAGE",
    "GOOGLESHEETS": "GOOGLESHEETS_APPEND_ROW",
}
_EXTRA_APPS = ("ZOHO_CRM", "HUBSPOT", "NOTION", "RAZORPAY", "TALLY_PRIME", "SHOPIFY", "SHIPROCKET", "INDIAMART", "TELEGRAM")
_SECRET_WORDS = ("token", "secret", "password", "key")


def _conn_view(c: ComposioConnectionModel) -> Dict[str, Any]:
    return {
        "status": c.status,
        "connection_id": c.connection_id,
        "connected_at": c.connected_at.isoformat(),
        "live": LIVE,
        **(c.metadata_json or {}),
    }


async def _connections(session: AsyncSession, tenant_id: str) -> Dict[str, ComposioConnectionModel]:
    rows = (
        await session.execute(select(ComposioConnectionModel).where(ComposioConnectionModel.tenant_id == tenant_id))
    ).scalars().all()
    return {r.app_name: r for r in rows}


async def list_catalog_and_connections(session: AsyncSession, tenant_id: str) -> Dict[str, Any]:
    conns = await _connections(session, tenant_id)
    items = []
    for app_key, meta in COMPOSIO_TOOL_CATALOG.items():
        conn = conns.get(app_key)
        items.append(
            {
                **meta,
                "connected": conn is not None,
                "live": LIVE,
                "connection_details": _conn_view(conn) if conn else None,
            }
        )
    logs = (
        await session.execute(
            select(ComposioExecutionLogModel)
            .where(ComposioExecutionLogModel.tenant_id == tenant_id)
            .order_by(ComposioExecutionLogModel.executed_at.desc())
            .limit(15)
        )
    ).scalars().all()
    return {
        "tenant_id": tenant_id,
        "live": LIVE,
        "tools": items,
        "recent_executions": [
            {
                "execution_id": log.execution_id,
                "tenant_id": log.tenant_id,
                "app": log.app_name,
                "action": log.action,
                "status": log.status,
                "payload": log.payload_json,
                "executed_at": log.executed_at.isoformat(),
            }
            for log in logs
        ],
    }


async def connect_tool(
    session: AsyncSession, tenant_id: str, app_name: str, target_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    app_key = app_name.upper().strip()
    if app_key not in COMPOSIO_TOOL_CATALOG:
        raise ValueError(f"Unsupported app: {app_name}")
    # Never persist secrets or oversized blobs the client sends as "metadata".
    meta = {
        str(k)[:40]: str(v)[:200]
        for k, v in list((target_metadata or {}).items())[:10]
        if not any(w in str(k).lower() for w in _SECRET_WORDS)
    }
    conn = (await _connections(session, tenant_id)).get(app_key)
    if conn is None:
        conn = ComposioConnectionModel(
            tenant_id=tenant_id, app_name=app_key, connection_id=f"sim_{uuid.uuid4().hex[:10]}"
        )
        session.add(conn)
    conn.status = STATUS_CONNECTED
    conn.metadata_json = meta
    await session.flush()
    return {"tenant_id": tenant_id, "app": app_key, "status": conn.status, "live": LIVE, "connection": _conn_view(conn)}


async def disconnect_tool(session: AsyncSession, tenant_id: str, app_name: str) -> Dict[str, Any]:
    app_key = app_name.upper().strip()
    conn = (await _connections(session, tenant_id)).get(app_key)
    if conn is not None:
        await session.delete(conn)
    return {"tenant_id": tenant_id, "app": app_key, "status": "DISCONNECTED"}


async def execute_post_call_chain(
    session: AsyncSession,
    tenant_id: str,
    caller_name: str,
    caller_phone: str,
    requirement_summary: str,
    language: str = "kn-IN",
    preferred_time: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Log the actions that WOULD run for each connected tool. See the module honesty note."""
    conns = await _connections(session, tenant_id)
    if not conns:
        return []
    base = {"caller_name": caller_name, "caller_phone": caller_phone, "summary": requirement_summary, "language": language}
    plan: List[tuple] = []
    for app_key, action in _ALWAYS_ON_ACTIONS.items():
        if app_key in conns:
            plan.append((app_key, action, dict(base)))
    if "GOOGLECALENDAR" in conns and preferred_time:
        plan.append(("GOOGLECALENDAR", "GOOGLECALENDAR_CREATE_EVENT", {**base, "slot": preferred_time}))
    for app_key in _EXTRA_APPS:
        if app_key in conns:
            plan.append((app_key, COMPOSIO_TOOL_CATALOG[app_key]["actions"][0], dict(base)))

    executed = []
    for app_key, action, payload in plan:
        log = ComposioExecutionLogModel(
            execution_id=f"exec_{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            app_name=app_key,
            action=action,
            status=STATUS_EXECUTED,
            payload_json=payload,
        )
        session.add(log)
        executed.append(
            {
                "execution_id": log.execution_id,
                "tenant_id": tenant_id,
                "app": app_key,
                "action": action,
                "status": STATUS_EXECUTED,
                "live": LIVE,
            }
        )
    await session.flush()
    return executed
