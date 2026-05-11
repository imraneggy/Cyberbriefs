from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _optional(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_text_model: str
    openai_image_model: str
    openai_image_quality: str
    openai_image_size: str
    openai_image_output_format: str
    telegram_bot_token: str
    telegram_admin_chat_id: str
    cloudflare_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket: str
    r2_public_base_url: str
    worker_base_url: str
    worker_shared_secret: str
    timezone: str = "Asia/Dubai"
    brand_name: str = "CyberBriefsDaily"
    site_url: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            openai_api_key=_required("OPENAI_API_KEY"),
            openai_text_model=_optional("OPENAI_TEXT_MODEL", "gpt-4.1-mini"),
            openai_image_model=_optional("OPENAI_IMAGE_MODEL", "gpt-image-2"),
            openai_image_quality=_optional("OPENAI_IMAGE_QUALITY", "low"),
            openai_image_size=_optional("OPENAI_IMAGE_SIZE", "1024x1024"),
            openai_image_output_format=_optional("OPENAI_IMAGE_OUTPUT_FORMAT", "jpeg"),
            telegram_bot_token=_required("TELEGRAM_BOT_TOKEN"),
            telegram_admin_chat_id=_required("TELEGRAM_ADMIN_CHAT_ID"),
            cloudflare_account_id=_required("CLOUDFLARE_ACCOUNT_ID"),
            r2_access_key_id=_required("CLOUDFLARE_R2_ACCESS_KEY_ID"),
            r2_secret_access_key=_required("CLOUDFLARE_R2_SECRET_ACCESS_KEY"),
            r2_bucket=_required("CLOUDFLARE_R2_BUCKET"),
            r2_public_base_url=_required("CLOUDFLARE_R2_PUBLIC_BASE_URL").rstrip("/"),
            worker_base_url=_required("WORKER_BASE_URL").rstrip("/"),
            worker_shared_secret=_required("WORKER_SHARED_SECRET"),
            timezone=_optional("CYBERBRIEFS_TIMEZONE", "Asia/Dubai"),
            brand_name=_optional("CYBERBRIEFS_BRAND_NAME", "CyberBriefsDaily"),
            site_url=os.getenv("CYBERBRIEFS_SITE_URL") or None,
        )
