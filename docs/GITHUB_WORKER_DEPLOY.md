# Deploy Cloudflare Worker From GitHub

Yes, the Cloudflare Worker can be deployed directly from GitHub Actions. This repository includes:

```text
.github/workflows/deploy-worker.yml
```

The workflow deploys `cloudflare-worker/` using Cloudflare Wrangler.

## What This Replaces

You do not need to deploy the Worker manually from your local machine if you use this workflow.

You still need to create Cloudflare resources first:

- Cloudflare account.
- R2 bucket.
- KV namespace.
- Cloudflare API token.

## Required GitHub Secrets For Worker Deployment

Add these in:

`GitHub repo -> Settings -> Secrets and variables -> Actions`

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

Some of these are also used by the post generation workflows.

## Create Cloudflare API Token

Create an API token in Cloudflare with permissions to deploy Workers and edit KV.

Recommended permissions:

```text
Account: Cloudflare Workers Scripts: Edit
Account: Workers KV Storage: Edit
Account: Account Settings: Read
```

Scope it to your account if possible.

Save the token as:

```text
CLOUDFLARE_API_TOKEN
```

## Create KV Namespace

In Cloudflare dashboard:

1. Go to Workers & Pages.
2. Open KV.
3. Create a namespace named `Cyberbriefs_Posts`.
4. Copy the namespace ID.
5. Save it as GitHub secret:

```text
CLOUDFLARE_KV_NAMESPACE_ID
```

The GitHub workflow generates `wrangler.toml` at deploy time using this secret.

## Deploy From GitHub

1. Open the repository.
2. Go to `Actions`.
3. Select `Deploy Cloudflare Worker`.
4. Click `Run workflow`.
5. Wait for it to complete.

After deployment, Cloudflare will show a Worker URL like:

```text
https://cyberbriefs-approval.<your-subdomain>.workers.dev
```

Add that URL as this GitHub secret:

```text
WORKER_BASE_URL
```

## Register Telegram Webhook

After the Worker is deployed, open this URL in your browser:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=<WORKER_BASE_URL>/telegram/webhook
```

Then verify:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo
```

## When It Auto-Deploys

The Worker deploy workflow runs when:

- You manually click `Run workflow`.
- A commit changes files under `cloudflare-worker/**`.
- A commit changes `.github/workflows/deploy-worker.yml`.

## Common Failure Reasons

- `CLOUDFLARE_API_TOKEN` is missing or lacks Worker edit permission.
- `CLOUDFLARE_KV_NAMESPACE_ID` is wrong.
- `INSTAGRAM_ACCESS_TOKEN` or `INSTAGRAM_USER_ID` is missing.
- Cloudflare account ID is wrong.
- Worker name already exists in a different account.
