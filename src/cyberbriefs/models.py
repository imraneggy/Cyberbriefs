from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl


PostStatus = Literal[
    "draft",
    "pending_approval",
    "approved",
    "rejected",
    "published",
    "expired",
    "failed",
]


class Source(BaseModel):
    title: str
    url: HttpUrl
    publisher: str | None = None


class GeneratedPost(BaseModel):
    post_id: str = Field(default_factory=lambda: uuid4().hex)
    status: PostStatus = "draft"
    topic: str
    slot: str
    headline: str
    image_prompt: str
    image_alt_text: str
    caption: str
    hashtags: list[str]
    sources: list[Source] = Field(default_factory=list)
    r2_object_key: str | None = None
    r2_image_url: str | None = None
    # Carousel support: when len(image_urls) > 1, this is an IG carousel post.
    # image_urls[0] mirrors r2_image_url (the cover slide), so single-image
    # downstream code keeps working. The Cloudflare Worker uses image_urls
    # to publish carousels via the IG Graph API CAROUSEL_ALBUM flow.
    image_urls: list[str] = Field(default_factory=list)
    # Per-slide titles for carousels (empty list for single posts). 1:1
    # indexed with image_urls.
    slide_titles: list[str] = Field(default_factory=list)
    telegram_message_id: int | None = None
    instagram_media_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None
    published_at: datetime | None = None
    error_log: str | None = None

    @property
    def is_carousel(self) -> bool:
        return len(self.image_urls) > 1

    def caption_for_instagram(self) -> str:
        """Build a copy-paste-ready Instagram caption.

        Hashtags are joined with a leading '#' on each so the post is
        actually discoverable (without the '#', Instagram treats them as
        plain words and the post does not surface in tag feeds).

        Disclaimer + source lines are opt-in via env to keep the default
        output casual and IG-shareable. Many users post these manually
        and don't want a corporate-sounding footer baked in.
        """
        import os
        tags = " ".join(f"#{h.lstrip('#')}" for h in self.hashtags if h)
        # Disclaimer / sources default OFF (set to "1" to include).
        include_disclaimer = os.getenv("CYBERBRIEFS_INCLUDE_DISCLAIMER", "0") == "1"
        include_sources = os.getenv("CYBERBRIEFS_INCLUDE_SOURCES", "0") == "1"
        source_line = ""
        if include_sources and self.sources:
            publishers = [s.publisher or str(s.url.host or "source") for s in self.sources[:3]]
            source_line = "\n\nSources: " + ", ".join(dict.fromkeys(publishers))
        disclaimer = (
            "\n\nEducational content only. Verify critical security decisions with official advisories."
            if include_disclaimer else ""
        )
        return f"{self.caption.strip()}{source_line}{disclaimer}\n\n{tags}".strip()


class TopicCandidate(BaseModel):
    topic: str
    angle: str
    sources: list[Source] = Field(default_factory=list)
