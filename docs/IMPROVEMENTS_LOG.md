# Improvements Log

Cumulative record of features and fixes shipped post-MVP. Most-recent first.

---

## 2026-05-11: Free stack + top-5 improvements

Five high-ROI improvements landed in one batch.

### 1. License file

- Added `LICENSE` (MIT).
- Clarifies redistribution rights — without this the default is
  "all rights reserved" and nobody can legally fork or contribute.

### 2. Free-stack content providers

New file: `src/cyberbriefs/free_client.py`

Adds 6 alternative providers selectable via `CONTENT_PROVIDER` and
`IMAGE_PROVIDER` environment variables:

Text:
- `github_models` — free in GH Actions, uses built-in `GITHUB_TOKEN`
- `groq` — free tier, Llama 3.3 70B at 30 req/min
- `huggingface` — free tier, ~100k tokens/day

Image:
- `pollinations` — truly free, no API key, FLUX-backed
- `huggingface` — free tier, FLUX.1-schnell
- `cloudflare` — free tier, SDXL Lightning via Workers AI

Wired into `generator.py` via `FREE_TEXT_PROVIDERS` / `FREE_IMAGE_PROVIDERS`
sets. Config (`config.py`) validates required env vars at startup. See
`docs/FREE_STACK_GUIDE.md` for setup walkthroughs and quality comparison.

Impact: **$1-15/month → $0/month** for typical 2-posts-per-day cadence.

### 3. Topic backlog expansion (10 → 100+)

`src/cyberbriefs/topics.py` now has 100+ curated cybersecurity infographic
topics organised into 13 categories:

- Phishing & social engineering (12)
- Ransomware & extortion (7)
- Passwords, identity, MFA (8)
- Cloud & infrastructure (9)
- Vulnerabilities & patching (7)
- Email & messaging (4)
- Devices, endpoints, IoT (7)
- Network security (6)
- Data, privacy, compliance (7)
- Insider & third-party risk (5)
- AI & emerging threats (8)
- Browser & web security (5)
- Physical & supply chain (4)
- Incident response & recovery (5)
- Security operations (5)
- Regulatory & executive (5)
- Personal & family security (5)

At 2 posts/day, the new backlog covers **~50 days of fresh content**
before any repetition (previous: 5 days).

### 4. Idempotent publish guard

`cloudflare-worker/src/index.ts` — `approveAndPublish()` now checks for
prior published state before re-calling the Instagram Graph API.

Previously: a second Telegram approval click (network retry, double-tap)
would create a duplicate Instagram post and burn Graph API quota.

Now: returns `{ already_published: true, instagram_media_id: <prior id> }`
without making any IG calls.

Also added recovery for `approved` status (publish failed mid-flight) —
re-runs publish and tags the retry timestamp in `error_log`.

### 5. Carousel support (2-10 slides)

Three-layer change to enable Instagram carousel posts:

- **Model** (`models.py`): added `image_urls: list[str]` and
  `slide_titles: list[str]` to `GeneratedPost`, plus an `is_carousel`
  computed property. Backward-compatible — `r2_image_url` still holds
  the cover (slide 0).
- **Generator** (`generator.py`): when `CAROUSEL_SLIDES > 1`, queries the
  LLM for distinct slide prompts (covering hook → defense → CTA), then
  generates and uploads each slide. Falls back to mechanical
  slide-role prompts if the planning LLM call fails.
- **Worker** (`cloudflare-worker/src/index.ts`): added
  `publishCarouselToInstagram()` which implements the 3-step IG
  CAROUSEL_ALBUM flow (children → carousel container → publish).
  Single-image path still uses the existing 2-step flow.

Enable with `CAROUSEL_SLIDES=3` (or any value 2-10). See
`docs/CAROUSEL_GUIDE.md` for engagement rationale and tuning.

### Documentation added

- `docs/FREE_STACK_GUIDE.md` — provider walkthroughs + quality comparison
- `docs/CAROUSEL_GUIDE.md` — carousel flow + composition strategy
- `docs/IMPROVEMENTS_LOG.md` — this file

### Documentation updated

- `README.md` — provider list, carousel mention
- `.env.example` — new env vars with inline explanations

### Files added

```text
LICENSE
src/cyberbriefs/free_client.py
docs/FREE_STACK_GUIDE.md
docs/CAROUSEL_GUIDE.md
docs/IMPROVEMENTS_LOG.md
```

### Files modified

```text
.env.example
README.md
src/cyberbriefs/config.py
src/cyberbriefs/generator.py
src/cyberbriefs/models.py
src/cyberbriefs/topics.py
cloudflare-worker/src/index.ts
```

### Migration notes

For existing deployments:

1. **Default behaviour unchanged** if you leave `CONTENT_PROVIDER=openai`.
2. **To go free**: set `CONTENT_PROVIDER=github_models` and
   `IMAGE_PROVIDER=pollinations`. Remove any `OPENAI_API_KEY` from secrets
   if you want to be sure you're not accidentally charged.
3. **To enable carousels**: add `CAROUSEL_SLIDES=3` (or whatever count).
4. **Worker redeploy needed** for the carousel publish flow and idempotency
   guard. Workflows: `Actions → Deploy Cloudflare Worker → Run workflow`.

### Remaining roadmap items (not yet shipped)

- Engagement analytics loopback (pull IG insights, mark winning topics)
- RSS/news feed as topic source (KrebsOnSecurity, BleepingComputer, THN)
- Hashtag whitelist post-filter
- High-res preview in Telegram approval
- Brand watermark overlay on generated images
- LinkedIn cross-poster
- Failed-publish DLQ
- Multi-account / multi-brand mode (productize)
