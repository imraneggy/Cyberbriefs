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
- Hashtags must include a mix of cybersecurity, scam awareness, privacy, and tech tags.

CRITICAL — image_prompt rules:
The image_prompt is fed DIRECTLY into a text-to-image model (FLUX/SDXL). It must be a
visual description, NOT a list of design rules. It MUST mention the topic so the
model knows what to draw. Examples of GOOD image_prompts for "{topic.topic}":
  "Flat-design Instagram infographic about {topic.topic}. Navy blue and teal palette,
   white background. Central illustration: <topic-specific visual metaphor, e.g.
   padlock with binary code / phishing hook on email envelope>. 3 supporting icons
   labelled '<step1>', '<step2>', '<step3>'. Bold title text at top: '<short title>'.
   Brand mark bottom-right. No photoreal people. Clean isometric style."
Examples of BAD image_prompts (DO NOT produce these):
  "Create a polished modern infographic." (no topic, no visual)
  "An infographic explaining ransomware." (too vague)

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


class OllamaTextClient(_BaseChatClient):
    """Local Ollama — 100% private, zero cost, fully offline.

    Talks to Ollama's OpenAI-compatible endpoint at /v1/chat/completions.
    Default base URL is http://localhost:11434 — override via OLLAMA_BASE_URL
    if Ollama runs on another host or port.

    Default model: cyberbriefs:latest (custom model created from local/cyberbriefs.Modelfile)
    Fallback chain if the custom model is not installed: qwen3:8b → phi4-mini

    The custom Modelfile bakes the cybersecurity-editor system prompt and
    sample outputs into the model so each call needs only the topic — this
    is the "training" step (technically a prompt-baked Ollama model, not a
    LoRA fine-tune, but it gives deterministic style at zero training cost).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "cyberbriefs:latest",
        timeout: float = 600.0,
    ) -> None:
        # 600s tolerates cold-load of a 5GB model on CPU. Real warm calls
        # complete in 20-60s; the timeout only matters for the first cron
        # firing after a system restart.
        self.model = model
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout)

    def generate_post_copy(self, *, topic: TopicCandidate, slot: str, brand_name: str) -> GeneratedPost:
        prompt = _post_prompt(topic, slot, brand_name)
        # /no_think suppresses qwen3's reasoning trace so the full token budget
        # goes to the JSON answer. Harmless on phi4-mini and llama variants.
        user_prompt = f"{prompt}\n\n/no_think"
        resp = self._client.post(
            "/v1/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a cybersecurity infographic editor. "
                            "Output a single valid JSON object only, no preamble, no reasoning."
                        ),
                    },
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.6,
                "response_format": {"type": "json_object"},
                "stream": False,
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Ollama call failed ({resp.status_code}): {resp.text[:300]} — "
                f"check Ollama is running and model '{self.model}' is installed "
                f"(run `ollama list`; create with local/cyberbriefs.Modelfile)"
            )
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


class RecraftImageClient:
    """Recraft v3 — purpose-built for readable in-image text + vector-quality
    illustration. 50 images/day on the free tier. Best free choice for
    infographic posts where the headline must be readable.

    Free tier: 50 credits/day; each image = 1 credit (default size).
    Sign up at https://www.recraft.ai/ → Settings → API → create token.
    Set RECRAFT_API_KEY env var.

    Default style 'digital_illustration' gives the clean flat-design look
    that Instagram cybersecurity posts use. Other free styles:
      - 'digital_illustration' (default, clean flat)
      - 'vector_illustration' (SVG-like)
      - 'realistic_image' (photoreal)
      - 'icon' (simple icon set)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "recraftv3",
        style: str = "digital_illustration",
        substyle: str | None = None,
        size: str = "1024x1024",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.style = style
        self.substyle = substyle
        self.size = size
        self._client = httpx.Client(
            base_url="https://external.api.recraft.ai/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=180,
        )

    def generate_image(self, prompt: str) -> bytes:
        # Recraft API: POST /images/generations returns a URL; we then GET the image.
        payload: dict[str, Any] = {
            "prompt": prompt[:1000],
            "style": self.style,
            "model": self.model,
            "size": self.size,
            "n": 1,
            "response_format": "url",
        }
        if self.substyle:
            payload["substyle"] = self.substyle
        resp = self._client.post("/images/generations", json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"Recraft generation failed ({resp.status_code}): {resp.text[:200]}")
        data = resp.json()
        url = data["data"][0]["url"]
        img_resp = httpx.get(url, timeout=60)
        img_resp.raise_for_status()
        return img_resp.content


