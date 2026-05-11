from __future__ import annotations

import httpx

from cyberbriefs.models import GeneratedPost


class TelegramClient:
    def __init__(self, bot_token: str, admin_chat_id: str) -> None:
        self.admin_chat_id = admin_chat_id
        self._client = httpx.Client(
            base_url=f"https://api.telegram.org/bot{bot_token}",
            timeout=60,
        )

    def send_approval_request(self, post: GeneratedPost) -> int:
        if not post.r2_image_url:
            raise RuntimeError("Cannot send approval without r2_image_url")
        text = (
            f"<b>{post.headline}</b>\n\n"
            f"{_telegram_escape(post.caption_for_instagram())}\n\n"
            f"<b>Post ID:</b> <code>{post.post_id}</code>"
        )
        response = self._client.post(
            "/sendPhoto",
            json={
                "chat_id": self.admin_chat_id,
                "photo": post.r2_image_url,
                "caption": text[:1024],
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {"text": "Approve", "callback_data": f"approve:{post.post_id}"},
                            {"text": "Reject", "callback_data": f"reject:{post.post_id}"},
                        ],
                        [
                            {
                                "text": "Regenerate caption",
                                "callback_data": f"regenerate_caption:{post.post_id}",
                            },
                            {
                                "text": "Regenerate image",
                                "callback_data": f"regenerate_image:{post.post_id}",
                            },
                        ],
                    ]
                },
            },
        )
        response.raise_for_status()
        return int(response.json()["result"]["message_id"])


def _telegram_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
