"""Local dry-run that simulates the full pipeline without touching any
external service except the (free, no-auth) Pollinations image generator.

Outputs:
  - The post object that would be POSTed to the Cloudflare Worker
  - The exact Telegram approval message body that would be sent
  - The generated image saved to /tmp/cyberbriefs_dryrun.jpg

Run:
  CONTENT_PROVIDER=test IMAGE_PROVIDER=pollinations python scripts/dry_run_telegram.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cyberbriefs.free_client import PollinationsImageClient
from cyberbriefs.models import GeneratedPost
from cyberbriefs.test_content import generate_test_post
from cyberbriefs.topics import choose_topic


def build_telegram_message(post: GeneratedPost) -> dict:
    """Mirror the message body that telegram.py would build.

    The Telegram approval message includes:
      - Headline + topic + slot
      - Image (cover slide for carousels)
      - Approve / Reject inline-keyboard buttons
      - Image alt text + caption preview
    """
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Approve & publish", "callback_data": f"approve:{post.post_id}"},
            {"text": "❌ Reject", "callback_data": f"reject:{post.post_id}"},
        ]]
    }
    text = (
        f"<b>{post.headline}</b>\n\n"
        f"<i>Topic:</i> {post.topic}\n"
        f"<i>Slot:</i> {post.slot}\n"
        f"<i>Carousel:</i> {len(post.image_urls) if post.is_carousel else 'No (single image)'}\n\n"
        f"<b>Caption preview:</b>\n{post.caption[:400]}{'...' if len(post.caption) > 400 else ''}\n\n"
        f"<b>Hashtags ({len(post.hashtags)}):</b> {' '.join('#' + h.lstrip('#') for h in post.hashtags[:8])}{'...' if len(post.hashtags) > 8 else ''}\n\n"
        f"<i>Alt text:</i> {post.image_alt_text}"
    )
    return {
        "method": "sendPhoto",
        "chat_id": "<YOUR_TELEGRAM_ADMIN_CHAT_ID>",
        "photo": post.r2_image_url or post.image_urls[0],
        "caption": text,
        "parse_mode": "HTML",
        "reply_markup": keyboard,
    }


def main() -> int:
    slot = os.getenv("SLOT", "morning")
    print(f"\n{'=' * 70}\nCyberBriefs DRY RUN — slot={slot}\n{'=' * 70}\n")

    # 1. Pick today's topic
    topic = choose_topic(slot)
    print(f"📌 Today's topic ({slot}):")
    print(f"   {topic.topic}")
    print(f"   Angle: {topic.angle}\n")

    # 2. Generate post copy (test mode = canned but realistic)
    post = generate_test_post(topic=topic, slot=slot, brand_name="CyberBriefsDaily")
    print(f"📝 Post copy generated:")
    print(f"   Headline: {post.headline}")
    print(f"   Caption: {post.caption[:200]}...")
    print(f"   {len(post.hashtags)} hashtags\n")

    # 3. Generate image via Pollinations (free, no API key)
    print(f"🎨 Generating image via Pollinations.ai (free)...")
    try:
        client = PollinationsImageClient(model="flux", width=1024, height=1024)
        image_bytes = client.generate_image(post.image_prompt)
        out_path = Path("/tmp/cyberbriefs_dryrun.jpg")
        out_path.write_bytes(image_bytes)
        print(f"   Image generated: {len(image_bytes):,} bytes")
        print(f"   Saved to: {out_path}\n")
    except Exception as exc:
        print(f"   [WARN] Pollinations failed: {exc}")
        print(f"   (Skipping image, using placeholder URL)\n")
        image_bytes = b""
        out_path = None

    # 4. Build the final post object (what would be POSTed to the Worker)
    post.r2_image_url = f"https://raw.githubusercontent.com/imraneggy/Cyberbriefs/main/public/posts/{post.post_id}.jpg"
    post.image_urls = [post.r2_image_url]
    post.status = "pending_approval"

    print(f"📦 Post object (what gets stored in Cloudflare KV):")
    pretty = post.model_dump(mode="json")
    print(json.dumps(pretty, indent=2, default=str)[:2000])
    print()

    # 5. Build the Telegram message that would be sent
    tg = build_telegram_message(post)
    print(f"{'=' * 70}")
    print(f"📱 TELEGRAM MESSAGE THAT WOULD BE SENT")
    print(f"{'=' * 70}")
    print(f"POST https://api.telegram.org/bot<TOKEN>/sendPhoto")
    print(f"chat_id: {tg['chat_id']}")
    print(f"photo URL: {tg['photo']}")
    print(f"caption (HTML):")
    print()
    print(tg["caption"])
    print()
    print(f"Inline keyboard:")
    for row in tg["reply_markup"]["inline_keyboard"]:
        for btn in row:
            print(f"  [{btn['text']}]  -> callback: {btn['callback_data']}")
    print(f"{'=' * 70}\n")

    # 6. Caption that would land on Instagram if approved
    print(f"📷 INSTAGRAM CAPTION (after approval):\n{'─' * 70}")
    print(post.caption_for_instagram())
    print(f"{'─' * 70}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
