from __future__ import annotations

import httpx

from cyberbriefs.config import Settings
from cyberbriefs.models import GeneratedPost
from cyberbriefs.openai_client import OpenAIClient
from cyberbriefs.r2 import R2Client
from cyberbriefs.telegram import TelegramClient
from cyberbriefs.topics import choose_topic


class PostGenerator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.openai = OpenAIClient(
            api_key=settings.openai_api_key,
            text_model=settings.openai_text_model,
            image_model=settings.openai_image_model,
            image_quality=settings.openai_image_quality,
            image_size=settings.openai_image_size,
            image_output_format=settings.openai_image_output_format,
        )
        self.r2 = R2Client(
            account_id=settings.cloudflare_account_id,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket=settings.r2_bucket,
            public_base_url=settings.r2_public_base_url,
        )
        self.telegram = TelegramClient(
            bot_token=settings.telegram_bot_token,
            admin_chat_id=settings.telegram_admin_chat_id,
        )
        self._worker = httpx.Client(base_url=settings.worker_base_url, timeout=60)

    def run(self, *, slot: str) -> GeneratedPost:
        topic = choose_topic(slot)
        post = self.openai.generate_post_copy(
            topic=topic,
            slot=slot,
            brand_name=self.settings.brand_name,
        )
        image_bytes = self.openai.generate_image(post.image_prompt)
        object_key, image_url = self.r2.upload_image(
            post_id=post.post_id,
            image_bytes=image_bytes,
            image_format=self.settings.openai_image_output_format,
        )
        post.r2_object_key = object_key
        post.r2_image_url = image_url
        post.status = "pending_approval"
        self._register_post(post)
        post.telegram_message_id = self.telegram.send_approval_request(post)
        self._register_post(post)
        return post

    def _register_post(self, post: GeneratedPost) -> None:
        response = self._worker.post(
            "/api/posts",
            headers={"X-CyberBriefs-Secret": self.settings.worker_shared_secret},
            json=post.model_dump(mode="json"),
        )
        response.raise_for_status()
