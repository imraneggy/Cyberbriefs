from __future__ import annotations

import json
import re

import httpx

from cyberbriefs.config import Settings
from cyberbriefs.free_client import (
    POST_SCHEMA,
    build_image_client,
    build_text_client,
)
from cyberbriefs.github_storage import GitHubImageStorage
from cyberbriefs.models import GeneratedPost, Source
from cyberbriefs.openai_client import OpenAIClient
from cyberbriefs.r2 import R2Client
from cyberbriefs.telegram import TelegramClient
from cyberbriefs.test_content import generate_test_image_svg, generate_test_post
from cyberbriefs.topics import choose_topic


FREE_TEXT_PROVIDERS = {"github_models", "groq", "huggingface"}
FREE_IMAGE_PROVIDERS = {"composite", "recraft", "nvidia", "pollinations", "huggingface", "cloudflare"}


def _enrich_image_prompt(raw_prompt: str, topic: str) -> str:
    """Defensive wrapper. If the LLM produced a topic-less or too-short image
    prompt (e.g. "create a polished infographic"), prepend the topic and a
    proven visual style so the image model has enough to draw on.

    Defense-in-depth — the LLM prompt already asks for topic-rich image
    prompts, but small free-tier models sometimes ignore that guidance.
    """
    p = (raw_prompt or "").strip()
    topic_lower = (topic or "").lower()
    # If the prompt already mentions the topic substantively, leave it alone
    if topic_lower and any(
        kw in p.lower() for kw in topic_lower.split() if len(kw) > 4
    ):
        return p
    # Otherwise, prepend a topic-anchored visual brief
    return (
        f"Flat-design Instagram infographic about: {topic}. "
        f"Navy blue and teal color palette on white background. "
        f"Strong title text at the top, 2-3 supporting icons with short labels. "
        f"Clean isometric style, no photoreal people, no fake logos. "
        f"Square 1024x1024. "
        f"{p}"
    ).strip()


