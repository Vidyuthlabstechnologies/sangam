from datetime import UTC, datetime

from fieldos_sales.config import Settings
from fieldos_sales.store import Store

# A Tuesday, 11:30 IST: inside default contact hours.
WORK_HOURS = datetime(2026, 11, 10, 6, 0, tzinfo=UTC)
MOBILE = "+919100050801"
LANDLINE = "+914023418080"


def make(live=True, **overrides):
    settings = Settings(live=live, **overrides)
    store = Store(":memory:")
    store.upsert_prospect({"id": 1, "firm": "Demo Builders", "segment": "Developer", "size": "Mid",
                           "priority": "A - best fit", "phones": [MOBILE, LANDLINE]})
    return settings, store


def ready_for(store, channel, phone=MOBILE):
    kind = "wa_opener" if channel == "whatsapp" else "call_brief"
    store.save_draft(1, kind, "Namaste, this is the FieldOS team. Reply STOP and we won't message again.")
    store.approve(1, channel)
    store.set_dnd(phone, False, WORK_HOURS)
