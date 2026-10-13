from pydantic import BaseModel, HttpUrl, Field
from app.config.settings import settings

# session_id is accepted for backward compatibility but ignored: the chat
# session always comes from the verified widget token.

class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1, max_length=settings.WIDGET_MAX_MESSAGE_CHARS)

class ContactUsRequest(BaseModel):
    session_id: str | None = None
    name: str
    email: str
    country_code: str
    contact: str

class ExtractWebsiteDataRequest(BaseModel):
    url: HttpUrl
    # Name used for the storage folder and the Qdrant collection.
    # Defaults to a slug derived from the URL's domain (e.g. "companiesnext").
    website: str | None = None
    # Homepage + same-domain pages discovered from it, capped at this count.
    max_pages: int = Field(default=30, ge=1, le=200)