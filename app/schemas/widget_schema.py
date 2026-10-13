from pydantic import BaseModel, Field


class WidgetSessionRequest(BaseModel):
    # Public identifier from the embed snippet's data-site-key attribute.
    site_key: str = Field(min_length=1, max_length=64)


class InvalidateSiteRequest(BaseModel):
    site_key: str = Field(min_length=1, max_length=64)
