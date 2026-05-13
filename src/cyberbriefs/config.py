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
    openai_api_key: str | None
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
    content_provider: str
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
    # Carousel — number of slides when content_provider supports it.
    # 1 = single image (default, IG single post). 2-10 = carousel.
    carousel_slides: int = 1
    # Free-stack image provider used when content_provider is a free option
    # (github_models / groq / huggingface / pollinations). One of:
    #   pollinations | huggingface | cloudflare
    image_provider: str = "pollinations"

    @classmethod
    def from_env(cls) -> "Settings":
        content_provider = _optional("CONTENT_PROVIDER", "openai").lower()
        image_storage_backend = _optional("IMAGE_STORAGE_BACKEND", "github").lower()
        image_provider = _optional("IMAGE_PROVIDER", "pollinations").lower()
        # In prompt-only mode we never store an image or publish via Worker,
        # so the GitHub-storage credentials become optional. The cron only
        # needs Telegram + a text LLM (Ollama is free, GitHub Models too).
        prompt_only = image_provider == "prompt_only"
        github_repository = _optional_none("GITHUB_REPOSITORY")
        github_token = _optional_none("CYBERBRIEFS_GITHUB_TOKEN") or _optional_none("GITHUB_TOKEN")

        if content_provider == "openai" and not _optional_none("OPENAI_API_KEY"):
            raise RuntimeError("Missing required environment variable: OPENAI_API_KEY")
        # Free providers each have their own credential check inside free_client.
        # We deliberately do NOT require any LLM key when content_provider == "test".
        if content_provider == "github_models":
            # GitHub Actions provides GITHUB_TOKEN automatically.
            if not (_optional_none("GITHUB_TOKEN") or _optional_none("CYBERBRIEFS_GITHUB_TOKEN")):
                raise RuntimeError("github_models provider needs GITHUB_TOKEN (auto in Actions, or set locally)")
        if content_provider == "groq" and not _optional_none("GROQ_API_KEY"):
            raise RuntimeError("groq provider needs GROQ_API_KEY")
        if content_provider == "huggingface" and not _optional_none("HUGGINGFACE_API_KEY"):
            raise RuntimeError("huggingface provider needs HUGGINGFACE_API_KEY")
        # ollama needs no API key — Ollama runs locally on the host and is
        # reached via http://localhost:11434. We don't pre-check connectivity
        # here; the client surfaces a clear error if Ollama isn't running.

        if image_storage_backend == "github" and not prompt_only:
            if not github_repository:
                raise RuntimeError("Missing required environment variable for GitHub storage: GITHUB_REPOSITORY")
            if not github_token:
                raise RuntimeError(
                    "Missing required environment variable for GitHub storage: CYBERBRIEFS_GITHUB_TOKEN"
                )

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
            openai_api_key=_optional_none("OPENAI_API_KEY"),
            openai_text_model=_optional("OPENAI_TEXT_MODEL", "gpt-4.1-mini"),
            openai_image_model=_optional("OPENAI_IMAGE_MODEL", "gpt-image-2"),
            openai_image_quality=_optional("OPENAI_IMAGE_QUALITY", "low"),
            openai_image_size=_optional("OPENAI_IMAGE_SIZE", "1024x1024"),
            openai_image_output_format=_optional("OPENAI_IMAGE_OUTPUT_FORMAT", "jpeg"),
            telegram_bot_token=_required("TELEGRAM_BOT_TOKEN"),
            telegram_admin_chat_id=_required("TELEGRAM_ADMIN_CHAT_ID"),
            # Worker is only needed for the auto-publish flow. In prompt-only
            # mode there is no publish step, so accept empty values.
            worker_base_url=(_optional("WORKER_BASE_URL", "") if prompt_only else _required("WORKER_BASE_URL")).rstrip("/"),
            worker_shared_secret=(_optional("WORKER_SHARED_SECRET", "") if prompt_only else _required("WORKER_SHARED_SECRET")),
            image_storage_backend=image_storage_backend,
            content_provider=content_provider,
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
            carousel_slides=max(1, min(10, int(_optional("CAROUSEL_SLIDES", "1")))),
            image_provider=image_provider,
        )
