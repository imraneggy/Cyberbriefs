# OpenAI API Key Guide

A ChatGPT subscription does not automatically include API usage. API access is managed from the OpenAI Platform and requires API billing or credits.

## Create The Key

1. Go to `https://platform.openai.com`.
2. Sign in with your OpenAI account.
3. Open `Settings`.
4. Open `Billing` and add API billing or credits.
5. Open `Projects`.
6. Create a project named `CyberBriefs Automation`.
7. Open the project API keys page.
8. Create a new secret key named `cyberbriefs-github-actions`.
9. Copy the key once.
10. Add it to GitHub Actions secrets as `OPENAI_API_KEY`.

Do not commit the API key to the repository.

## Recommended GitHub Secret Values

```text
OPENAI_API_KEY=<your key>
OPENAI_TEXT_MODEL=gpt-4.1-mini
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_QUALITY=low
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_IMAGE_OUTPUT_FORMAT=jpeg
```

## If Image Generation Fails

Check:

- API billing is enabled.
- The key belongs to the correct project.
- Your organization is verified if required.
- The selected image model is available to your account.
- The configured quality and size are supported.

## Model Choice

Use `gpt-image-2` for this automation because it is the default API-first image generation model in this project.

Use `chatgpt-image-latest` only if you specifically want the ChatGPT image snapshot behavior.
