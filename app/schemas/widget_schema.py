from pydantic import BaseModel, Field


class WidgetSessionRequest(BaseModel):
    # Public identifier from the embed snippet's data-site-key attribute.
    site_key: str = Field(min_length=1, max_length=64)
    # Anonymous ID the widget keeps in the browser so question limits apply
    # per visitor across page loads. Missing/invalid = a new one is issued.
    visitor_id: str | None = Field(default=None, max_length=256)


class InvalidateSiteRequest(BaseModel):
    site_key: str = Field(min_length=1, max_length=64)
