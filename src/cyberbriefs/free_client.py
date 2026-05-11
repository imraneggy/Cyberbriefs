"""Zero-cost text + image generation adapters.

Drop-in alternatives to ``OpenAIClient`` that use free or no-credit-card
services. Selected via the ``CONTENT_PROVIDER`` env var:

  CONTENT_PROVIDER=github_models   # uses GitHub Models (free in Actions)
  CONTENT_PROVIDER=groq            # uses Groq's free tier
  CONTENT_PROVIDER=huggingface     # uses Hugging Face Inference API
  CONTENT_PROVIDER=pollinations    # text via Pollinations + image via Pollinations

Image provider is selected by ``IMAGE_PROVIDER`` (default: pollinations):
  IMAGE_PROVIDER=pollinations      # truly free, no API key
  IMAGE_PROVIDER=huggingface       # FLUX.1-schnell on HF Inference API
  IMAGE_PROVIDER=cloudflare        # Workers AI SDXL Lightning (10k req/day)

Each adapter exposes the same surface as ``OpenAIClient``:
  - ``generate_post_copy(...)`` -> ``GeneratedPost``
  - ``generate_image(prompt: str)`` -> ``bytes``

For carousel posts (slides > 1), generators return a list of image bytes.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
from typing import Any

import httpx

from cyberbriefs.models import GeneratedPost, Source, TopicCandidate


# Reusable JSON schema for post copy — same shape across all providers so
# downstream code is provider-agnostic.
POST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["headline", "caption", "hashtags", "image_prompt", "image_alt_text"],
    "properties": {
        "headline": {"type": "string"},
        "caption": {"type": "string"},
        "hashtags": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 8,
            "maxItems": 15,
        },
        "image_prompt": {"type": "string"},
        "image_alt_text": {"type": "string"},
    },
}


def _post_prompt(topic: TopicCandidate, slot: str, brand_name: str) -> str:
    """Single prompt format reused across providers for output consistency."""
    return f"""Create one Instagram cybersecurity infographic draft for {brand_name}.

Topic: {topic.topic}
Angle: {topic.angle}
Slot: {slot}

Requirements:
- Single square infographic, not a carousel.
- Clear, factual, non-alarmist.
- Audience: founders, IT admins, students, and everyday users.
- Caption should use short paragraphs and scannable bullets.
- Include practical defense steps.
- Do not invent specific breach claims, victim names, dates, CVEs, or statistics.
- Image prompt must ask for a polished modern infographic with strong hierarchy,
  clean icons, no fake logos, no tiny unreadable text, and no photorealistic people.
- Hashtags must include a mix of cybersecurity, scam awareness, privacy, and tech tags.

Return ONLY a JSON object matching this schema:
{json.dumps(POST_SCHEMA, indent=2)}

No prose before or after the JSON. No markdown fences. Just the JSON object.""".strip()


def _carousel_prompt(topic: TopicCandidate, slot: str, brand_name: str, slides: int) -> str:
    """Carousel variant — asks for {slides} distinct panels with their own image prompts."""
    return f"""Create an Instagram cybersecurity CAROUSEL ({slides} slides) for {brand_name}.

Topic: {topic.topic}
Angle: {topic.angle}
Slot: {slot}

Each slide must be a self-contained panel that flows logically into the next.
Suggested structure for {slides}-slide carousels:
  Slide 1: The hook — "What is X?" or "The new threat"
  Middle slides: How it works / red flags / examples
  Final slide: Defense steps + call-to-follow

Return ONLY a JSON object:
{{
  "headline": "<carousel title (≤60 chars)>",
  "caption": "<single caption that summarizes the whole carousel, scannable bullets>",
  "hashtags": ["..."] (8-15 hashtags),
  "image_alt_text": "<one alt-text describing the carousel overall>",
  "slides": [
    {{"slide_title": "...", "image_prompt": "..."}},
    {{"slide_title": "...", "image_prompt": "..."}},
    ... ({slides} total)
  ]
}}

