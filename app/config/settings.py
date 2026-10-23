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

    # --- Qdrant vector store (app/core/qdrant.py) ---------------------------
    # Qdrant Cloud: set QDRANT_URL (https://...) and QDRANT_API_KEY.
    # Self-hosted: leave QDRANT_URL empty and use QDRANT_HOST/QDRANT_PORT.
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str

    # --- Embeddings (app/services/embedding_service.py) --------------------
    # Changing the model or dimension means rebuilding every Qdrant collection.
    VOYAGE_API_KEY: str
    VOYAGE_MODEL: str = "voyage-3.5"
    EMBEDDING_DIMENSION: int = 1024

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

    # --- Per-website LLM provider (app/services/llm_config_service.py) ------
    # Django's POST /api/internal/chatbot/llm-config/ (same service key).
    # Empty = derived from DJANGO_SUBSCRIPTION_VERIFY_URL.
    DJANGO_LLM_CONFIG_URL: str = ""
    # Seconds a site's provider/model/key is reused before asking Django again
    # (kept in process memory only - API keys never go to Redis).
    LLM_CONFIG_CACHE_TTL_SECONDS: int = 60

    # --- Per-visitor question limit (app/services/question_limit_service.py)
    # Django's questions/consume/ and questions/refund/ endpoints (same service
    # key). Empty = derived from DJANGO_SUBSCRIPTION_VERIFY_URL. The limit
    # itself is set per website in the Django admin.
    DJANGO_QUESTIONS_URL: str = ""

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
    def questions_url(self) -> str:
        """Base URL ending in "/questions/"; consume/ and refund/ are appended."""
        if self.DJANGO_QUESTIONS_URL:
            return self.DJANGO_QUESTIONS_URL.rstrip("/") + "/"
        if self.DJANGO_SUBSCRIPTION_VERIFY_URL.endswith("/verify-subscription/"):
            return self.DJANGO_SUBSCRIPTION_VERIFY_URL[: -len("verify-subscription/")] + "questions/"
        return ""

    @property
    def llm_config_url(self) -> str:
        if self.DJANGO_LLM_CONFIG_URL:
            return self.DJANGO_LLM_CONFIG_URL
        if self.DJANGO_SUBSCRIPTION_VERIFY_URL.endswith("/verify-subscription/"):
            return self.DJANGO_SUBSCRIPTION_VERIFY_URL[: -len("verify-subscription/")] + "llm-config/"
        return ""

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
