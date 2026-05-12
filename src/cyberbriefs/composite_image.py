"""Composite infographic renderer — pure PIL, perfectly readable text.

Generates a real Instagram-style infographic from the LLM-produced post
content. No diffusion model required for the foreground (text + sections
+ icons are all PIL-rendered), so text is always crisp. An optional AI
background can be requested for atmosphere.

Layout (1024×1024 square, Instagram-native):

  ┌─────────────────────────────────────────────────┐
  │ NAVY HEADER BAND                                │
  │   <Headline — wrapped, autosized>              │
  │   ──── (teal accent)                            │
  ├─────────────────────────────────────────────────┤
  │  ┌────────┐  ┌────────┐  ┌────────┐            │
  │  │  Icon  │  │  Icon  │  │  Icon  │            │
  │  │ LABEL1 │  │ LABEL2 │  │ LABEL3 │            │
  │  └────────┘  └────────┘  └────────┘            │
  │                                                 │
  │  • Bullet point 1                               │
  │  • Bullet point 2                               │
  │  • Bullet point 3                               │
  │  • Bullet point 4                               │
  │                                                 │
  ├─────────────────────────────────────────────────┤
  │ NAVY FOOTER BAND                                │
  │  ● CYBERBRIEFS DAILY        slot · topic       │
  └─────────────────────────────────────────────────┘

How content is extracted:
  - Headline → post.headline
  - 3 section labels → first emoji/header per section in the caption
  - Bullet points → "- " lines from the caption
  - Footer brand → COMPOSITE_BRAND_TEXT env var

Falls back gracefully when caption isn't structured: uses headline at the
top, single decorative panel, and the brand mark at the bottom.
"""
from __future__ import annotations

import io
import os
import re
import textwrap
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw, ImageFilter, ImageFont


# Font search order
_FONT_CANDIDATES = [
    "DejaVuSans-Bold.ttf",
    "DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:/Windows/Fonts/Arial.ttf",
    "C:/Windows/Fonts/Verdana.ttf",
]


def _load_font(size: int, override_path: str | None = None) -> ImageFont.FreeTypeFont:
    if override_path and Path(override_path).is_file():
        return ImageFont.truetype(override_path, size=size)
    for candidate in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size=size)
        except (OSError, FileNotFoundError):
            continue
    return ImageFont.load_default()


class _BaseProvider(Protocol):
    def generate_image(self, prompt: str) -> bytes: ...


# ── Icon glyphs — drawn with PIL primitives so they always render ────────
# Each icon function takes (draw, x, y, size, color) and stamps the glyph.
# Centered on (x, y), fitting in `size`×`size` box.

