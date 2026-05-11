from __future__ import annotations

import random
from datetime import UTC, datetime

from cyberbriefs.models import TopicCandidate


# 100+ topic backlog. At 2 posts/day, 100 topics ≈ 50 days of fresh content
# before any repetition. Topics are intentionally broad and evergreen — they
# are explainers, not breaking news. Add specific incidents/CVEs at edit time.
TOPIC_BACKLOG: list[tuple[str, str]] = [
    # ── PHISHING & SOCIAL ENGINEERING ────────────────────────────────────
    ("Phishing kits are getting faster at copying real login pages", "Explain how users can spot suspicious login flows before entering credentials."),
    ("Multi-factor authentication fatigue attacks", "Explain push bombing and safer MFA choices like passkeys and number matching."),
    ("Business email compromise red flags", "Create a checklist for finance teams before approving payment changes."),
    ("QR code phishing (quishing)", "Show how QR codes bypass email filters and what users should inspect."),
    ("AI voice scams targeting families", "Explain verification steps before sending money to a caller claiming to be a relative."),
    ("Smishing — SMS phishing red flags", "List 5 phrases scammers reuse in fake-delivery and bank texts."),
    ("Deepfake video calls in CEO fraud", "Steps to verify a leader's request before transferring funds."),
    ("Calendar invite phishing", "Show how malicious .ics files bypass spam filters."),
    ("LinkedIn message scams targeting job seekers", "Recognize fake recruiters and bogus take-home assignments."),
    ("Vishing — voice phishing at scale", "Why phone-number caller ID is unreliable and what to do instead."),
    ("Romance scams during major events", "Pattern-match the early-stage grooming signs."),
    ("Tax-season impersonation scams", "Spot fake tax-authority messages and verify on the real portal."),
    # ── RANSOMWARE & EXTORTION ───────────────────────────────────────────
    ("Why ransomware groups target backups first", "Show the attack timeline and the defensive controls that reduce blast radius."),
    ("Double-extortion ransomware explained", "Why even good backups don't fully protect against data-leak threats."),
    ("Ransomware-as-a-Service economics", "How affiliate models lower the bar for attackers."),
    ("Initial access brokers feeding ransomware gangs", "The marketplace where credentials are sold before encryption hits."),
    ("Why paying ransom rarely ends the problem", "Statistics on repeat targeting after payment."),
    ("Living-off-the-land attacks before encryption", "How attackers use built-in admin tools to stay invisible."),
    ("The 'dwell time' between breach and ransomware", "Why most networks have weeks-long compromise before the attack lands."),
    # ── PASSWORDS, IDENTITY, MFA ─────────────────────────────────────────
    ("Credential stuffing after a breach", "Explain why password reuse turns one leak into many account takeovers."),
    ("Passkeys vs passwords", "Explain why phishing-resistant login matters for everyday users and businesses."),
    ("Why SMS-based 2FA isn't enough anymore", "SIM swap risks and what to use instead."),
    ("Password managers — what gets stored vs encrypted", "Demystify the threat model so users can pick correctly."),
    ("Single sign-on benefits and risks", "Why SSO is a force multiplier — for both defenders and attackers."),
    ("Privileged access management essentials", "Why admin accounts need stricter controls than user accounts."),
    ("Service accounts and the silent risk", "Why non-human identities outnumber humans 10:1 in modern stacks."),
    ("Hardware security keys for the rest of us", "How a $20 key beats authenticator apps for high-value accounts."),
    # ── CLOUD & INFRASTRUCTURE ───────────────────────────────────────────
    ("Cloud storage misconfigurations", "Explain public buckets, leaked tokens, and practical prevention steps."),
    ("The shared-responsibility model", "What your cloud provider secures vs what you must secure."),
    ("Why over-permissive IAM roles are the #1 cloud risk", "Least-privilege in practice."),
    ("Cloud secrets in source code", "How leaked API keys get scanned and abused within minutes."),
    ("Kubernetes security misconfigurations", "The 5 cluster settings most attackers exploit."),
    ("Container image vulnerabilities", "Why pulling :latest is a slow-motion incident."),
    ("Cloud cost spikes as a security signal", "An unexpected bill can indicate cryptomining intrusion."),
    ("Multi-cloud security challenges", "Why consistency matters more than tool choice."),
    ("Serverless function attack surface", "The risks unique to Lambda/Cloud Functions."),
    # ── VULNERABILITIES & PATCHING ───────────────────────────────────────
    ("Zero-day vs n-day vulnerabilities", "Explain the difference and why patch speed matters after public disclosure."),
    ("Why the average patch cycle is too slow", "Real numbers on time-to-exploit after disclosure."),
    ("Supply chain attacks via dependencies", "How one malicious npm or PyPI package can compromise thousands."),
    ("CVE severity scoring — what CVSS misses", "Why a 7.5 in your environment can be more urgent than a 9.8 elsewhere."),
    ("Reachability vs exploitability", "Not every vulnerable library is actually exploitable in your stack."),
    ("End-of-life software is a silent risk", "What to do when vendor support ends but the product stays in use."),
    ("Vulnerability disclosure timelines", "Why responsible disclosure schedules matter for both sides."),
    # ── EMAIL & MESSAGING ────────────────────────────────────────────────
    ("Email spoofing without SPF/DKIM/DMARC", "Why those 3 acronyms decide if your brand can be impersonated."),
    ("Encrypted-messaging-app metadata leaks", "What Signal/Telegram still reveal even with E2EE."),
    ("Disappearing messages aren't recovery-proof", "What screenshots and OS backups still capture."),
    ("Why .pdf attachments are still a top attack vector", "Embedded scripts, exploits, and what to disable."),
    # ── DEVICES, ENDPOINTS, IOT ──────────────────────────────────────────
    ("Smart home device security basics", "The 4 settings to change on any new IoT device."),
    ("Public USB charging port risks (juice jacking)", "Why a $5 cable can be malicious."),
    ("Why MDM matters for BYOD", "How mobile device management balances privacy and security."),
    ("Lost-phone playbook", "What to do in the first 10 minutes after losing a device."),
    ("Router firmware — the forgotten attack surface", "Default credentials still account for many home breaches."),
    ("Webcam security beyond covering the lens", "Audio capture and microphone risk."),
    ("Smartwatch and wearable data exposure", "What fitness apps sync to the cloud without you noticing."),
    # ── NETWORK SECURITY ─────────────────────────────────────────────────
    ("Public WiFi risks — VPN vs not", "Concrete attack scenarios and when a VPN actually helps."),
    ("DNS hijacking and how to detect it", "Why DNS lookups are the silent telemetry of your activity."),
    ("Why HTTPS isn't a guarantee of safety", "Phishing sites have valid certs too."),
    ("Network segmentation for small offices", "How to isolate guest WiFi from business resources."),
    ("Zero Trust explained simply", "Beyond the buzzword — what changes in practice."),
    ("VPN myths and reality", "What a VPN can and cannot protect against."),
    # ── DATA, PRIVACY, COMPLIANCE ────────────────────────────────────────
    ("What your browser fingerprint reveals", "Why incognito mode isn't anonymity."),
    ("Cookies vs trackers vs fingerprinting", "The 3-tier tracking pyramid."),
    ("Data minimization as a security control", "Why collecting less is the strongest defense."),
    ("GDPR vs CCPA vs UAE PDPL — the 5 differences that matter", "Cross-jurisdiction privacy basics."),
    ("Right to be forgotten in practice", "What companies legally must delete vs what they actually can."),
    ("Data retention policies done right", "Aged data is liability, not asset."),
    ("HIPAA basics for SaaS founders", "When a US healthcare contract requires special handling."),
    # ── INSIDER & THIRD-PARTY RISK ───────────────────────────────────────
    ("Insider threat — the 3 types to watch", "Negligent, malicious, and compromised insiders."),
    ("Vendor security questionnaires that actually work", "5 questions every SaaS buyer should ask."),
    ("Third-party API risks", "When integrating a tool means inheriting their attack surface."),
    ("Off-boarding checklist when an employee leaves", "The 10-step credential revocation list."),
    ("Shadow IT — when employees use unapproved tools", "Why blocking doesn't work and what does."),
    # ── AI & EMERGING THREATS ────────────────────────────────────────────
    ("Prompt injection attacks on LLM apps", "When a clever input takes over an AI tool."),
    ("AI-generated phishing at scale", "Why personalized attacks just got cheaper."),
    ("Model poisoning in training data", "How attackers corrupt AI from the source."),
    ("LLM data leakage to providers", "What enterprise users should know before pasting code."),
    ("Adversarial examples explained", "Tiny tweaks that fool image classifiers."),
    ("AI deepfakes in identity verification", "Why selfie-based KYC is getting harder."),
    ("Synthetic identity fraud powered by AI", "The new account-opening fraud trend."),
    ("Hallucinations as a security risk in code generation", "When AI invents an API that doesn't exist."),
    # ── BROWSER & WEB SECURITY ───────────────────────────────────────────
    ("Browser extension permissions audit", "How a flashlight extension can read your bank login."),
    ("Session hijacking via cookies", "Why 'log out everywhere' matters after suspicion."),
    ("Malvertising — ads as malware delivery", "Even reputable sites can serve poisoned ads."),
    ("Watering hole attacks", "When the website you trust is the trap."),
    ("Cross-site request forgery in everyday apps", "Why one bad tab can submit forms in another."),
    # ── PHYSICAL & SUPPLY CHAIN ──────────────────────────────────────────
    ("Tailgating into the server room", "Physical access still defeats most cyber controls."),
    ("Discarded hardware as a data leak", "Why DBAN and physical destruction are not interchangeable."),
    ("Smart-badge cloning attacks", "RFID skimmers and how to defend."),
    ("Hardware supply chain risks", "When the chip itself is compromised."),
    # ── INCIDENT RESPONSE & RECOVERY ─────────────────────────────────────
    ("The first hour of an incident — what to do", "A 60-minute playbook for non-security teams."),
    ("Why 'just restore from backup' isn't always safe", "Reinfection risks from compromised backups."),
    ("Tabletop exercises that actually find gaps", "How to run a useful drill in 90 minutes."),
    ("After-action reports — the underrated security tool", "What good postmortems look like."),
    ("Forensic readiness — what logs to keep", "The 4 log sources you wish you had after an incident."),
    # ── SECURITY OPERATIONS ──────────────────────────────────────────────
    ("Alert fatigue in the SOC", "Why high alert volume creates blind spots."),
    ("SIEM vs XDR — the difference that matters", "When to invest in which capability."),
    ("Threat hunting basics", "Looking for the attack you haven't been alerted to."),
    ("MITRE ATT&CK in plain English", "Why this framework underpins modern detection."),
    ("Detection-as-code", "Treating detection rules like software."),
    # ── REGULATORY & EXECUTIVE ───────────────────────────────────────────
    ("Board-level cyber metrics that matter", "What execs should ask their security teams."),
    ("Cyber insurance — what's covered and what isn't", "Pre-incident reading for procurement."),
    ("NESA / UAE IA framework basics", "Compliance starting points for the GCC region."),
    ("ISO 27001 in 5 minutes", "What certification really requires."),
    ("NIST CSF 2.0 — what changed", "The new Govern function and why it matters."),
    # ── PERSONAL & FAMILY SECURITY ───────────────────────────────────────
    ("Securing a parent's smartphone in 10 minutes", "The 5 settings that block 80% of attacks."),
    ("Kid-safe internet basics", "Age-appropriate guidance, not surveillance."),
    ("Estate planning for digital accounts", "What happens to your accounts after you're gone."),
    ("Travel security checklist", "Border crossings, hotel WiFi, and device hygiene abroad."),
    ("Securing a new home network in 15 minutes", "The first-week router and DNS setup."),
]


def choose_topic(slot: str) -> TopicCandidate:
    """Pick a topic deterministically for today's (day, slot) seed.

    Date-based seed means morning + evening on the same day never collide,
    and a missed cron run does not accidentally pick yesterday's topic.
    The same (day, slot) always picks the same topic, useful for retries
    and idempotency.
    """
    day_of_year = datetime.now(UTC).timetuple().tm_yday
    rng = random.Random(f"{day_of_year}:{slot}")
    topic, angle = rng.choice(TOPIC_BACKLOG)
    return TopicCandidate(topic=topic, angle=angle)
