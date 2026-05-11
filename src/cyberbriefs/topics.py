from __future__ import annotations

import random
from datetime import UTC, datetime

from cyberbriefs.models import TopicCandidate


TOPIC_BACKLOG: list[tuple[str, str]] = [
    (
        "Phishing kits are getting faster at copying real login pages",
        "Explain how users can spot suspicious login flows before entering credentials.",
    ),
    (
        "Why ransomware groups target backups first",
        "Show the attack timeline and the defensive controls that reduce blast radius.",
    ),
    (
        "Multi-factor authentication fatigue attacks",
        "Explain push bombing and safer MFA choices like passkeys and number matching.",
    ),
    (
        "Cloud storage misconfigurations",
        "Explain public buckets, leaked tokens, and practical prevention steps.",
    ),
    (
        "Credential stuffing after a breach",
        "Explain why password reuse turns one leak into many account takeovers.",
    ),
    (
        "Business email compromise red flags",
        "Create a checklist for finance teams before approving payment changes.",
    ),
    (
        "Passkeys vs passwords",
        "Explain why phishing-resistant login matters for everyday users and businesses.",
    ),
    (
        "Zero-day vs n-day vulnerabilities",
        "Explain the difference and why patch speed matters after public disclosure.",
    ),
    (
        "AI voice scams",
        "Explain verification steps families and companies can use before sending money.",
    ),
    (
        "QR code phishing",
        "Show how quishing bypasses email filters and what users should inspect.",
    ),
]


def choose_topic(slot: str) -> TopicCandidate:
    day_of_year = datetime.now(UTC).timetuple().tm_yday
    rng = random.Random(f"{day_of_year}:{slot}")
    topic, angle = rng.choice(TOPIC_BACKLOG)
    return TopicCandidate(topic=topic, angle=angle)
