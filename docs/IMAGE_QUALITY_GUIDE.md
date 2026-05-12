# Image Quality Guide

The default free stack uses Pollinations.ai (FLUX). FLUX produces beautiful
*illustration* output but cannot reliably render readable text — that's an
inherent limitation of stable-diffusion-family models. This guide shows
how to get **readable in-image text** while staying free.

## Quick comparison (all free)

| Provider | Text rendering | Free tier | Style | Setup | Card needed |
|---|---|---|---|---|---|
| Provider | Text rendering | Free tier image quota | Style | Setup | Card needed |
|---|---|---|---|---|---|
| **Composite** ⭐ (default) | Perfect (PIL real font) | **Unlimited** | Infographic template | None | No |
| Gemini 2.5 Flash Image ("Nano Banana") | Good (native AI) | ❌ **0/day on free tier** (billing required) | AI-generated | 1 min signup + billing setup | **Yes** |
| Recraft v3 | Excellent | 50/day | Vector/flat-design | 1 min signup | **Yes (2026 change)** |
| Ideogram v2 | Best in class | 10/day | Realistic/illustrative | 1 min signup | No |
| NVIDIA NIM (FLUX Pro) | Good | ~1000 credits | FLUX family | 1 min signup | No |
| Pollinations | Weak (FLUX) | Unlimited | FLUX-style | None | No |
| HuggingFace SD3.5 | Decent | ~50/hour | SD3 | Already config'd | No |
| Cloudflare SDXL Lightning | Weak | 10k/day | SDXL | Already config'd | No |

> **⚠️ Important Gemini reality check (2026):** Google quietly moved
> `gemini-2.5-flash-image`, `gemini-3-pro-image-preview`, and
> `gemini-3.1-flash-image-preview` to **paid tier only**. The free
> tier `generate_content_free_tier_requests` quota for all image-gen
> models is hard-set to **`limit: 0`**. The widely-quoted "1500/day"
> figure is for **text generation only** — it does *not* apply to image
> generation. To verify yourself:
>
> ```bash
> curl -s -X POST \
>   "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key=$GEMINI_API_KEY" \
>   -H "Content-Type: application/json" \
>   -d '{"contents":[{"parts":[{"text":"a blue square"}]}],"generationConfig":{"responseModalities":["TEXT","IMAGE"]}}'
> ```
>
> A free-tier key will return HTTP 429 with `limit: 0` on the very first
> request. To use Gemini for images you must enable billing on the
> Google Cloud project the key belongs to. Pricing is ~$0.039 per image
> at time of writing — cheap, but not free.

## Gemini setup (only if you have billing enabled)

1. Go to https://aistudio.google.com/ → log in with your Google account
2. Top-left menu → **Get API Key** → **Create API key in new project**
3. **Enable billing** on that project at https://console.cloud.google.com/billing
   (without this, every image request returns HTTP 429 immediately)
4. Copy the key (looks like `AIzaSy...`)
5. In repo: Settings → Secrets and variables → Actions → **New repository secret**
   - Name: `GEMINI_API_KEY`
   - Value: paste
6. Variables tab → set `GEMINI_IMAGE_MODEL` = `gemini-2.5-flash-image`
   (or `gemini-3.1-flash-image-preview` for newest preview)
7. Variables tab → edit `IMAGE_PROVIDER` from `composite` → `gemini`

Paid-tier rate limit: 1000 RPM, no daily cap. At 5 drafts/day cost is
~$0.20 per day or ~$6 per month. Cheap, but composite mode is free.

## Recommended: Recraft v3

50 images/day is **10× what you need** for 5 drafts/day. Built specifically for
infographic-style content with readable text.

### Setup (5 minutes)

1. Go to https://www.recraft.ai/ → Sign up (Google/email)
2. Top-right menu → **API** → **Generate Token**
3. Copy the token (starts with `RcrSk_`)
4. In your CyberBriefs repo: Settings → Secrets and variables → Actions → **New repository secret**
   - Name: `RECRAFT_API_KEY`
   - Value: paste your token
5. In the same page → **Variables** tab → Edit `IMAGE_PROVIDER`:
   - Change from `pollinations` to `recraft`
6. Optional — customize style. Add variable `RECRAFT_STYLE`:
   - `digital_illustration` (default, clean flat design)
   - `vector_illustration` (SVG-like, super clean)
   - `realistic_image` (photoreal)
   - `icon` (simple icons only)

Next workflow run will use Recraft. **Daily budget: 5 drafts × 1 credit = 5 credits/day, well under 50.**

## Alternative: NVIDIA NIM (FLUX Pro variants)

If you prefer FLUX style but want the higher-quality `flux.1-dev` or
`flux.1.1-pro-ultra` variants:

1. https://build.nvidia.com/ → Sign up → personal API key
2. Add secret `NVIDIA_API_KEY`
3. Set variable `IMAGE_PROVIDER=nvidia`
4. Optional: `NVIDIA_MODEL=black-forest-labs/flux.1-dev` (slower, better)

Free credits typically cover 1000+ images.

## Why FLUX/SDXL can't render text well

Diffusion models learn to generate pixels from a noise field, optimizing for
visual coherence. Text rendering requires **discrete symbol fidelity** —
every glyph must be exactly correct, in the right font, at the right size,
respecting kerning. This is the opposite of how diffusion works.

Recraft and Ideogram solve this by:
- Training with text-heavy datasets (logos, posters, infographics)
- Often using a separate text rendering pass on top of the diffusion output
- Constraining the prompt structure to known-rendering patterns

NVIDIA NIM's FLUX Pro variants help marginally because they have more
parameters and better data, but the underlying limitation remains.

## When in doubt: rely on Telegram + Instagram captions

Remember that the **Telegram preview shows your caption text separately**
from the image, and **Instagram displays the caption + headline as native
text below the image**. So even an AI image with garbled text becomes a
valid post once it's in context — viewers read the caption, the image just
provides visual interest.

If you want production-grade text-in-image and are willing to pay $10/month:
- Recraft Pro
- Ideogram Pro
- Midjourney (no API, manual)
- DALL-E 3 via OpenAI (already supported as `CONTENT_PROVIDER=openai`)
