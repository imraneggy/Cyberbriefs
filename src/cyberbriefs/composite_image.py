"""Composite image provider — AI-generated background + PIL text overlay.

Why this exists: diffusion models (FLUX/SDXL) cannot reliably render
readable text. Composite mode sidesteps the problem entirely:

  1. Get an abstract visual background from a base image provider
     (Pollinations by default — truly free, no API key, no card)
     prompted to produce NO text, just visual style.
  2. Overlay the actual headline + brand mark with PIL using a real
     TrueType font. Real fonts mean perfectly readable text every time.

The result looks like a professional Canva template: AI-quality visual
backing + crisp typographic content.

Configuration via env vars:
  COMPOSITE_BASE_PROVIDER   pollinations | huggingface | cloudflare  (default: pollinations)
  COMPOSITE_HEADER_COLOR    hex like '#0F3D5C'  (navy band at top, default)
  COMPOSITE_TEXT_COLOR      hex for headline text  (default: white)
  COMPOSITE_BRAND_COLOR     hex for brand mark band  (default: teal)
  COMPOSITE_FONT            path to .ttf to use for headline  (default: bundled DejaVuSans-Bold)
  COMPOSITE_BRAND_TEXT      bottom-right brand text  (default: CYBERBRIEFS DAILY)
"""
from __future__ import annotations

import io
import os
import textwrap
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw, ImageFilter, ImageFont


# Font search order:
#   1. COMPOSITE_FONT env var (absolute path)
#   2. Pillow's bundled DejaVuSans
#   3. Common Linux/Windows system fonts
_FONT_CANDIDATES = [
    # Pillow bundles DejaVuSans in some builds — try those first
    "DejaVuSans-Bold.ttf",
    "DejaVuSans.ttf",
    # Linux (GH Actions ubuntu-latest)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    # macOS
    "/System/Library/Fonts/Helvetica.ttc",
    # Windows
    "C:/Windows/Fonts/Arial.ttf",
    "C:/Windows/Fonts/Verdana.ttf",
]


def _load_font(size: int, override_path: str | None = None) -> ImageFont.FreeTypeFont:
    """Resolve a TrueType font, falling back through candidates.

    Returns Pillow's default bitmap font only as a last resort (worst case).
    """
    if override_path and Path(override_path).is_file():
        return ImageFont.truetype(override_path, size=size)
    for candidate in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size=size)
        except (OSError, FileNotFoundError):
            continue
    # Last resort — built-in bitmap font (not great but works)
    return ImageFont.load_default()


class _BaseProvider(Protocol):
    def generate_image(self, prompt: str) -> bytes: ...


