"""Content generation schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class ContentGenerateRequest(BaseModel):
    """Content generation request."""

    location_id: UUID
    theme: str = Field(description="Content theme, e.g., 'fall-hydration', 'holiday-special'")
    services: list[str] | None = None
    tone: str = Field(default="expert yet friendly")
    language: str = Field(default="en")
    platform_targets: list[str] = Field(default=["GBP", "INSTAGRAM", "WEBSITE"])
    audience: str | None = None
    promo: str | None = None


class GBPContent(BaseModel):
    """Generated GBP content."""

    title: str = Field(max_length=58)
    body: str = Field(min_length=300, max_length=700)
    cta: str | None = None
    offer: str | None = None
    hashtags: list[str] = Field(max_length=6)


class InstagramContent(BaseModel):
    """Generated Instagram content."""

    caption: str = Field(min_length=700, max_length=1500)
    hashtags: list[str] = Field(min_length=15, max_length=25)


class WebContent(BaseModel):
    """Generated website/blog content."""

    title: str
    markdown: str
    meta_description: str | None = None
    internal_links: list[str] | None = None


class GeneratedContent(BaseModel):
    """Complete generated content response."""

    gbp: GBPContent | None = None
    instagram: InstagramContent | None = None
    web: WebContent | None = None
    image_prompt: str | None = None


class ContentGenerateResponse(BaseModel):
    """Content generation response."""

    location_id: UUID
    theme: str
    content: GeneratedContent
    posts_created: int = 0
