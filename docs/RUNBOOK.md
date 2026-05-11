# Operations Runbook

## Daily Monitoring

Check:

- GitHub Actions completed successfully.
- Telegram received two approval requests.
- R2 image URLs load publicly.
- Approved posts appear on Instagram.
- Failed posts send Telegram error messages.

## Manual Test

1. Open GitHub Actions.
2. Run `Generate Morning CyberBrief` manually.
3. Reject the first test message in Telegram.
4. Confirm no Instagram post appears.
5. Run the workflow again.
6. Approve the second test message.
7. Confirm the Instagram post appears.

## Common Failures

### No Telegram Message

Likely causes:

- Wrong `TELEGRAM_BOT_TOKEN`.
- Wrong `TELEGRAM_ADMIN_CHAT_ID`.
- R2 image URL is not public.
- GitHub Action failed before Telegram step.

### Telegram Approve Does Nothing

Likely causes:

- Telegram webhook not registered.
- Worker URL changed.
- Worker not deployed.
- `WORKER_SHARED_SECRET` mismatch.

### Instagram Publish Fails

Likely causes:

- Instagram account is not Business or Creator.
- Instagram account is not linked to Facebook Page.
- Access token expired.
- `INSTAGRAM_USER_ID` is wrong.
- R2 image URL is not publicly reachable by Meta.

### OpenAI Fails

Likely causes:

- API billing not enabled.
- Wrong `OPENAI_API_KEY`.
- Organization verification required.
- Image model not available to the account.
- Quality or size value unsupported by the selected model.

## Recovery Steps

- Re-run the failed GitHub Action after fixing secrets.
- Reject bad Telegram drafts instead of approving them.
- If Instagram publishing fails after approval, inspect Worker logs and GitHub Action logs.
- Rotate any token that was exposed outside GitHub/Cloudflare secrets.

## Weekly Review

- Check OpenAI API spend.
- Check Instagram analytics.
- Identify top 5 posts by saves and shares.
- Add 5 new topics based on what performed best.
- Remove weak topics from the backlog.
