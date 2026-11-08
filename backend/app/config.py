import re
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Sangam"
    app_version: str = "0.1.0"
    debug: bool = False
    # "production" turns on validate_production_settings() at startup.
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://sangam:sangam@localhost:5432/sangam"
    # Empty means in-process rate limits. Set REDIS_URL (compose and k8s do)
    # so every replica shares one counter.
    redis_url: str = ""
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"

    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800
    db_connect_timeout_seconds: int = 10
    db_command_timeout_seconds: int = 30

    # Optional MinIO/S3. All four must be set; otherwise uploads stay in the
    # existing extraction path and nothing is written to object storage.
    s3_endpoint_url: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_region: str = "us-east-1"

    # Optional OpenAI-compatible chat endpoint (Ollama, vLLM, llama.cpp).
    # Off unless LLM_BASE_URL is set. Sarvam remains the provider when
    # SARVAM_API_KEY is set. No model weights are bundled.
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None

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

    # SMTP is the mail path. Unset SMTP_HOST means mail is skipped (no paid API).
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
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

    # Firebase Authentication. The Android app signs users in with Google or
    # email/password through Firebase and sends the Firebase ID token. Set this
    # to the Firebase project id (android/app/google-services.json
    # project_info.project_id) to accept those tokens. Unset means Firebase
    # tokens are rejected.
    firebase_project_id: Optional[str] = None
    # Optional override of Google's securetoken JWKS URL (tests, proxies).
    firebase_jwks_url: Optional[str] = None
    # Reject email/password accounts until the address is verified.
    firebase_require_verified_email: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

_FIREBASE_PROJECT_RE = re.compile(r"[a-z][a-z0-9-]{4,29}")

def database_password(url: str) -> str:
    """Return the password embedded in a SQLAlchemy URL, or ""."""
    from urllib.parse import urlparse

    normalized = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    normalized = normalized.replace("postgresql+psycopg://", "postgresql://", 1)
    normalized = normalized.replace("postgresql+psycopg2://", "postgresql://", 1)
    return urlparse(normalized).password or ""


def validate_production_settings(s: Settings) -> None:
    """Refuse to start in production without a way to verify sign-in tokens.

    Sangam mints no tokens. Firebase (the Android app) or self-hosted Zitadel
    (the web dashboard) issues them, and at least one must be configured, or
    every request would be a 401. Fixture mode returns canned payment and AI
    responses and must not run as production.
    """
    if s.environment.strip().lower() != "production":
        return

    problems = []
    firebase_project = (s.firebase_project_id or "").strip()
    issuer = (s.zitadel_issuer or "").strip()
    if not firebase_project and not issuer:
        problems.append(
            "Set FIREBASE_PROJECT_ID or ZITADEL_ISSUER so sign-in tokens can be verified"
        )
    if firebase_project and not _FIREBASE_PROJECT_RE.fullmatch(firebase_project):
        problems.append("FIREBASE_PROJECT_ID must be a Firebase project id such as my-app-1234")
    if issuer and not issuer.startswith("https://"):
        problems.append("ZITADEL_ISSUER must be the https URL of the self-hosted Zitadel instance")
    if s.zitadel_client_id and not issuer:
        problems.append("ZITADEL_CLIENT_ID is set but ZITADEL_ISSUER is missing")
    if issuer and not any((s.zitadel_client_id, s.zitadel_android_client_id, s.zitadel_project_id)):
        problems.append("Set ZITADEL_CLIENT_ID or ZITADEL_PROJECT_ID so access-token audiences can be checked")
    if s.use_fixtures:
        problems.append("USE_FIXTURES must be false")
    if s.debug:
        problems.append("DEBUG must be false")
    if database_password(s.database_url) == "sangam":
        problems.append("DATABASE_URL must not use the default Postgres password")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