class CompositeImageClient:
    """AI background + PIL text overlay = perfectly readable infographic text.

    Workflow per generate_image() call:
      1. Build a "visual only" prompt (strips text instructions, requests
         an abstract security-themed background pattern).
      2. Get base bytes from the configured base provider.
      3. Composite the navy header bar + headline + brand mark on top.
      4. Return final JPG bytes.

    Headline is taken from the prompt itself — we extract the first
    meaningful phrase ("about X" or the first sentence) and render that.
    Brand text is configurable.
    """

    def __init__(
        self,
        base_provider: _BaseProvider,
        header_color: str = "#0F3D5C",
        accent_color: str = "#14B8A6",
        text_color: str = "#FFFFFF",
        brand_text: str = "CYBERBRIEFS DAILY",
        font_path: str | None = None,
    ) -> None:
        self.base = base_provider
        self.header_color = header_color
        self.accent_color = accent_color
        self.text_color = text_color
        self.brand_text = brand_text
        self.font_path = font_path

    # ── public API ────────────────────────────────────────────────────

    def generate_image(self, prompt: str) -> bytes:
        headline = self._extract_headline(prompt)
        # Ask the base provider for an ABSTRACT visual, not for text on the image.
        # This avoids the underlying model trying (and failing) to render the title.
        visual_prompt = self._visual_only_prompt(prompt)
        try:
            base_bytes = self.base.generate_image(visual_prompt)
            base_img = Image.open(io.BytesIO(base_bytes)).convert("RGB")
        except Exception:
            # If even the AI background fails, fall back to a solid gradient
            base_img = self._solid_background()

        # Normalise base to 1024x1024 (most providers already produce this)
        if base_img.size != (1024, 1024):
            base_img = base_img.resize((1024, 1024), Image.LANCZOS)

        composed = self._compose(base_img, headline)
        buf = io.BytesIO()
        composed.save(buf, format="JPEG", quality=88, optimize=True)
        return buf.getvalue()

    # ── composition pipeline ──────────────────────────────────────────

    def _compose(self, base: Image.Image, headline: str) -> Image.Image:
        """Layer the branded overlays on top of the AI base."""
        canvas = base.copy()

        # 1. Soft darken the AI image so overlay text is more readable
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 50))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

        # 2. Top header band — solid navy rectangle, 32% of canvas height
        draw = ImageDraw.Draw(canvas)
        band_h = int(canvas.height * 0.32)
        draw.rectangle([0, 0, canvas.width, band_h], fill=self.header_color)

        # 3. Accent strip below header band (3 px teal line)
        draw.rectangle(
            [0, band_h, canvas.width, band_h + 4],
            fill=self.accent_color,
        )

        # 4. Headline text — wrap to fit, autosize down if too long
        self._draw_wrapped_text(
            draw=draw,
            text=headline,
            xy=(60, 60),
            max_width=canvas.width - 120,
            max_height=band_h - 120,
            fill=self.text_color,
            font_path=self.font_path,
        )

        # 5. Brand mark in bottom-right with a small teal accent dot
        brand_font = _load_font(28, self.font_path)
        bb = draw.textbbox((0, 0), self.brand_text, font=brand_font)
        bw, bh = bb[2] - bb[0], bb[3] - bb[1]
        margin = 40
        bx = canvas.width - bw - margin
        by = canvas.height - bh - margin
        # Background pill for legibility
        draw.rounded_rectangle(
            [bx - 22, by - 12, bx + bw + 22, by + bh + 16],
            radius=20,
            fill=self.header_color,
        )
        draw.ellipse([bx - 14, by + bh // 2 - 6, bx - 2, by + bh // 2 + 6], fill=self.accent_color)
        draw.text((bx, by), self.brand_text, fill=self.text_color, font=brand_font)

        return canvas

    def _draw_wrapped_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        xy: tuple[int, int],
        max_width: int,
        max_height: int,
        fill: str,
        font_path: str | None,
    ) -> None:
        """Draw `text` starting at `xy`, wrapping + autosizing to fit the box."""
        # Start large, shrink until the wrapped text fits
        for size in (72, 64, 56, 50, 44, 38, 32):
            font = _load_font(size, font_path)
            # Approximate chars per line: max_width / avg-char-width
            avg = font.getlength("M") or 1
            chars_per_line = max(8, int(max_width / avg))
            lines = textwrap.wrap(text, width=chars_per_line) or [text]
            line_h = int(size * 1.15)
            total_h = line_h * len(lines)
            if total_h <= max_height and all(
                font.getlength(line) <= max_width for line in lines
            ):
                # Centred vertically inside the box
                y = xy[1] + (max_height - total_h) // 2
                for line in lines:
                    draw.text((xy[0], y), line, fill=fill, font=font)
                    y += line_h
                return
        # Final fallback: draw at size 28 even if it overflows
        font = _load_font(28, font_path)
        draw.text(xy, text, fill=fill, font=font)

    def _solid_background(self) -> Image.Image:
        """Fallback if the AI base provider errors out."""
        bg = Image.new("RGB", (1024, 1024), self.header_color)
        # Subtle gradient via blur of two-tone
        draw = ImageDraw.Draw(bg)
        draw.rectangle([0, 512, 1024, 1024], fill=self.accent_color)
        return bg.filter(ImageFilter.GaussianBlur(radius=120))

    # ── prompt helpers ────────────────────────────────────────────────

    @staticmethod
    def _extract_headline(prompt: str) -> str:
        """Pick a usable headline from the raw image prompt.

        The image prompt typically reads:
          "Flat-design Instagram infographic about Double-extortion ransomware..."
        We extract the topic after "about " up to a sentence break, falling
        back to the first sentence.
        """
        text = (prompt or "").strip()
        if not text:
            return "CyberBriefs Daily"
        # Look for "about <X>." pattern
        lower = text.lower()
        if "about " in lower:
            after = text[lower.index("about ") + 6 :]
            for sep in (". ", ".\n", "—", "–", ",", ";", "\n", ":"):
                if sep in after:
                    after = after[: after.index(sep)]
                    break
            after = after.strip().strip(".:")
            if after and 4 <= len(after) <= 80:
                return after
        # Fallback: first sentence of the prompt
        for sep in (". ", "\n"):
            if sep in text:
                first = text[: text.index(sep)].strip().rstrip(".")
                if 4 <= len(first) <= 100:
                    return first
        return text[:80]

    @staticmethod
    def _visual_only_prompt(prompt: str) -> str:
        """Rewrite the prompt to discourage text-in-image attempts.

        Replaces any 'title text at top'/'bold headline' clauses with
        empty-canvas instructions so the diffusion model produces a clean
        background that we'll overlay our real text on top of.
        """
        topic = ""
        lower = prompt.lower()
        if "about " in lower:
            after = prompt[lower.index("about ") + 6 :]
            for sep in (". ", "\n", "—", ":"):
                if sep in after:
                    topic = after[: after.index(sep)].strip()
                    break
        if not topic:
            topic = "cybersecurity"
        return (
            f"Abstract minimal background illustration for an infographic about {topic}. "
            f"Navy blue and teal color palette on white background. "
            f"Decorative cybersecurity-themed icons (padlock, shield, network nodes, "
            f"binary patterns). Clean flat-design isometric style. "
            f"DO NOT include any text or words in the image — leave space for "
            f"text overlay. No photoreal people, no fake logos. Square 1024x1024."
        )