def _icon_padlock(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color: str) -> None:
    """Padlock — shackle arc + body box."""
    bw = int(size * 0.55)
    bh = int(size * 0.40)
    body = (x - bw // 2, y - bh // 2 + int(size * 0.10), x + bw // 2, y + bh // 2 + int(size * 0.10))
    draw.rounded_rectangle(body, radius=4, fill=color)
    # Shackle (top arc)
    arc_h = int(size * 0.35)
    arc = (x - bw // 2 + 6, y - int(size * 0.30), x + bw // 2 - 6, y + int(size * 0.10))
    draw.arc(arc, start=180, end=360, fill=color, width=4)
    # Keyhole
    draw.ellipse((x - 3, y + 3, x + 3, y + 9), fill="white")


def _icon_warning(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color: str) -> None:
    """Triangle warning sign with exclamation mark."""
    half = int(size * 0.35)
    triangle = [(x, y - half), (x - half, y + half), (x + half, y + half)]
    draw.polygon(triangle, fill=color)
    # Exclamation in white
    draw.rectangle((x - 2, y - 8, x + 2, y + 4), fill="white")
    draw.ellipse((x - 3, y + 6, x + 3, y + 12), fill="white")


def _icon_shield(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color: str) -> None:
    """Shield outline."""
    w = int(size * 0.45)
    h = int(size * 0.55)
    # Trapezoidal shield body
    pts = [
        (x - w // 2, y - h // 2),
        (x + w // 2, y - h // 2),
        (x + w // 2 - 4, y + h // 4),
        (x, y + h // 2),
        (x - w // 2 + 4, y + h // 4),
    ]
    draw.polygon(pts, fill=color)
    # Inner checkmark
    draw.line([(x - 8, y), (x - 2, y + 6), (x + 10, y - 8)], fill="white", width=3)


def _icon_lightbulb(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color: str) -> None:
    """Lightbulb — circle with base."""
    r = int(size * 0.25)
    draw.ellipse((x - r, y - r - 4, x + r, y + r - 4), fill=color)
    # Base
    draw.rectangle((x - 6, y + r - 4, x + 6, y + r + 8), fill=color)
    draw.rectangle((x - 4, y + r + 8, x + 4, y + r + 12), fill=color)


def _icon_eye(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color: str) -> None:
    """Eye — almond outline with pupil."""
    w = int(size * 0.45)
    h = int(size * 0.20)
    draw.ellipse((x - w, y - h, x + w, y + h), fill=color)
    draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill="white")
    draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)


def _icon_key(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color: str) -> None:
    """Key — circle + stem with teeth."""
    r = int(size * 0.18)
    draw.ellipse((x - r - 12, y - r, x + r - 12, y + r), fill=color)
    draw.ellipse((x - r - 6, y - r + 6, x + r - 18, y + r - 6), fill="white")
    # Stem
    draw.rectangle((x - 8, y - 4, x + 18, y + 4), fill=color)
    # Teeth
    draw.rectangle((x + 4, y + 4, x + 10, y + 12), fill=color)
    draw.rectangle((x + 14, y + 4, x + 18, y + 10), fill=color)


# Badge label → icon. Labels come from _label_for_heading(), so icon and
# text always agree. This is more reliable than keyword-matching the full
# heading text (which can match multiple categories, e.g. "defend against
# threats" matches both "defend" and "threats").
ICONS_BY_LABEL = {
    "WHAT": _icon_lightbulb,
    "WHY": _icon_warning,
    "HOW": _icon_shield,
    "DEFEND": _icon_shield,
    "RISKS": _icon_warning,
    "DETECT": _icon_eye,
    "EXAMPLE": _icon_lightbulb,
    "FACTS": _icon_lightbulb,
}

# Fallback keyword-based picker for unusual labels (single-word headings
# that didn't match a label rule).
_KEYWORD_ICONS = [
    (("attack", "ransom", "encrypt", "lock", "credential", "password"), _icon_padlock),
    (("access", "auth", "identity", "iam", "key", "mfa", "passkey"), _icon_key),
    (("detect", "monitor", "observ", "watch", "visibility", "scan"), _icon_eye),
    (("defen", "protect", "step", "tip", "recommend", "best practice", "mitigation"), _icon_shield),
    (("risk", "warning", "red flag", "danger", "threat", "vulnerab"), _icon_warning),
    (("what", "definition", "explain", "overview", "introduction"), _icon_lightbulb),
]


def _pick_icon(label: str, section_text: str):
    """Pick an icon: prefer the label-keyed map (matches the badge text),
    fall back to keyword matching on the heading."""
    if label in ICONS_BY_LABEL:
        return ICONS_BY_LABEL[label]
    low = section_text.lower()[:200]
    for keywords, fn in _KEYWORD_ICONS:
        if any(kw in low for kw in keywords):
            return fn
    return _icon_lightbulb  # neutral default


# ── Caption parsing ───────────────────────────────────────────────────────

# Strip leading emoji + variation selectors + whitespace from a heading line
_EMOJI_RE = re.compile(
    r"["
    r"\U0001F300-\U0001F9FF"  # symbols + pictographs
    r"\U0001F600-\U0001F64F"  # emoticons
    r"\U00002700-\U000027BF"  # dingbats
    r"\U0001F680-\U0001F6FF"
    r"☀-⛿"           # misc symbols
    r"✀-➿"
    r"︀-️"           # variation selectors
    r"]+",
    flags=re.UNICODE,
)

# Detect a "heading-style" line — starts with an emoji, OR is title-cased
# without a leading bullet/dash, OR ends with a colon.
_BULLET_PREFIX = ("- ", "• ", "* ", "·", "— ", "– ")


def _is_heading(line: str) -> bool:
    """A line looks like a section heading if it starts with an emoji,
    ends with a colon, or doesn't start with a bullet marker AND looks
    like a title (mixed case, short)."""
    if not line:
        return False
    if line.startswith(_BULLET_PREFIX):
        return False
    # Starts with an emoji?
    if _EMOJI_RE.match(line):
        return True
    # Ends with colon → section header
    if line.rstrip().endswith(":"):
        return True
    return False


# 1-2 word badge label per heading. Maps lowercase keyword fragments to a
# short label that fits in the badge.
_LABEL_RULES = [
    (("what is", "what are", "definition", "overview", "explain", "introduction"), "WHAT"),
    (("why ", "reason", "impact", "important", "matter"), "WHY"),
    (("how ", "way to", "method"), "HOW"),
    (("step", "tip", "defen", "protect", "mitigat", "prevent", "best practice", "recommend"), "DEFEND"),
    (("red flag", "warning", "danger", "risk", "threat", "attack"), "RISKS"),
    (("detect", "monitor", "spot", "identify"), "DETECT"),
    (("example", "case", "scenario"), "EXAMPLE"),
    (("fact", "stat", "number"), "FACTS"),
]


def _label_for_heading(heading: str) -> str:
    """Pick a short 1-word badge label from a heading line."""
    low = heading.lower()
    for keywords, label in _LABEL_RULES:
        if any(kw in low for kw in keywords):
            return label
    # Fallback: first meaningful word, max 8 chars
    clean = _EMOJI_RE.sub("", heading).strip(" :-—–")
    words = [w for w in re.split(r"\s+", clean) if w]
    if not words:
        return "INFO"
    first = words[0].upper()[:8]
    return first or "INFO"


def _parse_caption(caption: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Extract (sections, bullets) from the LLM caption.

    Section detection is heading-driven, NOT block-driven, so blank lines
    between a heading and its bullet list don't break parsing.

    A section is (badge_label, original_heading_text). Up to 3 sections.
    Up to 5 total bullets returned across all sections.
    """
    sections: list[tuple[str, str]] = []
    bullets: list[str] = []
    if not caption:
        return sections, bullets

    lines = [ln.rstrip() for ln in caption.splitlines()]
    current_heading: str | None = None
    for raw in lines:
        ln = raw.strip()
        if not ln:
            continue
        # Bullet line — collect under the most recent section
        if ln.startswith(_BULLET_PREFIX):
            bullet = ln
            for prefix in _BULLET_PREFIX:
                if bullet.startswith(prefix):
                    bullet = bullet[len(prefix):]
                    break
            bullet = bullet.strip()
            if bullet and len(bullets) < 5:
                bullets.append(bullet)
            continue
        # Heading line — open a new section
        if _is_heading(ln):
            current_heading = ln
            if len(sections) < 3:
                sections.append((_label_for_heading(ln), ln))
            continue
        # Plain prose line — append as a bullet if we have no structured bullets yet
        if len(bullets) < 5 and len(ln) < 200:
            bullets.append(ln)

    # Fallback: no structured sections at all — split caption into 1-2 sentences
    if not sections and not bullets:
        sentences = re.split(r"(?<=[.!?])\s+", caption.strip())
        for s in sentences[:4]:
            s = s.strip()
            if s and len(bullets) < 4:
                bullets.append(s)

    return sections, bullets


# ── Main client ───────────────────────────────────────────────────────────

class CompositeImageClient:
    """Renders a real Instagram infographic from a GeneratedPost.

    Two entry points:
      - generate_image(prompt)        legacy contract; uses prompt as headline
      - generate_from_post(post)      RECOMMENDED — uses headline + caption
                                       to build a multi-section infographic
    """

    def __init__(
        self,
        base_provider: _BaseProvider | None = None,  # unused for infographic mode (kept for compat)
        header_color: str = "#0F3D5C",
        accent_color: str = "#14B8A6",
        text_color: str = "#FFFFFF",
        body_bg: str = "#F4F7FB",
        body_text: str = "#0F3D5C",
        brand_text: str = "CYBERBRIEFS DAILY",
        font_path: str | None = None,
    ) -> None:
        self.base = base_provider  # currently unused in infographic mode
        self.header_color = header_color
        self.accent_color = accent_color
        self.text_color = text_color
        self.body_bg = body_bg
        self.body_text = body_text
        self.brand_text = brand_text
        self.font_path = font_path

    # ── Public API ─────────────────────────────────────────────────────

    def generate_image(self, prompt: str) -> bytes:
        """Legacy entry point — derives a headline from the prompt."""
        headline = self._extract_headline_from_prompt(prompt)
        return self._render(headline=headline, sections=[], bullets=[])

    def generate_from_post(self, post) -> bytes:
        """Recommended entry point — uses post.headline + post.caption."""
        headline = (getattr(post, "headline", "") or "CyberBriefs Daily").strip()
        sections, bullets = _parse_caption(getattr(post, "caption", "") or "")
        # Slot label for the footer (morning/evening)
        slot = (getattr(post, "slot", "") or "").upper().replace("_", " ")
        return self._render(headline=headline, sections=sections, bullets=bullets, slot=slot)

    # ── Rendering pipeline ────────────────────────────────────────────

    def _render(
        self,
        *,
        headline: str,
        sections: list[tuple[str, str]],
        bullets: list[str],
        slot: str = "",
    ) -> bytes:
        W, H = 1024, 1024
        canvas = Image.new("RGB", (W, H), self.body_bg)
        draw = ImageDraw.Draw(canvas)

        # ── 1. Header band ────────────────────────────────────────────
        header_h = 260
        draw.rectangle((0, 0, W, header_h), fill=self.header_color)
        draw.rectangle((0, header_h, W, header_h + 6), fill=self.accent_color)

        self._draw_wrapped_text(
            draw=draw,
            text=headline,
            box=(60, 50, W - 60, header_h - 30),
            sizes=(72, 64, 56, 50, 44, 38),
            fill=self.text_color,
            line_spacing=1.12,
        )

        # ── 2. Icon badge row (3 max) ─────────────────────────────────
        if sections:
            badge_y = header_h + 40
            badge_size = 130
            n = len(sections)
            gap = (W - n * badge_size) // (n + 1)
            label_font = _load_font(20, self.font_path)
            for i, (label, original) in enumerate(sections):
                bx = gap + i * (badge_size + gap)
                by = badge_y
                # Rounded badge
                draw.rounded_rectangle(
                    (bx, by, bx + badge_size, by + badge_size),
                    radius=18,
                    fill=self.header_color,
                )
                # Icon (mapped from label so badge icon + label always agree)
                icon_fn = _pick_icon(label, original)
                icon_fn(draw, bx + badge_size // 2, by + badge_size // 2 - 8, 90, self.accent_color)
                # Label below icon, inside the badge
                bbox = draw.textbbox((0, 0), label, font=label_font)
                lw = bbox[2] - bbox[0]
                draw.text(
                    (bx + (badge_size - lw) // 2, by + badge_size - 30),
                    label,
                    fill=self.text_color,
                    font=label_font,
                )

        # ── 3. Bullet points ──────────────────────────────────────────
        body_top = header_h + (220 if sections else 60)
        body_bottom = H - 130  # leave footer space
        if bullets:
            self._draw_bullets(
                draw=draw,
                bullets=bullets,
                box=(80, body_top, W - 80, body_bottom),
            )

        # ── 4. Footer band ────────────────────────────────────────────
        footer_h = 100
        draw.rectangle((0, H - footer_h, W, H), fill=self.header_color)
        draw.rectangle((0, H - footer_h - 4, W, H - footer_h), fill=self.accent_color)
        # Brand: accent dot + text
        brand_font = _load_font(28, self.font_path)
        dot_x = 60
        dot_y = H - footer_h // 2
        draw.ellipse((dot_x, dot_y - 8, dot_x + 16, dot_y + 8), fill=self.accent_color)
        draw.text(
            (dot_x + 30, dot_y - 16),
            self.brand_text,
            fill=self.text_color,
            font=brand_font,
        )
        # Right-side meta (slot label)
        if slot:
            small = _load_font(22, self.font_path)
            bb = draw.textbbox((0, 0), slot, font=small)
            sw = bb[2] - bb[0]
            draw.text(
                (W - sw - 60, dot_y - 12),
                slot,
                fill=self.text_color,
                font=small,
            )

        # Encode JPEG
        buf = io.BytesIO()
        canvas.save(buf, format="JPEG", quality=90, optimize=True)
        return buf.getvalue()

    # ── Helpers ───────────────────────────────────────────────────────

    def _draw_wrapped_text(
        self,
        *,
        draw: ImageDraw.ImageDraw,
        text: str,
        box: tuple[int, int, int, int],
        sizes: tuple[int, ...],
        fill: str,
        line_spacing: float = 1.15,
    ) -> None:
        """Wrap text to fit a box, autosizing down through `sizes` until it fits."""
        x0, y0, x1, y1 = box
        max_width = x1 - x0
        max_height = y1 - y0
        for size in sizes:
            font = _load_font(size, self.font_path)
            avg = font.getlength("M") or 1
            chars_per_line = max(8, int(max_width / avg))
            lines = textwrap.wrap(text, width=chars_per_line) or [text]
            line_h = int(size * line_spacing)
            total_h = line_h * len(lines)
            if total_h <= max_height and all(font.getlength(ln) <= max_width for ln in lines):
                y = y0 + (max_height - total_h) // 2
                for ln in lines:
                    draw.text((x0, y), ln, fill=fill, font=font)
                    y += line_h
                return
        # Last-resort: smallest size
        font = _load_font(sizes[-1], self.font_path)
        draw.text((x0, y0), text, fill=fill, font=font)

    def _draw_bullets(
        self,
        *,
        draw: ImageDraw.ImageDraw,
        bullets: list[str],
        box: tuple[int, int, int, int],
    ) -> None:
        """Render a vertical bullet list inside `box`, autosizing to fit."""
        x0, y0, x1, y1 = box
        max_width = x1 - x0 - 60  # leave room for bullet dot
        max_height = y1 - y0
        for size in (32, 28, 26, 24, 22, 20):
            font = _load_font(size, self.font_path)
            avg = font.getlength("M") or 1
            chars_per_line = max(20, int(max_width / avg))
            wrapped = []
            for b in bullets:
                pieces = textwrap.wrap(b, width=chars_per_line) or [b]
                wrapped.append(pieces)
            # Total height: each bullet = N wrapped lines × line_h + gap
            line_h = int(size * 1.25)
            gap = int(size * 0.7)
            total_h = sum(line_h * len(p) for p in wrapped) + gap * max(0, len(wrapped) - 1)
            if total_h <= max_height:
                y = y0 + (max_height - total_h) // 2
                for pieces in wrapped:
                    # Bullet dot
                    dot_r = max(4, size // 6)
                    dot_y = y + line_h // 2 - dot_r
                    draw.ellipse(
                        (x0 + 8, dot_y, x0 + 8 + dot_r * 2, dot_y + dot_r * 2),
                        fill=self.accent_color,
                    )
                    for j, line in enumerate(pieces):
                        draw.text((x0 + 40, y), line, fill=self.body_text, font=font)
                        y += line_h
                    y += gap
                return
        # Last-resort: too much text, render what we can at size 18
        font = _load_font(18, self.font_path)
        y = y0
        for b in bullets:
            draw.text((x0 + 40, y), b[:80], fill=self.body_text, font=font)
            y += 24

    @staticmethod
    def _extract_headline_from_prompt(prompt: str) -> str:
        """Used by the legacy generate_image() path. Pulls headline-like text
        from a free-form image prompt."""
        text = (prompt or "").strip()
        if not text:
            return "CyberBriefs Daily"
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
        for sep in (". ", "\n"):
            if sep in text:
                first = text[: text.index(sep)].strip().rstrip(".")
                if 4 <= len(first) <= 100:
                    return first
        return text[:80]
