# Project Modifications

## Initial Implementation

The repository was initialized as a greenfield implementation for a free-tier, serverless Instagram automation system.

## Added Components

- Python generation package under `src/cyberbriefs/`.
- GitHub Actions schedules for morning and evening post generation.
- GitHub Actions job to expire old pending posts.
- Cloudflare Worker for Telegram approval callbacks and Instagram publishing.
- Cloudflare R2 upload client.
- Telegram approval sender.
- Instagram Graph API publishing logic.
- Markdown setup, implementation, tech stack, monetization, and operations guides.
- HTML full implementation report.

## Important Design Decisions

- Use GitHub Actions instead of n8n because no dedicated server is available.
- Use Cloudflare Worker instead of a VPS for Telegram webhooks.
- Use Cloudflare R2 because Instagram requires a public media URL.
- Use Telegram approval before publishing to reduce factual and design risk.
- Use `gpt-image-2` as the default OpenAI image model.
- Use JPEG output for safer Instagram publishing compatibility.

## Future Modifications

Recommended next changes after v1 is stable:

- Add real cybersecurity RSS/news source ingestion.
- Add deduplication against published post history.
- Add carousel generation.
- Add analytics export from Instagram.
- Add LinkedIn and X cross-posting.
- Add automated long-lived Meta token refresh reminders.
