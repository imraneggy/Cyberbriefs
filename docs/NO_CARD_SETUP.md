# No-Credit-Card Setup

Cloudflare R2 can ask for a payment method before bucket creation. If you want to avoid adding a card, do not use R2.

This repository now supports a no-card image hosting path:

```text
GitHub Actions -> generated image -> commit to public repo -> raw.githubusercontent.com image URL -> Telegram approval -> Instagram Graph API
```

## What Changes

Use GitHub as the image host instead of Cloudflare R2.

Generated images are committed to:

```text
public/posts/<post_id>.jpg
```

The public image URL becomes:

```text
https://raw.githubusercontent.com/imraneggy/Cyberbriefs/main/public/posts/<post_id>.jpg
```

## Required GitHub Secrets

For the no-card path, you do not need these R2 secrets:

```text
CLOUDFLARE_R2_ACCESS_KEY_ID
CLOUDFLARE_R2_SECRET_ACCESS_KEY
CLOUDFLARE_R2_BUCKET
CLOUDFLARE_R2_PUBLIC_BASE_URL
```

You still need:

```text
OPENAI_API_KEY
OPENAI_TEXT_MODEL
OPENAI_IMAGE_MODEL
OPENAI_IMAGE_QUALITY
OPENAI_IMAGE_SIZE
OPENAI_IMAGE_OUTPUT_FORMAT
TELEGRAM_BOT_TOKEN
TELEGRAM_ADMIN_CHAT_ID
WORKER_BASE_URL
WORKER_SHARED_SECRET
```

The GitHub image upload uses the built-in GitHub Actions token, so you do not need to create a separate GitHub token for image storage.

## GitHub Actions Permission

The generation workflows include:

```yaml
permissions:
  contents: write
```

This allows the workflow to commit generated images into `public/posts/`.

## Required Environment Values

The workflows already set:

```text
IMAGE_STORAGE_BACKEND=github
GITHUB_IMAGE_BRANCH=main
GITHUB_IMAGE_PATH_PREFIX=public/posts
GITHUB_TOKEN=${{ github.token }}
```

## What Still Needs Cloudflare

The current v1 still uses a Cloudflare Worker for Telegram approval callbacks and Instagram publishing.

This usually does not require R2. If Cloudflare also asks for a card for Workers or KV in your account, the next fallback is a pure GitHub Actions polling mode that checks Telegram approvals every 5 minutes instead of using a webhook.

## Tradeoffs

Advantages:

- No R2 bucket.
- No R2 credit card requirement.
- No extra image hosting service.
- Works with your public GitHub repository.

Limitations:

- The repository will grow over time because images are committed to Git.
- Public GitHub raw URLs are used as media URLs.
- If Instagram rejects raw GitHub URLs, switch to GitHub Pages or another free public image host.

## Next Step

Skip Cloudflare R2 setup and continue with:

1. Cloudflare Worker deploy.
2. Telegram webhook registration.
3. Manual GitHub Action test.
