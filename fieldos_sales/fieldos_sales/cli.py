"""Command line: python -m fieldos_sales <command> ...  (run with --help for the list)."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from .compliance import can_contact, import_dnd_csv
from .config import Settings
from .conversation import Conversation
from .llm import make_llm
from .pitch import write_pitch
from .prospects import import_xlsx, normalise_indian_phone
from .research import research_prospect
from .store import Store


def parse_ids(value: str) -> list[int]:
    ids: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            ids.extend(range(int(a), int(b) + 1))
        elif part:
            ids.append(int(part))
    return ids


def _select(store: Store, args: argparse.Namespace) -> list[dict]:
    if getattr(args, "ids", None):
        return [p for p in (store.prospect(i) for i in parse_ids(args.ids)) if p]
    rows = store.prospects(getattr(args, "priority", None))
    limit = getattr(args, "limit", None)
    return rows[:limit] if limit else rows


def cmd_import(args, settings, store):
    n = import_xlsx(store, Path(args.xlsx), args.sheet)
    print(f"Imported {n} prospects into {settings.db_path}")


def cmd_list(args, settings, store):
    for p in _select(store, args):
        researched = "R" if store.profile(p["id"]) else "-"
        drafted = "D" if store.draft(p["id"], "wa_opener") else "-"
        ok = ("W" if store.is_approved(p["id"], "whatsapp") else "-") + ("C" if store.is_approved(p["id"], "call") else "-")
        print(f"{p['id']:>4} {researched}{drafted}{ok} {(p.get('priority') or '')[:1]:1} {p['firm'][:44]:44} {', '.join(p['phones'])[:40]}")
    print("\nFlags: R researched, D drafted, W approved for WhatsApp, C approved for calls")


def cmd_research(args, settings, store):
    llm = make_llm(settings, store)
    for p in _select(store, args):
        if store.profile(p["id"]) and not args.force:
            continue
        print(f"Researching {p['id']} {p['firm']} ...", flush=True)
        try:
            profile = research_prospect(p, llm)
        except Exception as e:  # keep going through the list
            print(f"  failed: {e}")
            continue
        store.save_profile(p["id"], profile)
        print(f"  {profile['confidence']}: {profile['summary'][:140]}")
    print(f"AI spend today: ${store.llm_spend_today():.4f}")


def cmd_pitch(args, settings, store):
    llm = make_llm(settings, store)
    for p in _select(store, args):
        profile = store.profile(p["id"])
        if not profile:
            print(f"{p['id']} {p['firm']}: research it first")
            continue
        out = write_pitch(p, profile, llm)
        store.save_draft(p["id"], "call_brief", out["call_brief"])
        store.save_draft(p["id"], "wa_opener", out["whatsapp_opener"])
        print(f"{p['id']} {p['firm']}: drafted")
    print(f"AI spend today: ${store.llm_spend_today():.4f}")


def _status_lines(store: Store, settings: Settings, p: dict) -> list[str]:
    lines = []
    for phone in p["phones"] or ["(no phone)"]:
        for channel in ("whatsapp", "call"):
            if phone.startswith("+"):
                d = can_contact(store, settings, p, phone, channel)
                lines.append(f"  {channel:8} {phone}: {'READY' if d.ok else 'blocked: ' + '; '.join(d.reasons)}")
    return lines


def cmd_show(args, settings, store):
    p = store.prospect(args.id)
    if not p:
        sys.exit("No such prospect")
    print(f"# {p['id']} {p['firm']} ({p.get('segment')}, {p.get('size')}, {p.get('priority')})")
    print(f"Website: {p.get('website')}  Phones: {', '.join(p['phones'])}")
    profile = store.profile(p["id"])
    print("\n## Profile\n" + (json.dumps(profile, indent=2, ensure_ascii=False) if profile else "(not researched)"))
    print("\n## Call brief\n" + (store.draft(p["id"], "call_brief") or "(none)"))
    print("\n## WhatsApp opener\n" + (store.draft(p["id"], "wa_opener") or "(none)"))
    print("\n## Can we contact them now?")
    print("\n".join(_status_lines(store, settings, p)))
    touches = store.touches(p["id"])
    if touches:
        print("\n## History")
        for t in touches[-15:]:
            print(f"  {t['created_at']} {t['channel']} {t['direction']} {t['outcome'] or ''} {(t['text'] or '')[:100]}")


def cmd_review(args, settings, store):
    out = Path(args.out or settings.data_dir / "review.md")
    parts = ["# FieldOS outreach drafts for review\n",
             "Read each draft. Approve with: python -m fieldos_sales approve --channel whatsapp --ids 1,4,7\n"]
    for p in _select(store, args):
        opener = store.draft(p["id"], "wa_opener")
        if not opener:
            continue
        profile = store.profile(p["id"]) or {}
        parts.append(f"\n## {p['id']}. {p['firm']}\n")
        parts.append(f"Research confidence: **{profile.get('confidence', '?')}**. {profile.get('summary', '')}\n")
        if profile.get("sources"):
            parts.append("Sources: " + ", ".join(profile["sources"]) + "\n")
        parts.append("\n**WhatsApp opener**\n\n> " + opener.replace("\n", "\n> ") + "\n")
        parts.append("\n**Call brief**\n\n" + (store.draft(p["id"], "call_brief") or "") + "\n")
        parts.append("\n" + "\n".join(_status_lines(store, settings, p)) + "\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {out}")


def cmd_approve(args, settings, store):
    for pid in parse_ids(args.ids):
        p = store.prospect(pid)
        if not p:
            print(f"{pid}: no such prospect")
            continue
        kind = "wa_opener" if args.channel == "whatsapp" else "call_brief"
        if not store.draft(pid, kind):
            print(f"{pid} {p['firm']}: no draft yet, not approved")
            continue
        if args.revoke:
            store.revoke(pid, args.channel)
            print(f"{pid} {p['firm']}: approval removed for {args.channel}")
        else:
            store.approve(pid, args.channel)
            print(f"{pid} {p['firm']}: approved for {args.channel}")


def cmd_import_dnd(args, settings, store):
    total, registered = import_dnd_csv(store, Path(args.csv))
    print(f"Loaded {total} scrub results; {registered} numbers are on DND and will never be called")


def cmd_optout(args, settings, store):
    phone = normalise_indian_phone(args.phone)
    if not phone:
        sys.exit("Not an Indian number")
    store.suppress(phone, args.reason or "added by hand", "cli")
    print(f"{phone} will never be called or messaged")


def cmd_simulate(args, settings, store):
    """Rehearse a call or chat in the terminal. You play the prospect. Nothing is sent."""
    p = store.prospect(args.id)
    if not p:
        sys.exit("No such prospect")
    phone = p["phones"][0] if p["phones"] else "+910000000000"
    sim = Store(":memory:")  # opt-outs during a rehearsal must not touch the real list
    sim.upsert_prospect({**p})
    if store.profile(p["id"]):
        sim.save_profile(p["id"], store.profile(p["id"]))
    for kind in ("call_brief", "wa_opener"):
        if store.draft(p["id"], kind):
            sim.save_draft(p["id"], kind, store.draft(p["id"], kind))
    convo = Conversation.load(sim, make_llm(settings, store), sim.prospect(p["id"]), phone, args.channel)
    print(f"Rehearsing a {args.channel} with {p['firm']}. Type as the prospect; empty line or Ctrl-D ends.\n")
    if args.channel == "call":
        print("AI:", convo.opening())
    else:
        print("AI (opener):", store.draft(p["id"], "wa_opener") or "(no opener drafted)")
    while not convo.finished:
        try:
            said = input("You: ").strip()
        except EOFError:
            break
        if not said:
            break
        turn = convo.respond(said)
        print("AI:", turn.say)
        if turn.outcome:
            print(f"   [{turn.outcome}] {turn.note} {turn.demo_slot}")
            if args.channel == "call":
                break


def cmd_call(args, settings, store):
    from .telephony import ExotelDialer

    p = store.prospect(args.id)
    if not p:
        sys.exit("No such prospect")
    phone = normalise_indian_phone(args.phone) if args.phone else (p["phones"][0] if p["phones"] else None)
    if not phone:
        sys.exit("No phone number")
    decision = can_contact(store, settings, p, phone, "call")
    if not decision:
        sys.exit("Not calling: " + "; ".join(decision.reasons))
    sid = ExotelDialer(settings).dial(phone, p["id"])
    from .store import iso
    store.execute("INSERT INTO calls (call_sid, prospect_id, phone, status, created_at) VALUES (?, ?, ?, 'queued', ?)",
                  (sid, p["id"], phone, iso()))
    store.log("call", "out", prospect_id=p["id"], phone=phone, outcome="dialled", meta={"call_sid": sid})
    print(f"Calling {p['firm']} on {phone} (call {sid})")


def cmd_wa_queue(args, settings, store):
    from .whatsapp import queue_openers
    print("\n".join(queue_openers(store, parse_ids(args.ids))))


def cmd_wa_followups(args, settings, store):
    from .whatsapp import queue_followups
    print(f"Queued {queue_followups(store, args.after_days)} follow-ups")


def cmd_wa_preview(args, settings, store):
    from .whatsapp import DryGateway, send_next
    print(asyncio.run(send_next(store, settings, DryGateway())) or "Nothing queued")


def cmd_status(args, settings, store):
    q = lambda sql: store.one(sql)[0]
    print(f"Live mode: {'ON' if settings.live else 'off (dry run)'}   WhatsApp gateway: {settings.whatsapp_gateway}")
    print(f"Prospects {q('SELECT COUNT(*) FROM prospects')}, researched {q('SELECT COUNT(*) FROM profiles')}, "
          f"drafted {q('SELECT COUNT(*) FROM drafts WHERE kind = ' + chr(39) + 'wa_opener' + chr(39))}")
    print(f"Approved: WhatsApp {q('SELECT COUNT(*) FROM approvals WHERE channel = ' + chr(39) + 'whatsapp' + chr(39))}, "
          f"calls {q('SELECT COUNT(*) FROM approvals WHERE channel = ' + chr(39) + 'call' + chr(39))}")
    for status, n in store.all("SELECT status, COUNT(*) FROM wa_outbox GROUP BY status"):
        print(f"WhatsApp outbox {status}: {n}")
    for outcome, n in store.all("SELECT outcome, COUNT(*) FROM touches WHERE direction = 'event' GROUP BY outcome"):
        print(f"Outcome {outcome}: {n}")
    print(f"Opted out: {q('SELECT COUNT(*) FROM suppressions')}   AI spend today: ${store.llm_spend_today():.4f}")


def cmd_serve(args, settings, store):
    import uvicorn

    from .server import create_app
    uvicorn.run(create_app(settings, store), host=args.host, port=args.port)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(prog="python -m fieldos_sales", description="FieldOS AI sales calling and WhatsApp agents")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_, select=False):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        if select:
            sp.add_argument("--ids", help="e.g. 1,4,7-12")
            sp.add_argument("--priority", help="A, B or C")
            sp.add_argument("--limit", type=int)
        return sp

    sp = add("import", cmd_import, "import prospects from the target-firm xlsx")
    sp.add_argument("xlsx")
    sp.add_argument("--sheet", default="Firms")
    add("list", cmd_list, "list prospects", select=True)
    sp = add("research", cmd_research, "research each firm's website", select=True)
    sp.add_argument("--force", action="store_true")
    add("pitch", cmd_pitch, "write a call brief and WhatsApp opener per firm", select=True)
    sp = add("show", cmd_show, "show one prospect: profile, drafts, whether we may contact them")
    sp.add_argument("id", type=int)
    sp = add("review", cmd_review, "write all drafts to a review file", select=True)
    sp.add_argument("--out")
    sp = add("approve", cmd_approve, "approve prospects for a channel (after reading their drafts)")
    sp.add_argument("--channel", choices=["whatsapp", "call"], required=True)
    sp.add_argument("--ids", required=True)
    sp.add_argument("--revoke", action="store_true")
    sp = add("import-dnd", cmd_import_dnd, "load a DND/NCPR scrub result CSV (phone,dnd)")
    sp.add_argument("csv")
    sp = add("optout", cmd_optout, "never contact a number again")
    sp.add_argument("phone")
    sp.add_argument("--reason")
    sp = add("simulate", cmd_simulate, "rehearse a call or chat in the terminal (nothing is sent)")
    sp.add_argument("id", type=int)
    sp.add_argument("--channel", choices=["call", "whatsapp"], default="call")
    sp = add("call", cmd_call, "place one real AI call (live mode, approved, DND-scrubbed only)")
    sp.add_argument("id", type=int)
    sp.add_argument("--phone")
    sp = add("wa-queue", cmd_wa_queue, "queue WhatsApp openers for approved prospects")
    sp.add_argument("--ids", required=True)
    sp = add("wa-followups", cmd_wa_followups, "queue one follow-up where an opener got no reply")
    sp.add_argument("--after-days", type=int, default=3)
    add("wa-preview", cmd_wa_preview, "show the next message the sender would send, and whether it may")
    add("status", cmd_status, "counts, outcomes and AI spend")
    sp = add("serve", cmd_serve, "run the WhatsApp webhooks, the slow sender and the call audio stream")
    sp.add_argument("--host", default="0.0.0.0")
    sp.add_argument("--port", type=int, default=8090)

    args = ap.parse_args(argv)
    settings = Settings.from_env()
    store = Store(settings.db_path)
    args.fn(args, settings, store)
