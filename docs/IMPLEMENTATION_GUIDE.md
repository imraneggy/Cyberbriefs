# Implementation Guide

## Phase 1: Repository Setup

1. Use the `imraneggy/Cyberbriefs` repository.
2. Enable GitHub Actions.
3. Add all GitHub secrets listed in `README.md`.
4. Keep the repository free of real `.env` files and raw tokens.

## Phase 2: Cloudflare Setup

1. Create a Cloudflare R2 bucket.
2. Enable a public bucket URL or custom public domain.
3. Create R2 API credentials.
4. Create a Cloudflare KV namespace.
5. Deploy the Worker from `cloudflare-worker/`.
6. Save the Worker URL as `WORKER_BASE_URL`.

## Phase 3: Telegram Setup

1. Create a Telegram bot through `@BotFather`.
2. Get your admin chat ID.
3. Add Telegram secrets to GitHub and Cloudflare Worker.
4. Set the webhook to `<WORKER_BASE_URL>/telegram/webhook`.

## Phase 4: Instagram Setup

1. Create a Business Instagram account.
2. Link it to a Facebook Page.
3. Create a Meta developer app.
4. Add Instagram Graph API permissions.
5. Generate a long-lived access token.
6. Store the token and Instagram user ID as Cloudflare Worker secrets.

## Phase 5: OpenAI Setup

1. Add `OPENAI_API_KEY` to GitHub secrets.
2. Set `OPENAI_TEXT_MODEL=gpt-4.1-mini`.
3. Set `OPENAI_IMAGE_MODEL=gpt-image-2`.
4. Set `OPENAI_IMAGE_OUTPUT_FORMAT=jpeg`.
5. Start with `OPENAI_IMAGE_QUALITY=low`; increase to `medium` when quality becomes more important than cost.

## Phase 6: Test

1. Manually run `Generate Morning CyberBrief`.
2. Confirm the image appears in Telegram.
3. Reject the first test post.
4. Run the workflow again.
5. Approve the second post.
6. Confirm Instagram publishing.
7. Confirm the Telegram success message includes an Instagram media ID.

## Phase 7: Operate

- Check GitHub Actions after each failed Telegram alert.
- Keep pending approval windows short.
- Monitor OpenAI spend weekly.
- Review Instagram analytics every 7 days.
- Add carousels only after single-image publishing is stable.
