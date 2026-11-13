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
    # Rate limits key on the client IP. Behind a proxy that APPENDS the real
    # client address to X-Forwarded-For (Cloud Run, most load balancers), set
    # this to how many entries from the right that address sits (1 on Cloud
    # Run). Entries further left are whatever the client sent and can be forged.
    # 0 uses the socket peer (or whatever uvicorn --proxy-headers resolved).
    client_ip_forwarded_hop: int = 0
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

    # Sarvam Voice Agents (Samvaad). A SEPARATE key from SARVAM_API_KEY: the two
    # are not interchangeable. It stays on the server; the app reaches agents only
    # through /voice-agents, which proxies the WebSocket. Org and workspace ids
    # come from the Samvaad dashboard URL or Settings. Missing key = fixture mode.
    sarvam_samvaad_api_key: Optional[str] = None
    samvaad_org_id: Optional[str] = None
    samvaad_workspace_id: Optional[str] = None
    samvaad_api_base: str = "https://apps.sarvam.ai/api"
    # Public https base of this API, used to build the outbound-call webhook URL.
    # Empty = taken from the request (Cloud Run forwards the https scheme).
    public_base_url: Optional[str] = None
    # Abuse guards on calls that spend money.
    samvaad_max_pending_calls: int = 5
    samvaad_max_session_seconds: int = 900

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
    # Reject email/password accounts until the address is verified. The app
    # sends the verification link and asks the user to sign in after tapping it.
    firebase_require_verified_email: bool = True

    # RevenueCat (Google Play Billing). The webhook is accepted only with this
    # exact Authorization header value, set in RevenueCat -> Integrations ->
    # Webhooks. Unset means the webhook rejects everything.
    revenuecat_webhook_auth: Optional[str] = None
    # Credit license-tester (sandbox) purchases. Keep true through closed
    # testing so testers can exercise paid features; set false at launch if
    # test purchases should not grant real call minutes.
    revenuecat_accept_sandbox: bool = True

    # Public legal pages (/legal/privacy, /legal/terms, /legal/delete-account).
    # Google Play shows these to users, so set them to real, monitored values.
    # Defaults are the operating company's details; override per deployment.
    legal_contact_email: str = "info@mldynamic.com"
    # Grievance Officer mailbox shown on the privacy policy (DPDP Act). Empty hides the line.
    legal_grievance_email: str = "rishi@mldynamic.com"
    legal_operator_name: str = "M L Dynamic Solutions Private Limited"
    # Registered office, as published on mldynamic.com/privacy.html.
    legal_postal_address: str = (
        "606, 6th Floor, Gowra Fountainhead, Patrika Nagar, Madhapur, "
        "Hi-Tech City, Hyderabad, Telangana - 500081, India"
    )

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
    _warn_on_placeholder_legal_details(s)


_PLACEHOLDER_LEGAL_EMAIL = "dpo@sangamitra.in"


def _warn_on_placeholder_legal_details(s: Settings) -> None:
    """Warn, but do not refuse to boot, on settings that are fine for testing but not for launch.

    Covers placeholder legal details, canned AI replies and sandbox purchases.

    Play and the DPDP Act expect a monitored grievance contact. A missing
    mailbox should not take the API down, so this is a loud log line only.
    """
    import logging

    log = logging.getLogger(__name__)
    if s.legal_contact_email.strip().lower() == _PLACEHOLDER_LEGAL_EMAIL:
        log.warning(
            "LEGAL_CONTACT_EMAIL is still the placeholder %s; set a monitored mailbox "
            "before the privacy policy is shown on Google Play",
            _PLACEHOLDER_LEGAL_EMAIL,
        )
    if not (s.sarvam_api_key or "").strip():
        log.warning(
            "SARVAM_API_KEY is not set; voice agents answer with canned fixture replies, "
            "not real speech or language models"
        )
    if not (s.sarvam_samvaad_api_key or "").strip():
        log.warning(
            "SARVAM_SAMVAAD_API_KEY is not set; /voice-agents calls and sessions return canned fixtures"
        )
    elif not ((s.samvaad_org_id or "").strip() and (s.samvaad_workspace_id or "").strip()):
        log.warning(
            "SARVAM_SAMVAAD_API_KEY is set but SAMVAAD_ORG_ID or SAMVAAD_WORKSPACE_ID is missing; "
            "/voice-agents answers 503 until both are set"
        )
    if s.revenuecat_accept_sandbox:
        log.warning(
            "REVENUECAT_ACCEPT_SANDBOX is on; Play license-tester purchases credit real wallets. "
            "Turn it off before the public launch"
        )
    if not s.firebase_require_verified_email and (s.firebase_project_id or "").strip():
        log.warning("FIREBASE_REQUIRE_VERIFIED_EMAIL is off; unverified email accounts can sign in")
    if not s.legal_postal_address.strip():
        log.warning("LEGAL_POSTAL_ADDRESS is empty; the public legal pages show no postal address")
