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

    def send_draft_only(self, post: GeneratedPost) -> int:
        """Send a text-only draft for the prompt-only flow.

        Posts ONE Telegram message containing three copy-paste blocks: the
        image prompt (for the user's image tool), the Instagram caption,
        and the hashtags. No photo attachment, no approve/reject buttons —
        the user handles image gen and IG posting manually.

        Each block is in <pre><code> so Telegram renders a tap-to-copy
        affordance on mobile.
        """
        cap_for_ig = post.caption_for_instagram()
        # Telegram sendMessage caps at 4096 chars; squeeze if needed.
        text = (
            f"<b>{_telegram_escape(post.headline)}</b>\n"
            f"<i>{_telegram_escape(post.topic)}</i>\n\n"
            f"<b>IMAGE PROMPT</b> — paste into ChatGPT / Gemini / Midjourney:\n"
            f"<pre><code>{_telegram_escape(post.image_prompt)}</code></pre>\n"
            f"<b>INSTAGRAM CAPTION</b> — paste into the IG post:\n"
            f"<pre><code>{_telegram_escape(cap_for_ig)}</code></pre>\n"
            f"<b>POST ID:</b> <code>{post.post_id}</code>"
        )
        if len(text) > 4090:
            text = text[:4080] + "\n…(truncated)"
        response = self._client.post(
            "/sendMessage",
            json={
                "chat_id": self.admin_chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
        response.raise_for_status()
        return int(response.json()["result"]["message_id"])

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
