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


settings = Settings()
