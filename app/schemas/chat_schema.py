from pydantic import BaseModel, HttpUrl, Field

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ContactUsRequest(BaseModel):
    session_id: str
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