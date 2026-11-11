"""Settings, read from the environment and an optional .env file.

Every outbound action (a real call, a real WhatsApp message) is off unless
FIELDOS_SALES_LIVE=1. Even then each prospect must be approved for that
channel, and every compliance check must pass at send time.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    """Minimal .env reader: KEY=VALUE lines; existing env vars win."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _hours(value: str) -> tuple[int, int]:
    try:
        start, end = value.split("-", 1)
        s, e = int(start), int(end)
        if 0 <= s < e <= 24:
            return s, e
    except ValueError:
        pass
    return 10, 19


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: PACKAGE_ROOT / "data")
    live: bool = False

    anthropic_api_key: str = ""
    model: str = "claude-haiku-5-5"
    llm_daily_budget_usd: float = 1.0

    sarvam_api_key: str = ""
    sarvam_speaker: str = "anushka"
    sarvam_tts_model: str = "bulbul:v3"
    agent_name: str = "Priya"
    agent_gender: str = "f"
    voice_pace: float = 1.05
    end_of_turn_ms: int = 650

    exotel_sid: str = ""
    exotel_api_key: str = ""
    exotel_api_token: str = ""
    exotel_subdomain: str = "api.exotel.com"
    exotel_caller_id: str = ""
    exotel_flow_url: str = ""
    voice_stream_token: str = ""
    public_base_url: str = ""

    whatsapp_gateway: str = "waha"
    waha_url: str = "http://localhost:3000"
    waha_api_key: str = ""
    waha_session: str = "default"
    wa_webhook_token: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    owner_notify_number: str = ""

    calls_per_day: int = 20
    wa_new_chats_per_day: int = 15
    wa_min_gap_seconds: int = 240
    wa_max_gap_seconds: int = 540
    contact_hours: tuple[int, int] = (10, 19)
    contact_days: tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
    dnd_max_age_days: int = 7
    dashboard_token: str = ""
    auto_summarise: bool = True

    @property
    def db_path(self) -> Path:
        return self.data_dir / "sales.db"

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv(PACKAGE_ROOT / ".env")
        env = os.environ.get
        data_dir = Path(env("FIELDOS_SALES_DATA_DIR", "") or PACKAGE_ROOT / "data")
        days = tuple(d.strip()[:3].title() for d in (env("CONTACT_DAYS", "") or "Mon,Tue,Wed,Thu,Fri,Sat").split(",") if d.strip())
        return cls(
            data_dir=data_dir,
            live=env("FIELDOS_SALES_LIVE", "0").strip() == "1",
            anthropic_api_key=env("ANTHROPIC_API_KEY", ""),
            model=env("SALES_MODEL", "") or "claude-haiku-5-5",
            llm_daily_budget_usd=_float("LLM_DAILY_BUDGET_USD", 1.0),
            sarvam_api_key=env("SARVAM_API_KEY", ""),
            sarvam_speaker=env("SARVAM_SPEAKER", "") or "anushka",
            sarvam_tts_model=env("SARVAM_TTS_MODEL", "") or "bulbul:v3",
            agent_name=env("AGENT_NAME", "") or "Priya",
            agent_gender=(env("AGENT_GENDER", "") or "f").lower()[:1],
            voice_pace=_float("VOICE_PACE", 1.05),
            end_of_turn_ms=_int("END_OF_TURN_MS", 650),
            exotel_sid=env("EXOTEL_SID", ""),
            exotel_api_key=env("EXOTEL_API_KEY", ""),
            exotel_api_token=env("EXOTEL_API_TOKEN", ""),
            exotel_subdomain=env("EXOTEL_SUBDOMAIN", "") or "api.exotel.com",
            exotel_caller_id=env("EXOTEL_CALLER_ID", ""),
            exotel_flow_url=env("EXOTEL_FLOW_URL", ""),
            voice_stream_token=env("VOICE_STREAM_TOKEN", ""),
            public_base_url=env("PUBLIC_BASE_URL", "").rstrip("/"),
            whatsapp_gateway=(env("WHATSAPP_GATEWAY", "") or "waha").lower(),
            waha_url=(env("WAHA_URL", "") or "http://localhost:3000").rstrip("/"),
            waha_api_key=env("WAHA_API_KEY", ""),
            waha_session=env("WAHA_SESSION", "") or "default",
            wa_webhook_token=env("WA_WEBHOOK_TOKEN", ""),
            twilio_account_sid=env("TWILIO_ACCOUNT_SID", ""),
            twilio_auth_token=env("TWILIO_AUTH_TOKEN", ""),
            twilio_whatsapp_from=env("TWILIO_WHATSAPP_FROM", ""),
            owner_notify_number=env("OWNER_NOTIFY_NUMBER", ""),
            calls_per_day=_int("CALLS_PER_DAY", 20),
            wa_new_chats_per_day=_int("WA_NEW_CHATS_PER_DAY", 15),
            wa_min_gap_seconds=_int("WA_MIN_GAP_SECONDS", 240),
            wa_max_gap_seconds=_int("WA_MAX_GAP_SECONDS", 540),
            contact_hours=_hours(env("CONTACT_HOURS_IST", "") or "10-19"),
            contact_days=days or ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat"),
            dnd_max_age_days=_int("DND_MAX_AGE_DAYS", 7),
            dashboard_token=env("DASHBOARD_TOKEN", ""),
            auto_summarise=env("AUTO_SUMMARISE", "1").strip() != "0",
        )
