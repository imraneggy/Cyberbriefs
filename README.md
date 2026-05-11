# CyberBriefs Automation

Fully serverless Instagram infographic automation with Telegram approval.

This repository implements:

- Two scheduled daily draft generations with GitHub Actions.
- OpenAI-generated cybersecurity infographic images and captions using the latest Image API model.
- Cloudflare R2 image hosting for public Instagram media URLs.
- Cloudflare Worker Telegram approval webhook.
- Instagram Graph API publishing after manual Telegram approval.
- Cloudflare Worker deployment directly from GitHub Actions.

The automation infrastructure can run on free tiers. OpenAI API image generation is the expected paid component.

## Architecture

```text
GitHub Actions
  -> Python generator
  -> OpenAI text + image generation
  -> Cloudflare R2 upload
  -> Cloudflare Worker post registry
  -> Telegram approval message

Telegram Approve button
  -> Cloudflare Worker webhook
  -> Instagram Graph API create media container
  -> Instagram Graph API publish container
  -> Telegram confirmation
```

## Repository Layout

```text
.github/workflows/
  deploy-worker.yml
  generate-morning.yml
  generate-evening.yml
  expire-pending.yml

cloudflare-worker/
  src/index.ts
  wrangler.toml.example

src/cyberbriefs/
  config.py
  generator.py
  instagram.py
  models.py
  openai_client.py
  r2.py
  telegram.py
  topics.py

scripts/
  generate_post.py
  expire_pending.py

docs/
  GITHUB_WORKER_DEPLOY.md
  SETUP.md
  IMPLEMENTATION_GUIDE.md
  TECH_STACK.md
  PROJECT_RUNDOWN.md
  PROJECT_MODIFICATIONS.md
  MONETIZATION_GUIDE.md
  RUNBOOK.md

reports/
  full-report.html
```

## Required Accounts

1. OpenAI API account.
2. Telegram bot from `@BotFather`.
3. Cloudflare free account with R2 enabled.
4. Instagram Business or Creator account.
5. Facebook Page linked to the Instagram account.
6. Meta developer app with Instagram Graph API access.
7. GitHub repository with Actions enabled.

## Required GitHub Secrets

Add these in GitHub:

`Settings -> Secrets and variables -> Actions -> New repository secret`

Generation secrets:

```text
OPENAI_API_KEY
OPENAI_TEXT_MODEL
OPENAI_IMAGE_MODEL
OPENAI_IMAGE_QUALITY
OPENAI_IMAGE_SIZE
OPENAI_IMAGE_OUTPUT_FORMAT
TELEGRAM_BOT_TOKEN
TELEGRAM_ADMIN_CHAT_ID
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_R2_ACCESS_KEY_ID
CLOUDFLARE_R2_SECRET_ACCESS_KEY
CLOUDFLARE_R2_BUCKET
CLOUDFLARE_R2_PUBLIC_BASE_URL
WORKER_BASE_URL
WORKER_SHARED_SECRET
```

Worker deployment secrets:

```text
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_KV_NAMESPACE_ID
TELEGRAM_BOT_TOKEN
TELEGRAM_ADMIN_CHAT_ID
INSTAGRAM_ACCESS_TOKEN
INSTAGRAM_USER_ID
WORKER_SHARED_SECRET
```

Optional GitHub variables:

```text
CYBERBRIEFS_TIMEZONE
CYBERBRIEFS_BRAND_NAME
CYBERBRIEFS_SITE_URL
```

Defaults:

```text
OPENAI_TEXT_MODEL=gpt-4.1-mini
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_QUALITY=low
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_IMAGE_OUTPUT_FORMAT=jpeg
CYBERBRIEFS_TIMEZONE=Asia/Dubai
CYBERBRIEFS_BRAND_NAME=CyberBriefsDaily
```

Image model notes:

- `gpt-image-2` is the default because OpenAI currently lists it as the state-of-the-art Image API model.
- `chatgpt-image-latest` can be used if you specifically want the image model snapshot used in ChatGPT.
- The output format defaults to `jpeg` because public Instagram publishing is more reliable with JPEG media URLs.

## Deploy Worker From GitHub

This repo includes:

```text
.github/workflows/deploy-worker.yml
```

Steps:

1. Create Cloudflare R2 bucket.
2. Create Cloudflare KV namespace and save its ID as `CLOUDFLARE_KV_NAMESPACE_ID`.
3. Create a Cloudflare API token and save it as `CLOUDFLARE_API_TOKEN`.
4. Add Instagram Worker secrets to GitHub: `INSTAGRAM_ACCESS_TOKEN` and `INSTAGRAM_USER_ID`.
5. Go to `Actions -> Deploy Cloudflare Worker -> Run workflow`.
6. Copy the deployed Worker URL and save it as `WORKER_BASE_URL`.

Detailed guide:

```text
docs/GITHUB_WORKER_DEPLOY.md
```

## Telegram Setup

Create a bot:

1. Message `@BotFather`.
2. Run `/newbot`.
3. Save the token as `TELEGRAM_BOT_TOKEN`.
4. Send any message to the bot from your Telegram account.
5. Get your chat ID:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates
```

Set Telegram webhook to your deployed Worker:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<worker-url>/telegram/webhook
```

## Instagram Setup

Use the official Instagram Graph API flow:

1. Convert the Instagram account to Business or Creator.
2. Link it to a Facebook Page.
3. Create a Meta developer app.
4. Add Instagram Graph API.
5. Get the Instagram business account ID.
6. Generate a long-lived access token.
7. Store `INSTAGRAM_ACCESS_TOKEN` and `INSTAGRAM_USER_ID` as GitHub Actions secrets for Worker deployment.

The Worker publishes by:

1. `POST /{ig-user-id}/media` with `image_url` and `caption`.
2. `POST /{ig-user-id}/media_publish` with `creation_id`.

## Cloudflare R2 Setup

Create an R2 bucket, then add a public domain or `r2.dev` public URL.

Set:

```text
CLOUDFLARE_R2_PUBLIC_BASE_URL=https://your-public-r2-domain
```

The generated image URL must be publicly fetchable by Instagram.

## Test A Draft

In GitHub:

`Actions -> Generate Morning CyberBrief -> Run workflow`

Approve the Telegram preview. The Worker should publish to Instagram and reply with the Instagram media ID.

## Safety Rules

- No post publishes without Telegram approval.
- Pending posts expire automatically.
- Captions include source attribution metadata when available.
- Prompts avoid claiming unverified breach details as fact.
- Instagram automation uses the official Graph API only.

## Monetization Roadmap

First 90 days:

- Post 2 single-image cyber explainers per day.
- Track saves, shares, follows, profile visits, and reach.
- Keep the visual system consistent.
- Prioritize save-worthy explainers over generic news summaries.

After traction:

- Add carousels for weekly cyber recaps.
- Add LinkedIn cross-posting.
- Build a newsletter.
- Monetize with affiliates, security awareness templates, cheat sheets, sponsorships, and B2B awareness content.
