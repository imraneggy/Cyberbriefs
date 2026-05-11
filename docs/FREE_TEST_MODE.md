# Free Test Mode

Use this mode to test the automation without OpenAI API usage.

It validates:

- GitHub Actions.
- GitHub image hosting under `public/posts/`.
- Cloudflare Worker `/api/posts` registration.
- Telegram image + caption delivery.
- Telegram approval/reject buttons.

It does not call OpenAI.

## Run The Test

1. Open GitHub Actions.
2. Select `Test Pipeline Without OpenAI`.
3. Click `Run workflow`.
4. Keep `slot=manual`.
5. Click `Run workflow`.

Expected result:

- A test SVG image is committed to `public/posts/`.
- Telegram receives a post preview.
- The caption clearly says `TEST MODE`.

## Safety

Tap `Reject` first.

Only tap `Approve` if you intentionally want to test Instagram publishing. If your Instagram secrets are placeholders, approval will fail at the Instagram API step, which is expected.

## Switch Back To OpenAI

Use the normal workflows:

- `Generate Morning CyberBrief`
- `Generate Evening CyberBrief`

Those workflows use OpenAI by default.
