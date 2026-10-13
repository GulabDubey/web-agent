from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # pydantic-settings reads the .env file itself (no need for
    # `python-dotenv`/`load_dotenv()` anywhere in application code).
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App server (run.py) ---------------------------------------------
    APP_ENV: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # --- Anthropic LLM (app/llm/anthropic.py) ------------------------------
    ANTHROPIC_API_KEY: str
    ANTHROPIC_MODEL: str = "claude-sonnet-4"

    # --- MySQL database (app/config/database.py) --------------------------
    DB_HOST: str
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # --- Redis (app/config/redis.py) ---------------------------------------
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # --- Qdrant vector store (app/core/qdrant.py) ---------------------------
    QDRANT_HOST: str
    QDRANT_PORT: int
    QDRANT_COLLECTION: str

    # --- Embeddings (app/services/embedding_service.py) --------------------
    VOYAGE_API_KEY: str
    HF_TOKEN: str

    # --- Django subscription verification (app/services/subscription_service.py)
    # Server-to-server only; DJANGO_SERVICE_API_KEY must match one of the
    # Django project's CHATBOT_SERVICE_TOKENS and never reaches the browser.
    DJANGO_SUBSCRIPTION_VERIFY_URL: str = ""
    DJANGO_SERVICE_API_KEY: str = ""
    DJANGO_VERIFY_TIMEOUT_SECONDS: float = 5.0
    # After this many failed calls within a minute, stop calling Django for
    # DJANGO_VERIFY_COOLDOWN_SECONDS (requests fail closed with 503 meanwhile).
    DJANGO_VERIFY_FAILURE_THRESHOLD: int = 5
    DJANGO_VERIFY_COOLDOWN_SECONDS: int = 30

    # --- Django database, read-only (app/services/site_collection_service.py)
    # Each chat reads websites_website.collection_name for the verified site.
    # Host/user/password/port default to this app's DB_* values.
    DJANGO_DB_NAME: str = "django_app"
    DJANGO_DB_HOST: str = ""
    DJANGO_DB_PORT: int = 3306
    DJANGO_DB_USER: str = ""
    DJANGO_DB_PASSWORD: str = ""

    # --- Widget access tokens (app/services/widget_token_service.py) --------
    WIDGET_JWT_SECRET: str = ""
    WIDGET_TOKEN_TTL_SECONDS: int = 600
    # An expired token can still be exchanged for a new one (same chat
    # session) within this window; the subscription is re-verified first.
    WIDGET_TOKEN_REFRESH_GRACE_SECONDS: int = 1800
    WIDGET_TOKEN_AUDIENCE: str = "chatbot-widget"
    WIDGET_TOKEN_ISSUER: str = "web-agent"

    # --- Widget authorization (app/core/widget_auth.py) ---------------------
    # How long a Django "authorized" answer is reused before re-verifying,
    # and how long a denial is remembered.
    WIDGET_AUTH_CACHE_TTL_SECONDS: int = 60
    WIDGET_DENY_CACHE_TTL_SECONDS: int = 30
    # Optional extra allowlist of domains (comma-separated, e.g.
    # "example.com,shop.example.org"). Empty = rely on Django's registered domain.
    WIDGET_ALLOWED_ORIGINS: str = ""
    # Development only (ignored unless APP_ENV=development). Local origins
    # (localhost/127.0.0.1/[::1]) are verified with Django as their own
    # "host:port", e.g. "127.0.0.1:8012" - register that in Django's admin.
    # Set this to make every local origin act as a registered public domain
    # instead (e.g. "companiesnext.com").
    WIDGET_DEV_DOMAIN: str = ""
    WIDGET_MAX_MESSAGE_CHARS: int = 2000

    # --- Rate limits & usage (per minute unless noted) ----------------------
    RATE_LIMIT_INVALID_KEY_PER_IP: int = 10  # per 10 minutes
    RATE_LIMIT_SESSIONS_PER_IP: int = 20
    RATE_LIMIT_SESSIONS_PER_SITE: int = 300
    RATE_LIMIT_CHAT_PER_SESSION: int = 15
    RATE_LIMIT_CHAT_PER_IP: int = 40
    RATE_LIMIT_CHAT_PER_SITE: int = 300
    WIDGET_MAX_CONCURRENT_PER_SITE: int = 10
    # LLM tokens per site per UTC day; 0 disables the cap.
    WIDGET_DAILY_TOKEN_LIMIT_PER_SITE: int = 1_000_000

    # --- Internal service endpoints (crawl/ingest/users) --------------------
    # Comma-separated bearer tokens; the Django CRAWLER_API_TOKEN must be one.
    INTERNAL_SERVICE_TOKENS: str = ""

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @staticmethod
    def _split(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def internal_service_tokens(self) -> list[str]:
        return self._split(self.INTERNAL_SERVICE_TOKENS)

    @property
    def widget_allowed_origins(self) -> list[str]:
        return self._split(self.WIDGET_ALLOWED_ORIGINS)


settings = Settings()
