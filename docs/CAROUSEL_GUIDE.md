# Carousel Guide

Instagram carousels (2-10 image swipeable posts) consistently get **3-5×
the engagement** of single-image posts in the algorithm. CyberBriefs
supports carousels with a single env var change.

## Enable carousels

In your `.env` or GitHub Actions variables:

```text
CAROUSEL_SLIDES=3   # 1-10. 1 = single post (default). 2+ = carousel.
```

That's it. The pipeline detects `CAROUSEL_SLIDES > 1` and switches the
prompting + image generation + Instagram publish flow accordingly.

## How it works end-to-end

```text
┌─────────────────────────┐
│ choose_topic(slot)      │  picks today's topic (deterministic seed)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ LLM generates           │
│   - 1 caption           │
│   - 8-15 hashtags       │
│   - N slide prompts     │ ← when N > 1, asks for distinct panel prompts
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ For each slide:         │
│   image_provider        │
│     .generate_image()   │
│   GitHub commit → URL   │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Worker stores post      │
│ image_urls=[url1,url2,..│
│ Telegram approval msg   │
└────────────┬────────────┘
             │ user taps ✓
             ▼
┌─────────────────────────┐
│ IG Graph API:           │
│  1. Create N child      │
│     containers (each    │
│     is_carousel_item)   │
│  2. Create parent       │
│     CAROUSEL container  │
│     with children=N1,N2 │
│  3. media_publish parent│
└─────────────────────────┘
```

## Slide composition strategy

When `CAROUSEL_SLIDES=N`, the bot prompts the LLM to plan a coherent N-slide
deck following this structure:

| Slide | Role |
|---|---|
| 1 | **Hook** — bold title, the question/threat |
| 2 | **What is it?** — definition / illustrated overview |
| 3 | **How it works** — 2-3 step diagram |
| 4 | **Red flags** — bulleted warning signs |
| 5 | **Defense steps** — actionable checklist |
| 6 | **Example** — labelled scenario |
| 7 | **Comparison** — before/after panel |
| 8 | **Quick stats** — large number callouts |
| 9 | **Reminder** — single key takeaway |
| 10 | **Call to action** — follow for more |

For carousels < 10 slides, the bot picks the most-impactful subset. The
fallback path (when the planning LLM call fails) also uses these slide-role
prompts deterministically so generation never blocks on a bad LLM response.

## Cost implications

| Provider | Cost per single | Cost per 3-slide carousel | Per month (2 posts/day) |
|---|---|---|---|
| openai gpt-image-2 (low) | ~$0.011 | ~$0.033 | ~$2.00 |
| huggingface FLUX | $0 | $0 | $0 |
| pollinations | $0 | $0 | $0 |
| cloudflare SDXL | $0 (within 10k/day) | $0 | $0 |

The free image providers have no per-image cost, so carousels are
effectively free.

## Image consistency across slides

Image generators don't share state between calls, which is the main
weakness of multi-slide AI carousels — colors and styles drift between
panels. CyberBriefs mitigates this in two ways:

1. The carousel prompt asks the LLM to specify a consistent palette in
   each slide's `image_prompt` (e.g. "navy and teal palette, white
   background, isometric icons").
2. The mechanical fallback appends the same base prompt to every slide,
   varying only the panel role suffix.

For maximum consistency, edit `_carousel_prompt` in
`src/cyberbriefs/free_client.py` to inject your brand colors explicitly
into every slide prompt.

## Approval flow with carousels

The Telegram approval message currently shows the **cover slide only** to
keep message size low. Plans for future:

- Send all N slides as a media group in Telegram (one message, N photos)
- Show slide titles as captions under each

For now, glance at the post via `https://raw.githubusercontent.com/<owner>/<repo>/main/public/posts/<post_id>_0.jpg`
(replace `_0` with `_1`, `_2`, etc. for other slides).

## Disabling carousels

Set `CAROUSEL_SLIDES=1` (the default). The bot falls back to the single-image
flow with zero overhead.

## Troubleshooting

**`Carousel child create failed`** — Instagram requires each child image to
be publicly reachable. If using GitHub storage, ensure the repo is public
(`public/posts/<id>_<n>.jpg` must be browsable in incognito mode).

**Slides look unrelated** — the planning LLM call may have failed silently.
Check the Action logs for `generate carousel prompts` errors. As a workaround,
the mechanical fallback runs automatically.

**Some slides have text glitches but others don't** — diffusion models are
inherently inconsistent with rendered text. Mitigations:
  - Use shorter `image_prompt` text overlays (≤6 words)
  - Or switch to `IMAGE_PROVIDER=cloudflare` (SDXL handles text better)
  - Or stick with a single-image post for that day
