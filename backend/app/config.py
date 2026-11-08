from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "Sangam"
    app_version: str = "0.1.0"
    debug: bool = False
    # "production" turns on validate_production_settings() at startup.
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://sangam:sangam@localhost:5432/sangam"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "sangam"

    sarvam_api_key: Optional[str] = None

    razorpay_key_id: Optional[str] = None
    razorpay_key_secret: Optional[str] = None
    razorpay_webhook_secret: Optional[str] = None

    # When true (or when a service's credentials are absent), external
    # clients return deterministic canned responses through identical code
    # paths. Keeps tests hermetic and lets the demo run without live spend.
    use_fixtures: bool = False

    # Self-hosted Zitadel. Leave the issuer empty in tests and in default local
    # dev so the API never calls the network. Do not point this at Zitadel Cloud.
    # Access tokens are RS256. Audience is the web client, the Android public
    # client, or the Zitadel project id (Zitadel often puts the project in aud).
    zitadel_issuer: Optional[str] = None
    zitadel_client_id: Optional[str] = None
    zitadel_android_client_id: Optional[str] = None
    zitadel_project_id: Optional[str] = None
    # Optional override. When unset, keys are read from {issuer}/oauth/v2/keys.
    zitadel_jwks_url: Optional[str] = None

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "capabilities"

    allow_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost"

    jwt_secret: str = "CHANGE-ME-IN-PRODUCTION-GENERATE-A-SECURE-RANDOM-KEY"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    api_p99_target_ms: int = 100

    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_per_minute_ai: int = 10
    rate_limit_burst: int = 10

    fcm_project_id: str = "sangam-00001"
    fcm_server_key: Optional[str] = None

    notification_webhook_url: Optional[str] = None

    email_api_key: Optional[str] = None
    email_from: str = "noreply@sangam.ai"
    email_from_name: str = "Sangam"
    app_url: str = "http://localhost:5173"

    slack_webhook_url: Optional[str] = None

    # Shared secret the Sarvam voice agent sends in X-Webhook-Secret when it
    # posts a callback request. Unset means the webhook rejects everything.
    agent_webhook_secret: Optional[str] = None

    # Optional fan-out of each recorded callback. All unset means no forwarding.
    # Google Sheet: the deployed Apps Script web app URL, plus the secret it checks.
    callback_sheet_webhook_url: Optional[str] = None
    callback_sheet_webhook_secret: Optional[str] = None
    # WhatsApp Cloud API: staff are messaged with an APPROVED template whose body
    # has five placeholders (name, phone, service, preferred time, urgency).
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_access_token: Optional[str] = None
    whatsapp_staff_numbers: Optional[str] = None  # comma-separated, with country code
    whatsapp_template_name: str = "surya_new_callback"
    whatsapp_template_lang: str = "en"
    whatsapp_graph_version: Optional[str] = None  # set to a currently supported Graph API version

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()


def validate_production_settings(s: Settings) -> None:
    """Refuse to start in production without a real identity provider.

    Access tokens come from the self-hosted Zitadel issuer. Fixture mode
    returns canned payment and AI responses and must not run as production.
    """
    if s.environment.strip().lower() != "production":
        return

    problems = []
    issuer = (s.zitadel_issuer or "").strip()
    if not issuer.startswith("https://"):
        problems.append("ZITADEL_ISSUER must be the https URL of the self-hosted Zitadel instance")
    if not any((s.zitadel_client_id, s.zitadel_android_client_id, s.zitadel_project_id)):
        problems.append("Set ZITADEL_CLIENT_ID or ZITADEL_PROJECT_ID so access-token audiences can be checked")
    if s.use_fixtures:
        problems.append("USE_FIXTURES must be false")
    if s.debug:
        problems.append("DEBUG must be false")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
