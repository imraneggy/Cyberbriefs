from __future__ import annotations

from cyberbriefs.models import GeneratedPost, TopicCandidate


SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#071017"/>
      <stop offset="52%" stop-color="#102838"/>
      <stop offset="100%" stop-color="#06130f"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="18" stdDeviation="20" flood-color="#000" flood-opacity="0.35"/>
    </filter>
  </defs>
  <rect width="1024" height="1024" fill="url(#bg)"/>
  <circle cx="830" cy="160" r="180" fill="#57d6a3" opacity="0.12"/>
  <circle cx="170" cy="820" r="220" fill="#5bbcff" opacity="0.12"/>
  <rect x="82" y="88" width="860" height="848" rx="48" fill="#0d1b24" opacity="0.92" filter="url(#shadow)"/>
  <text x="122" y="174" fill="#57d6a3" font-family="Arial, sans-serif" font-size="30" font-weight="700" letter-spacing="4">CYBERBRIEFS TEST MODE</text>
  <text x="122" y="276" fill="#eef7fb" font-family="Arial, sans-serif" font-size="68" font-weight="800">{title_line_1}</text>
  <text x="122" y="352" fill="#eef7fb" font-family="Arial, sans-serif" font-size="68" font-weight="800">{title_line_2}</text>
  <rect x="122" y="430" width="780" height="4" fill="#57d6a3" opacity="0.85"/>
  <text x="122" y="510" fill="#d7fbe8" font-family="Arial, sans-serif" font-size="38" font-weight="700">1. Verify the sender</text>
  <text x="122" y="584" fill="#d7fbe8" font-family="Arial, sans-serif" font-size="38" font-weight="700">2. Check the URL</text>
  <text x="122" y="658" fill="#d7fbe8" font-family="Arial, sans-serif" font-size="38" font-weight="700">3. Use MFA and passkeys</text>
  <text x="122" y="780" fill="#9eb6c4" font-family="Arial, sans-serif" font-size="30">Generated without OpenAI for pipeline testing.</text>
  <text x="122" y="834" fill="#9eb6c4" font-family="Arial, sans-serif" font-size="30">Approve in Telegram only if this is a test.</text>
</svg>
"""


def generate_test_post(*, topic: TopicCandidate, slot: str, brand_name: str) -> GeneratedPost:
    return GeneratedPost(
        topic=topic.topic,
        slot=slot,
        headline=f"TEST MODE: {topic.topic}",
        image_prompt="Local SVG test image. No OpenAI call was made.",
        image_alt_text="A CyberBriefs test-mode infographic placeholder.",
        caption=(
            f"TEST MODE for {brand_name}.\n\n"
            f"Topic: {topic.topic}\n\n"
            "This draft validates GitHub Actions, image hosting, Worker registration, "
            "Telegram approval, and Instagram handoff without using OpenAI credits.\n\n"
            "Reject this post unless you intentionally want to test publishing."
        ),
        hashtags=["#CyberSecurity", "#InfoSec", "#TestMode", "#Automation"],
        sources=topic.sources,
    )


def generate_test_image_svg(*, headline: str) -> bytes:
    words = headline.replace("TEST MODE:", "").strip().split()
    title_line_1 = " ".join(words[:3]) or "Cybersecurity"
    title_line_2 = " ".join(words[3:6]) or "Pipeline Test"
    svg = SVG_TEMPLATE.format(
        title_line_1=_escape_xml(title_line_1[:24]),
        title_line_2=_escape_xml(title_line_2[:24]),
    )
    return svg.encode("utf-8")


def _escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
