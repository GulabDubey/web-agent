from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    QDRANT_HOST: str
    QDRANT_PORT: int

    QDRANT_COLLECTION: str

    VOYAGE_API_KEY: str
    HF_TOKEN: str

settings = Settings()
