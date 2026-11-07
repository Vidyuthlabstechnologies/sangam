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

    zitadel_domain: Optional[str] = None
    zitadel_client_id: Optional[str] = None
    zitadel_client_secret: Optional[str] = None

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

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

_MIN_SECRET_LENGTH = 32


def validate_production_settings(s: Settings) -> None:
    """Refuse to start in production with settings that make it forgeable.

    The default JWT secret is in source control, so anyone who has read the
    repo could mint a valid token for any actor. Fixture mode returns canned
    payment and AI responses. Neither may ever run as "production".
    """
    if s.environment.strip().lower() != "production":
        return

    problems = []
    secret = s.jwt_secret or ""
    if secret.upper().startswith("CHANGE-ME") or len(secret) < _MIN_SECRET_LENGTH:
        problems.append(f"JWT_SECRET must be a random value of at least {_MIN_SECRET_LENGTH} characters")
    if s.use_fixtures:
        problems.append("USE_FIXTURES must be false")
    if s.debug:
        problems.append("DEBUG must be false")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))
