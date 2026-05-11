from __future__ import annotations

import base64
import json
import time
from typing import Any

import httpx

from cyberbriefs.models import GeneratedPost, Source, TopicCandidate


class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        text_model: str,
        image_model: str,
        image_quality: str,
        image_size: str,
        image_output_format: str,
    ) -> None:
        self.api_key = api_key
        self.text_model = text_model
        self.image_model = image_model
        self.image_quality = image_quality
        self.image_size = image_size
        self.image_output_format = image_output_format
        self._client = httpx.Client(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120,
        )

    def generate_post_copy(
        self,
        *,
        topic: TopicCandidate,
        slot: str,
        brand_name: str,
    ) -> GeneratedPost:
        schema = {
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
        prompt = f"""
Create one Instagram cybersecurity infographic draft for {brand_name}.

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
Return JSON only.
""".strip()
        payload: dict[str, Any] = {
            "model": self.text_model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert cybersecurity editor and infographic art director. "
                        "You produce accurate educational content and avoid unsupported claims."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "cyberbriefs_post",
                    "schema": schema,
                    "strict": True,
                }
            },
        }
        response = self._post_with_retries("/responses", payload, operation="generate post copy")
        data = response.json()
        raw_text = _extract_response_text(data)
        parsed = json.loads(raw_text)
        return GeneratedPost(
            topic=topic.topic,
            slot=slot,
            headline=parsed["headline"],
            caption=parsed["caption"],
            hashtags=[_normalise_hashtag(tag) for tag in parsed["hashtags"]],
            image_prompt=parsed["image_prompt"],
            image_alt_text=parsed["image_alt_text"],
            sources=[Source.model_validate(source) for source in topic.sources],
        )

    def generate_image(self, prompt: str) -> bytes:
        payload = {
            "model": self.image_model,
            "prompt": prompt,
            "size": self.image_size,
            "quality": self.image_quality,
            "output_format": self.image_output_format,
            "n": 1,
        }
        response = self._post_with_retries("/images/generations", payload, operation="generate image")
        data = response.json()
        b64_json = data["data"][0]["b64_json"]
        return base64.b64decode(b64_json)

    def _post_with_retries(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        operation: str,
        max_attempts: int = 4,
    ) -> httpx.Response:
        for attempt in range(1, max_attempts + 1):
            response = self._client.post(path, json=payload)
            if response.status_code < 400:
                return response

            retryable = response.status_code in {408, 409, 429, 500, 502, 503, 504}
            if retryable and attempt < max_attempts:
                retry_after = _retry_after_seconds(response)
                delay = retry_after if retry_after is not None else min(2 ** attempt, 30)
                print(
                    f"OpenAI {operation} failed with HTTP {response.status_code}; "
                    f"retrying in {delay}s (attempt {attempt}/{max_attempts})."
                )
                time.sleep(delay)
                continue

            message = _openai_error_message(response)
            raise RuntimeError(
                f"OpenAI {operation} failed with HTTP {response.status_code}: {message}"
            )

        raise RuntimeError(f"OpenAI {operation} failed after {max_attempts} attempts")


def _extract_response_text(data: dict[str, Any]) -> str:
    if "output_text" in data:
        return data["output_text"]
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return content["text"]
    raise RuntimeError("OpenAI response did not include text output")


def _normalise_hashtag(tag: str) -> str:
    clean = tag.strip()
    if not clean:
        return "#CyberSecurity"
    if not clean.startswith("#"):
        clean = f"#{clean}"
    return clean.replace(" ", "")


def _retry_after_seconds(response: httpx.Response) -> int | None:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(1, min(int(value), 60))
    except ValueError:
        return None


def _openai_error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:1000]

    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        parts = [
            str(error.get("message") or "").strip(),
            f"type={error.get('type')}" if error.get("type") else "",
            f"code={error.get('code')}" if error.get("code") else "",
        ]
        return " | ".join(part for part in parts if part)
    return json.dumps(body)[:1000]