class PostGenerator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.openai = self._build_openai(settings)
        self.free_text = self._build_free_text(settings)
        self.free_image = self._build_free_image(settings)
        self.image_storage = self._build_image_storage(settings)
        self.telegram = TelegramClient(
            bot_token=settings.telegram_bot_token,
            admin_chat_id=settings.telegram_admin_chat_id,
        )
        self._worker = httpx.Client(base_url=settings.worker_base_url, timeout=60)

    def run(self, *, slot: str) -> GeneratedPost:
        topic = choose_topic(slot)
        slides = max(1, min(10, self.settings.carousel_slides))

        # 1. Generate post copy and image bytes for each slide
        if self.settings.content_provider == "test":
            post = generate_test_post(
                topic=topic, slot=slot, brand_name=self.settings.brand_name
            )
            slide_images = [(generate_test_image_svg(headline=post.headline), "svg+xml")]
            slide_titles: list[str] = []
        elif self.settings.content_provider == "openai":
            if not self.openai:
                raise RuntimeError("OpenAI content provider requires OPENAI_API_KEY")
            post = self.openai.generate_post_copy(
                topic=topic, slot=slot, brand_name=self.settings.brand_name
            )
            slide_titles = []
            if slides > 1:
                # OpenAI carousel: ask for distinct slide prompts
                slide_prompts, slide_titles = self._openai_carousel_prompts(
                    post=post, slides=slides, slot=slot, topic_str=topic.topic
                )
                slide_images = [
                    (self.openai.generate_image(p), self.settings.openai_image_output_format)
                    for p in slide_prompts
                ]
            else:
                slide_images = [(
                    self.openai.generate_image(post.image_prompt),
                    self.settings.openai_image_output_format,
                )]
        elif self.settings.content_provider in FREE_TEXT_PROVIDERS:
            if not self.free_text:
                raise RuntimeError(f"Free text provider {self.settings.content_provider} not initialised")
            if not self.free_image:
                raise RuntimeError(f"Free image provider {self.settings.image_provider} not initialised")
            post = self.free_text.generate_post_copy(
                topic=topic, slot=slot, brand_name=self.settings.brand_name
            )
            slide_titles = []
            if slides > 1:
                # Free carousel: build per-slide prompts by varying the base prompt
                slide_prompts, slide_titles = self._free_carousel_prompts(
                    post=post, slides=slides
                )
                slide_images = [
                    (self.free_image.generate_image(_enrich_image_prompt(p, topic.topic)), "jpeg")
                    for p in slide_prompts
                ]
            else:
                enriched = _enrich_image_prompt(post.image_prompt, topic.topic)
                slide_images = [(self.free_image.generate_image(enriched), "jpeg")]
        else:
            raise RuntimeError(f"Unknown content_provider: {self.settings.content_provider}")

        # 2. Upload each slide and collect URLs
        image_urls: list[str] = []
        object_keys: list[str] = []
        for idx, (img_bytes, img_format) in enumerate(slide_images):
            object_key, image_url = self.image_storage.upload_image(
                post_id=f"{post.post_id}_{idx}" if len(slide_images) > 1 else post.post_id,
                image_bytes=img_bytes,
                image_format=img_format,
            )
            object_keys.append(object_key)
            image_urls.append(image_url)

        # 3. Wire into model. r2_image_url stays = cover (first slide) for
        # backward compatibility with single-post code paths.
        post.r2_object_key = object_keys[0]
        post.r2_image_url = image_urls[0]
        post.image_urls = image_urls
        post.slide_titles = slide_titles
        post.status = "pending_approval"

        # 4. Register with Worker + send Telegram approval
        self._register_post(post)
        post.telegram_message_id = self.telegram.send_approval_request(post)
        self._register_post(post)
        return post

    # ── carousel helpers ────────────────────────────────────────────────

    def _openai_carousel_prompts(
        self, *, post: GeneratedPost, slides: int, slot: str, topic_str: str
    ) -> tuple[list[str], list[str]]:
        """Ask OpenAI for {slides} distinct image prompts derived from the
        post's headline + caption. Returns (image_prompts, slide_titles)."""
        if not self.openai:
            raise RuntimeError("openai not available for carousel")
        ask = (
            f"For an Instagram carousel about '{topic_str}', return JSON: "
            f'{{"slides":[{{"title":"...","image_prompt":"..."}},...{slides} items]}}. '
            f"Maintain consistent palette across slides. Each prompt should describe "
            f"a polished infographic panel with clean icons, no fake logos."
        )
        # Reuse OpenAI's chat to enumerate the panels
        resp = self.openai._post_with_retries(  # noqa: SLF001 — controlled internal reuse
            "/responses",
            {
                "model": self.openai.text_model,
                "input": [
                    {"role": "system", "content": "Return JSON only."},
                    {"role": "user", "content": ask},
                ],
            },
            operation="generate carousel prompts",
        )
        data = resp.json()
        raw = _extract_openai_responses_text(data)
        parsed = _extract_first_json(raw)
        slide_objs = parsed.get("slides", [])[:slides]
        if not slide_objs:
            # Fallback: derive {slides} prompts mechanically from the base prompt
            return self._free_carousel_prompts(post=post, slides=slides)
        prompts = [str(s.get("image_prompt") or post.image_prompt) for s in slide_objs]
        titles = [str(s.get("title") or f"Slide {i+1}") for i, s in enumerate(slide_objs)]
        return prompts, titles

    def _free_carousel_prompts(
        self, *, post: GeneratedPost, slides: int
    ) -> tuple[list[str], list[str]]:
        """Mechanical fallback: derive N slide prompts from one base prompt.
        Adds slide context (1/N, 2/N...) and panel role so images differ
        meaningfully even without a planning LLM call."""
        roles = [
            "(Slide 1: Hook — bold title only, large readable text)",
            "(Slide 2: What is this? — illustrated definition)",
            "(Slide 3: How it works — 2-3 step diagram)",
            "(Slide 4: Red flags — bullet-list panel with icons)",
            "(Slide 5: Defense steps — checklist panel)",
            "(Slide 6: Example — labelled annotated screenshot mockup)",
            "(Slide 7: Comparison — before vs after panel)",
            "(Slide 8: Quick stats — large number callouts)",
            "(Slide 9: Reminder — single key takeaway, bold)",
            "(Slide 10: Call to action — follow for daily security)",
        ]
        prompts = []
        titles = []
        for i in range(slides):
            role = roles[i] if i < len(roles) else f"(Slide {i+1})"
            prompts.append(f"{post.image_prompt}\n{role}")
            titles.append(f"Slide {i+1}")
        return prompts, titles

    def _register_post(self, post: GeneratedPost) -> None:
        response = self._worker.post(
            "/api/posts",
            headers={"X-CyberBriefs-Secret": self.settings.worker_shared_secret},
            json=post.model_dump(mode="json"),
        )
        response.raise_for_status()

    @staticmethod
    def _build_openai(settings: Settings) -> OpenAIClient | None:
        if settings.content_provider != "openai":
            return None
        if not settings.openai_api_key:
            raise RuntimeError("OpenAI content provider requires OPENAI_API_KEY")
        return OpenAIClient(
            api_key=settings.openai_api_key,
            text_model=settings.openai_text_model,
            image_model=settings.openai_image_model,
            image_quality=settings.openai_image_quality,
            image_size=settings.openai_image_size,
            image_output_format=settings.openai_image_output_format,
        )

    @staticmethod
    def _build_free_text(settings: Settings):
        if settings.content_provider not in FREE_TEXT_PROVIDERS:
            return None
        return build_text_client(settings.content_provider)

    @staticmethod
    def _build_free_image(settings: Settings):
        if settings.content_provider not in FREE_TEXT_PROVIDERS:
            return None
        if settings.image_provider not in FREE_IMAGE_PROVIDERS:
            raise RuntimeError(
                f"image_provider must be one of {FREE_IMAGE_PROVIDERS} when "
                f"content_provider is free, got {settings.image_provider!r}"
            )
        return build_image_client(settings.image_provider)

    @staticmethod
    def _build_image_storage(settings: Settings) -> GitHubImageStorage | R2Client:
        if settings.image_storage_backend == "github":
            if not settings.github_repository or not settings.github_token:
                raise RuntimeError("GitHub image storage requires GITHUB_REPOSITORY and GITHUB_TOKEN")
            return GitHubImageStorage(
                repository=settings.github_repository,
                token=settings.github_token,
                branch=settings.github_image_branch,
                path_prefix=settings.github_image_path_prefix,
                public_base_url=settings.github_image_public_base_url,
            )

        if settings.image_storage_backend == "r2":
            if not all(
                [
                    settings.cloudflare_account_id,
                    settings.r2_access_key_id,
                    settings.r2_secret_access_key,
                    settings.r2_bucket,
                    settings.r2_public_base_url,
                ]
            ):
                raise RuntimeError("R2 image storage is missing required Cloudflare R2 settings")
            return R2Client(
                account_id=settings.cloudflare_account_id,
                access_key_id=settings.r2_access_key_id,
                secret_access_key=settings.r2_secret_access_key,
                bucket=settings.r2_bucket,
                public_base_url=settings.r2_public_base_url,
            )

        raise RuntimeError(f"Unsupported IMAGE_STORAGE_BACKEND: {settings.image_storage_backend}")


# ── small helpers reused by carousel-prompt extraction ────────────────────

def _extract_openai_responses_text(data: dict) -> str:
    """Pull the assistant text out of OpenAI /v1/responses output."""
    try:
        # New responses API: output[0].content[0].text
        return data["output"][0]["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        # Fallback shapes
        return data.get("output_text") or json.dumps(data)


def _extract_first_json(raw: str) -> dict:
    if not raw:
        return {}
    text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    text = re.sub(r"\s*```\s*$", "", text)
    start = text.find("{")
    if start < 0:
        return {}
    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except Exception:
                    return {}
    return {}