class GeminiImageClient:
    """Google Gemini API native image generation — free tier on AI Studio.

    Free tier: ~1500 requests/day, 15 RPM, no credit card.
    Sign up at https://aistudio.google.com/ → 'Get API Key' (Google login).
    Set GEMINI_API_KEY env var.

    Default model: gemini-2.5-flash-image  (Google's "Nano Banana"; native infographic-friendly)
      Other valid choices (subject to availability — query ListModels for current set):
        gemini-3-pro-image-preview
        gemini-3.1-flash-image-preview
      Older names like 'gemini-2.0-flash-preview-image-generation' are now 404.

    Image-gen via Gemini works by asking for both Text and Image modalities,
    then extracting the inline base64-encoded image from the response. The
    model accepts a long-form prompt and returns a 1024×1024 (or similar)
    image. Decent text rendering — better than FLUX, not as polished as
    DALL-E 3 or Imagen 3.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash-image",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self._client = httpx.Client(
            base_url="https://generativelanguage.googleapis.com/v1beta",
            timeout=180,
        )

    def generate_image(self, prompt: str) -> bytes:
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt[:2000]}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "temperature": 0.4,
            },
        }
        resp = self._client.post(
            f"/models/{self.model}:generateContent",
            params={"key": self.api_key},
            json=body,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Gemini image gen failed ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        # Walk candidates → content.parts to find an inline_data part with image bytes
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    import base64
                    return base64.b64decode(inline["data"])
        raise RuntimeError(
            f"Gemini returned no image part. Response keys: {list(data.keys())}; "
            f"first 200 chars: {str(data)[:200]}"
        )


class NvidiaImageClient:
    """NVIDIA NIM / build.nvidia.com hosted FLUX.1 family + others.

    Free credits on signup (typically 1000+), then paid. Useful when you want
    higher-quality FLUX variants (flux.1-dev, flux.1-schnell, flux.1.1-pro-ultra)
    or NVIDIA-specific models.

    Sign up at https://build.nvidia.com/ → personal API key.
    Set NVIDIA_API_KEY env var.

    Default model 'black-forest-labs/flux.1-schnell' is the fastest free FLUX.
    For higher quality try 'black-forest-labs/flux.1-dev' (slower).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "black-forest-labs/flux.1-schnell",
        width: int = 1024,
        height: int = 1024,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.width = width
        self.height = height
        self._client = httpx.Client(
            base_url="https://ai.api.nvidia.com/v1",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=180,
        )

    def generate_image(self, prompt: str) -> bytes:
        payload = {
            "prompt": prompt[:1500],
            "width": self.width,
            "height": self.height,
            "steps": 4,
            "seed": int(time.time()) % 2_000_000_000,
        }
        resp = self._client.post(f"/genai/{self.model}", json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"NVIDIA NIM failed ({resp.status_code}): {resp.text[:200]}")
        data = resp.json()
        # NIM returns either base64 in "artifacts" or a URL — handle both
        if "artifacts" in data and data["artifacts"]:
            import base64
            return base64.b64decode(data["artifacts"][0]["base64"])
        if "image" in data:
            import base64
            return base64.b64decode(data["image"])
        raise RuntimeError(f"NVIDIA NIM unexpected response shape: {list(data.keys())}")


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
    if provider == "ollama":
        return OllamaTextClient(
            base_url=env_get("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=env_get("OLLAMA_MODEL", "cyberbriefs:latest"),
        )
    raise ValueError(f"Unknown free text provider: {provider}")


class PromptOnlyImageClient:
    """Sentinel — does NOT generate an image. Signals the generator that the
    user wants prompt-only delivery: the LLM-produced image_prompt is sent
    verbatim via Telegram for the user to paste into their own image tool.

    Required for the "Flow A" prompt-only drafting mode where the system
    drafts the post text + image prompt and the user handles image gen +
    Instagram posting manually.
    """

    is_prompt_only = True  # sentinel flag the generator checks for

    def generate_image(self, prompt: str) -> bytes:  # pragma: no cover — defensive
        raise RuntimeError(
            "PromptOnlyImageClient.generate_image() should never be called. "
            "The generator must short-circuit when image_provider == 'prompt_only'."
        )


def build_image_client(provider: str, env_get=os.environ.get):
    """Construct an image client based on provider name. Returns object with
    ``generate_image(prompt)`` method.
    """
    provider = provider.lower()
    if provider == "prompt_only":
        return PromptOnlyImageClient()
    if provider == "composite":
        # Composite = AI background + PIL text overlay = readable text always.
        # The base provider is configurable; defaults to pollinations (free, no card).
        from cyberbriefs.composite_image import CompositeImageClient
        base_name = env_get("COMPOSITE_BASE_PROVIDER", "pollinations").lower()
        # Recurse into this factory to build the base (must not be 'composite')
        if base_name == "composite":
            raise ValueError("COMPOSITE_BASE_PROVIDER cannot itself be 'composite'")
        base = build_image_client(base_name, env_get)
        return CompositeImageClient(
            base_provider=base,
            header_color=env_get("COMPOSITE_HEADER_COLOR", "#0F3D5C"),
            accent_color=env_get("COMPOSITE_ACCENT_COLOR", "#14B8A6"),
            text_color=env_get("COMPOSITE_TEXT_COLOR", "#FFFFFF"),
            brand_text=env_get("COMPOSITE_BRAND_TEXT", "CYBERBRIEFS DAILY"),
            font_path=env_get("COMPOSITE_FONT") or None,
        )
    if provider == "gemini":
        api_key = env_get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("gemini image provider needs GEMINI_API_KEY (free at aistudio.google.com)")
        return GeminiImageClient(
            api_key=api_key,
            model=env_get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"),
        )
    if provider == "recraft":
        api_key = env_get("RECRAFT_API_KEY")
        if not api_key:
            raise RuntimeError("recraft image provider needs RECRAFT_API_KEY (free signup at recraft.ai)")
        return RecraftImageClient(
            api_key=api_key,
            model=env_get("RECRAFT_MODEL", "recraftv3"),
            style=env_get("RECRAFT_STYLE", "digital_illustration"),
            substyle=env_get("RECRAFT_SUBSTYLE") or None,
        )
    if provider == "nvidia":
        api_key = env_get("NVIDIA_API_KEY")
        if not api_key:
            raise RuntimeError("nvidia image provider needs NVIDIA_API_KEY (free signup at build.nvidia.com)")
        return NvidiaImageClient(
            api_key=api_key,
            model=env_get("NVIDIA_MODEL", "black-forest-labs/flux.1-schnell"),
        )
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
