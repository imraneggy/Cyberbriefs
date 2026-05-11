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


def _optional_none(name: str) -> str | None:
    value = os.getenv(name)
    return value if value else None


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
    worker_base_url: str
    worker_shared_secret: str
    image_storage_backend: str
    github_repository: str | None = None
    github_token: str | None = None
    github_image_branch: str = "main"
    github_image_path_prefix: str = "public/posts"
    github_image_public_base_url: str | None = None
    cloudflare_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str | None = None
    r2_public_base_url: str | None = None
    timezone: str = "Asia/Dubai"
    brand_name: str = "CyberBriefsDaily"
    site_url: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        image_storage_backend = _optional("IMAGE_STORAGE_BACKEND", "github").lower()
        github_repository = _optional_none("GITHUB_REPOSITORY")
        github_token = _optional_none("GITHUB_TOKEN")

        if image_storage_backend == "github":
            if not github_repository:
                raise RuntimeError("Missing required environment variable for GitHub storage: GITHUB_REPOSITORY")
            if not github_token:
                raise RuntimeError("Missing required environment variable for GitHub storage: GITHUB_TOKEN")

        cloudflare_account_id = _optional_none("CLOUDFLARE_ACCOUNT_ID")
        r2_access_key_id = _optional_none("CLOUDFLARE_R2_ACCESS_KEY_ID")
        r2_secret_access_key = _optional_none("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
        r2_bucket = _optional_none("CLOUDFLARE_R2_BUCKET")
        r2_public_base_url = _optional_none("CLOUDFLARE_R2_PUBLIC_BASE_URL")

        if image_storage_backend == "r2":
            required_r2 = {
                "CLOUDFLARE_ACCOUNT_ID": cloudflare_account_id,
                "CLOUDFLARE_R2_ACCESS_KEY_ID": r2_access_key_id,
                "CLOUDFLARE_R2_SECRET_ACCESS_KEY": r2_secret_access_key,
                "CLOUDFLARE_R2_BUCKET": r2_bucket,
                "CLOUDFLARE_R2_PUBLIC_BASE_URL": r2_public_base_url,
            }
            for name, value in required_r2.items():
                if not value:
                    raise RuntimeError(f"Missing required environment variable for R2 storage: {name}")

        return cls(
            openai_api_key=_required("OPENAI_API_KEY"),
            openai_text_model=_optional("OPENAI_TEXT_MODEL", "gpt-4.1-mini"),
            openai_image_model=_optional("OPENAI_IMAGE_MODEL", "gpt-image-2"),
            openai_image_quality=_optional("OPENAI_IMAGE_QUALITY", "low"),
            openai_image_size=_optional("OPENAI_IMAGE_SIZE", "1024x1024"),
            openai_image_output_format=_optional("OPENAI_IMAGE_OUTPUT_FORMAT", "jpeg"),
            telegram_bot_token=_required("TELEGRAM_BOT_TOKEN"),
            telegram_admin_chat_id=_required("TELEGRAM_ADMIN_CHAT_ID"),
            worker_base_url=_required("WORKER_BASE_URL").rstrip("/"),
            worker_shared_secret=_required("WORKER_SHARED_SECRET"),
            image_storage_backend=image_storage_backend,
            github_repository=github_repository,
            github_token=github_token,
            github_image_branch=_optional("GITHUB_IMAGE_BRANCH", "main"),
            github_image_path_prefix=_optional("GITHUB_IMAGE_PATH_PREFIX", "public/posts"),
            github_image_public_base_url=_optional_none("GITHUB_IMAGE_PUBLIC_BASE_URL"),
            cloudflare_account_id=cloudflare_account_id,
            r2_access_key_id=r2_access_key_id,
            r2_secret_access_key=r2_secret_access_key,
            r2_bucket=r2_bucket,
            r2_public_base_url=r2_public_base_url.rstrip("/") if r2_public_base_url else None,
            timezone=_optional("CYBERBRIEFS_TIMEZONE", "Asia/Dubai"),
            brand_name=_optional("CYBERBRIEFS_BRAND_NAME", "CyberBriefsDaily"),
            site_url=os.getenv("CYBERBRIEFS_SITE_URL") or None,
        )
