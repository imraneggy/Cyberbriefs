# Setup Guide

This guide gets the free-tier automation running end to end.

## 1. Create The Instagram Account

1. Create a new Instagram account.
2. Switch it to Business or Creator.
3. Create or use a Facebook Page.
4. Link the Instagram account to the Facebook Page.

Do not use unofficial browser automation. Use Instagram Graph API publishing only.

## 2. Create Meta App And Token

1. Open Meta for Developers.
2. Create an app.
3. Add Instagram Graph API.
4. Connect the linked Facebook Page and Instagram account.
5. Generate a long-lived access token with publishing access.
6. Find the Instagram user ID.

Save these as Worker secrets:

```text
INSTAGRAM_ACCESS_TOKEN
INSTAGRAM_USER_ID
```

## 3. Create Telegram Bot

1. Open Telegram and message `@BotFather`.
2. Run `/newbot`.
3. Save the token.
4. Message your bot once.
5. Open:

```text
https://api.telegram.org/bot<token>/getUpdates
```

6. Copy your chat ID.

Save these in GitHub and Cloudflare Worker secrets:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_ADMIN_CHAT_ID
```

## 4. Create Cloudflare R2 Bucket

1. Open Cloudflare dashboard.
2. Create an R2 bucket.
3. Enable a public bucket URL or custom public domain.
4. Create R2 API credentials with object read/write access.

Save these as GitHub secrets:

```text
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_R2_ACCESS_KEY_ID
CLOUDFLARE_R2_SECRET_ACCESS_KEY
CLOUDFLARE_R2_BUCKET
CLOUDFLARE_R2_PUBLIC_BASE_URL
```

The public base URL should not include a trailing slash.

## 5. Deploy Cloudflare Worker

From `cloudflare-worker/`:

```bash
npm install
npx wrangler login
npx wrangler kv namespace create POSTS_KV
```

Copy:

```bash
cp wrangler.toml.example wrangler.toml
```

Edit `wrangler.toml` and add the KV namespace ID.

Set Worker secrets:

```bash
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_ADMIN_CHAT_ID
npx wrangler secret put INSTAGRAM_ACCESS_TOKEN
npx wrangler secret put INSTAGRAM_USER_ID
npx wrangler secret put WORKER_SHARED_SECRET
```

Deploy:

```bash
npx wrangler deploy
```

Save the deployed URL as:

```text
WORKER_BASE_URL
```

## 6. Register Telegram Webhook

Open this URL:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=<WORKER_BASE_URL>/telegram/webhook
```

Then verify:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo
```

## 7. Add GitHub Secrets

In GitHub:

`Settings -> Secrets and variables -> Actions`

Add:

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

Recommended values:

```text
OPENAI_TEXT_MODEL=gpt-4.1-mini
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_QUALITY=low
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_IMAGE_OUTPUT_FORMAT=jpeg
```

Use `chatgpt-image-latest` only if you specifically want the image snapshot used by ChatGPT. For API-first automation, keep `gpt-image-2`.

## 8. Test

1. In GitHub, open Actions.
2. Run `Generate Morning CyberBrief` manually.
3. Wait for Telegram message.
4. Tap `Reject` first and confirm it does not publish.
5. Run the workflow again.
6. Tap `Approve`.
7. Confirm Instagram post appears.

## 9. Go Live

The schedules are UTC:

```text
Morning: 06:00 UTC = 10:00 Asia/Dubai
Evening: 14:00 UTC = 18:00 Asia/Dubai
```

GitHub scheduled workflows may be delayed by several minutes. This is normal on the free tier.
