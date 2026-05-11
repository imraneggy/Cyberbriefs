# Project Rundown

## What This Builds

CyberBriefs Automation is a serverless system that creates two cybersecurity infographic drafts every day, asks for Telegram approval, and posts approved images to Instagram.

## Daily Flow

1. GitHub Actions starts the morning or evening workflow.
2. Python chooses a cybersecurity topic.
3. OpenAI generates a caption, hashtags, alt text, and image prompt.
4. OpenAI Image API generates a JPEG infographic with `gpt-image-2`.
5. The image uploads to Cloudflare R2.
6. The generated post is saved in Cloudflare KV through the Worker API.
7. Telegram sends the image and caption to the admin.
8. Admin taps `Approve` or `Reject`.
9. Cloudflare Worker publishes approved posts to Instagram.
10. Telegram sends publish success or failure status.

## Why This Architecture

- No VPS or always-on server is required.
- GitHub Actions handles scheduled work.
- Cloudflare Worker is enough for event-driven approval.
- R2 gives Instagram a public image URL.
- Telegram approval prevents low-quality or incorrect posts from going live.

## Current Scope

Included:

- Single-image Instagram feed posts.
- Telegram approve/reject buttons.
- Basic regeneration request handling.
- Post expiration.
- Markdown setup and monetization documentation.
- HTML implementation report.

Not included in v1:

- Carousels.
- Reels.
- Auto-news scraping from paid sources.
- Analytics dashboards.
- Token refresh automation.

## Recommended Repo Name

```text
Cyberbriefs
```

Alternative names:

- `instagram-cyber-infographics`
- `cyberbriefs-ai-publisher`
- `threatbrief-automation`
