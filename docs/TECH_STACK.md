# Tech Stack

## Runtime

- Python 3.11 for scheduled generation scripts.
- TypeScript on Cloudflare Workers for Telegram approval and Instagram publishing.
- GitHub Actions for free scheduled execution.

## AI

- OpenAI Responses API for structured post copy and image prompts.
- OpenAI Image API for infographic generation.
- Default image model: `gpt-image-2`.
- Optional ChatGPT-specific model alias: `chatgpt-image-latest`.
- Default image output: `jpeg`, `1024x1024`, `low` quality for low-cost daily posting.

## Automation

- GitHub Actions runs morning and evening generation workflows.
- Cloudflare Worker receives Telegram callback webhooks.
- Cloudflare KV stores post state.
- Cloudflare R2 stores generated images.

## Social APIs

- Telegram Bot API sends approval previews with inline buttons.
- Instagram Graph API publishes approved feed posts.

## Cost Profile

- GitHub Actions: free tier.
- Cloudflare Worker/KV/R2: free tier for this expected usage.
- Telegram Bot API: free.
- Instagram Graph API: free.
- OpenAI API: paid usage, controlled by image quality and post volume.

## Security

- API keys are stored as GitHub Actions secrets and Cloudflare Worker secrets.
- The Worker write API requires `X-CyberBriefs-Secret`.
- Instagram publishing happens only after Telegram approval.
- No Instagram password or browser automation is used.
