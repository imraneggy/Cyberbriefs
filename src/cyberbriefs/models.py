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
    telegram_message_id: int | None = None
    instagram_media_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None
    published_at: datetime | None = None
    error_log: str | None = None

    def caption_for_instagram(self) -> str:
        tags = " ".join(self.hashtags)
        source_line = ""
        if self.sources:
            publishers = [s.publisher or str(s.url.host or "source") for s in self.sources[:3]]
            source_line = "\n\nSources: " + ", ".join(dict.fromkeys(publishers))
        disclaimer = "\n\nEducational content only. Verify critical security decisions with official advisories."
        return f"{self.caption.strip()}{source_line}{disclaimer}\n\n{tags}".strip()


class TopicCandidate(BaseModel):
    topic: str
    angle: str
    sources: list[Source] = Field(default_factory=list)