Each image_prompt must describe a polished modern infographic panel — strong
hierarchy, clean icons, no fake logos, no tiny unreadable text, no photoreal
people. Maintain visual consistency across slides (same color palette).
No prose before/after the JSON. No markdown fences.""".strip()


# ── TEXT PROVIDERS ────────────────────────────────────────────────────────

class _BaseChatClient:
    """Common JSON-extraction logic — accepts text from any chat API."""

    @staticmethod
    def _extract_json_object(raw: str) -> dict[str, Any]:
        """Find the first balanced {...} block in raw output and parse it.

        Tolerant of preamble, code fences, and trailing prose since not every
        free-tier model honors JSON-mode instructions strictly.
        """
        if not raw:
            raise ValueError("Empty LLM output")
        text = raw.strip()
        # Strip code fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
        # Strip <think> blocks (Qwen3-style reasoners)
        text = re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", text, flags=re.DOTALL | re.IGNORECASE)
        # Find first balanced object — naive but works for our schema depth
        start = text.find("{")
        if start < 0:
            raise ValueError(f"No JSON object found in output: {text[:120]!r}")
        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : i + 1])
        raise ValueError(f"Unbalanced JSON in output: {text[start : start + 200]!r}")

    def _build_post(
        self,
        data: dict[str, Any],
        topic: TopicCandidate,
        slot: str,
    ) -> GeneratedPost:
        return GeneratedPost(
            topic=topic.topic,
            slot=slot,
            headline=str(data["headline"]),
            image_prompt=str(data.get("image_prompt", "")),
            image_alt_text=str(data.get("image_alt_text", "")),
            caption=str(data["caption"]),
            hashtags=[str(h).strip().lstrip("#") for h in data.get("hashtags", []) if h],
            sources=list(topic.sources),
        )


class GitHubModelsClient(_BaseChatClient):
    """Free in GitHub Actions — uses the GITHUB_TOKEN automatically.

    Endpoint: https://models.github.ai/inference/chat/completions
    Default model: openai/gpt-4o-mini (free preview).
    """

    def __init__(self, token: str, model: str = "openai/gpt-4o-mini") -> None:
        self.token = token
        self.model = model
        self._client = httpx.Client(
            base_url="https://models.github.ai",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=120,
        )

    def generate_post_copy(self, *, topic: TopicCandidate, slot: str, brand_name: str) -> GeneratedPost:
        prompt = _post_prompt(topic, slot, brand_name)
        resp = self._client.post(
            "/inference/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a cybersecurity infographic editor. Output only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        return self._build_post(self._extract_json_object(raw), topic, slot)


class GroqClient(_BaseChatClient):
    """Groq free tier — 30 req/min, OpenAI-compatible API."""

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile") -> None:
        self.api_key = api_key
        self.model = model
        self._client = httpx.Client(
            base_url="https://api.groq.com/openai/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120,
        )

    def generate_post_copy(self, *, topic: TopicCandidate, slot: str, brand_name: str) -> GeneratedPost:
        prompt = _post_prompt(topic, slot, brand_name)
        resp = self._client.post(
            "/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a cybersecurity infographic editor. Output only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        return self._build_post(self._extract_json_object(raw), topic, slot)


class HuggingFaceTextClient(_BaseChatClient):
    """Hugging Face Inference API — free tier, ~100k tokens/day on common models."""

    def __init__(self, api_key: str, model: str = "meta-llama/Llama-3.1-8B-Instruct") -> None:
        self.api_key = api_key
        self.model = model
        self._client = httpx.Client(
            base_url=f"https://api-inference.huggingface.co/models/{model}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120,
        )

    def generate_post_copy(self, *, topic: TopicCandidate, slot: str, brand_name: str) -> GeneratedPost:
        prompt = _post_prompt(topic, slot, brand_name)
        resp = self._client.post(
            "",
            json={
                "inputs": prompt,
                "parameters": {"max_new_tokens": 600, "temperature": 0.7, "return_full_text": False},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data[0]["generated_text"] if isinstance(data, list) else data.get("generated_text", "")
        return self._build_post(self._extract_json_object(raw), topic, slot)


# ── IMAGE PROVIDERS ───────────────────────────────────────────────────────

class PollinationsImageClient:
    """Pollinations.ai — truly free, no API key, no rate limit (within reason).

    Just an HTTP GET against a URL-encoded prompt. Backed by FLUX/SDXL.
    """

    def __init__(self, model: str = "flux", width: int = 1024, height: int = 1024) -> None:
        self.model = model
        self.width = width
        self.height = height
        # nologo=true removes the small watermark; seed=- gives random output each call
        self._client = httpx.Client(timeout=120, follow_redirects=True)

    def generate_image(self, prompt: str) -> bytes:
        encoded = urllib.parse.quote(prompt[:1900], safe="")
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?model={self.model}&width={self.width}&height={self.height}&nologo=true"
        )
        # Pollinations sometimes returns 502 under load — retry with backoff
        for attempt in range(4):
            try:
                resp = self._client.get(url)
                if resp.status_code == 200 and resp.content:
                    return resp.content
            except httpx.HTTPError:
                pass
            time.sleep(2 ** attempt)
        raise RuntimeError(f"Pollinations failed after 4 attempts for prompt: {prompt[:80]!r}")


class HuggingFaceImageClient:
    """Hugging Face Inference API for image gen — FLUX.1-schnell by default."""

    def __init__(self, api_key: str, model: str = "black-forest-labs/FLUX.1-schnell") -> None:
        self.api_key = api_key
        self.model = model
        self._client = httpx.Client(
            base_url=f"https://api-inference.huggingface.co/models/{model}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=300,
        )

    def generate_image(self, prompt: str) -> bytes:
        resp = self._client.post(
            "",
            json={"inputs": prompt[:1900], "parameters": {"width": 1024, "height": 1024}},
        )
        resp.raise_for_status()
        return resp.content


class CloudflareImageClient:
    """Cloudflare Workers AI SDXL Lightning — 10k requests/day free."""

    def __init__(self, account_id: str, api_token: str, model: str = "@cf/bytedance/stable-diffusion-xl-lightning") -> None:
        self.account_id = account_id
        self.api_token = api_token
        self.model = model
        self._client = httpx.Client(
            base_url=f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run",
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=120,
        )

    def generate_image(self, prompt: str) -> bytes:
        resp = self._client.post(
            f"/{self.model}",
            json={"prompt": prompt[:1900], "width": 1024, "height": 1024, "num_steps": 4},
        )
        resp.raise_for_status()
        return resp.content


# ── FACTORIES ─────────────────────────────────────────────────────────────

def build_text_client(provider: str, env_get=os.environ.get):
    """Construct a text client based on provider name. Returns object with
    ``generate_post_copy`` method. Raises if required env vars are missing.
    """
    provider = provider.lower()
    if provider == "github_models":
        token = env_get("GITHUB_TOKEN") or env_get("CYBERBRIEFS_GITHUB_TOKEN")
        if not token:
            raise RuntimeError("github_models text provider needs GITHUB_TOKEN env var")
        return GitHubModelsClient(token=token, model=env_get("GITHUB_MODELS_MODEL", "openai/gpt-4o-mini"))
    if provider == "groq":
        api_key = env_get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("groq text provider needs GROQ_API_KEY env var")
        return GroqClient(api_key=api_key, model=env_get("GROQ_MODEL", "llama-3.3-70b-versatile"))
    if provider == "huggingface":
        api_key = env_get("HUGGINGFACE_API_KEY")
        if not api_key:
            raise RuntimeError("huggingface text provider needs HUGGINGFACE_API_KEY env var")
        return HuggingFaceTextClient(api_key=api_key, model=env_get("HUGGINGFACE_TEXT_MODEL", "meta-llama/Llama-3.1-8B-Instruct"))
    raise ValueError(f"Unknown free text provider: {provider}")


def build_image_client(provider: str, env_get=os.environ.get):
    """Construct an image client based on provider name. Returns object with
    ``generate_image(prompt)`` method.
    """
    provider = provider.lower()
    if provider == "pollinations":
        return PollinationsImageClient(model=env_get("POLLINATIONS_MODEL", "flux"))
    if provider == "huggingface":
        api_key = env_get("HUGGINGFACE_API_KEY")
        if not api_key:
            raise RuntimeError("huggingface image provider needs HUGGINGFACE_API_KEY env var")
        return HuggingFaceImageClient(api_key=api_key, model=env_get("HUGGINGFACE_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell"))
    if provider == "cloudflare":
        account_id = env_get("CLOUDFLARE_ACCOUNT_ID")
        api_token = env_get("CLOUDFLARE_API_TOKEN")
        if not (account_id and api_token):
            raise RuntimeError("cloudflare image provider needs CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN env vars")
        return CloudflareImageClient(account_id=account_id, api_token=api_token)
    raise ValueError(f"Unknown free image provider: {provider}")
