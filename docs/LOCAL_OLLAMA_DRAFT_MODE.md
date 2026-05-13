# Local Ollama draft mode (prompt-only Telegram delivery)

This mode does NOT generate images and does NOT publish to Instagram.
It uses a local Ollama model to draft the post text + image prompt,
then sends a single Telegram message with three copy-paste blocks:

```
🎯 IMAGE PROMPT      ← paste into ChatGPT / Gemini / Midjourney
📱 INSTAGRAM CAPTION ← paste into your IG post (with image you generated)
🏷️ HASHTAGS          ← already in the caption block above
```

You generate the image with your own AI subscription and post to Instagram
manually. The system's job ends at Telegram delivery.

## Why this mode exists

Free-tier image generation in 2026 is broken (Gemini = `limit: 0`, Recraft
needs a card, FLUX can't render text). Free-tier text generation is
abundant. So we play to that asymmetry: the cron does what local LLMs are
great at (structured text), and you handle the image with whatever AI
subscription you already pay for.

Bonus: nothing leaves your machine except the final Telegram message.
The draft itself is generated 100% offline by your local Ollama.

## Setup

### 1. Install Ollama (one-time)

Download from https://ollama.com/ and run the installer. Verify:
```
ollama --version
```

### 2. Pull a base model

Models you might already have:
```
ollama list
```

Recommended (best small-model quality + speed):
```
ollama pull phi4-mini      # 2.5 GB — default, fast
ollama pull qwen3:4b       # 2.5 GB — better long-form but uses /no_think
ollama pull qwen3:8b       # 5 GB   — best quality, slower
```

### 3. Build the cyberbriefs model

This bakes the cybersecurity-editor system prompt and a worked example
into a custom Ollama model. Re-run any time you tune the Modelfile.

```
cd /path/to/Cyberbriefs
ollama create cyberbriefs:latest -f local/cyberbriefs.Modelfile
```

Verify the bake:
```
ollama run cyberbriefs:latest "Topic: phishing via QR codes"
```

You should see a JSON object scroll past with `headline`, `caption`,
`image_prompt`, `image_alt_text`, `hashtags`.

### 4. Install the Python package

```
python -m pip install -e .
```

### 5. Set the two required env vars

Only Telegram is needed — no GitHub Actions secrets, no Worker, no IG
Graph API, no image storage. Drop a `.env` in the repo root:

```
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_ADMIN_CHAT_ID=987654321
```

The chat ID is your personal Telegram user ID; send `/start` to
[@userinfobot](https://t.me/userinfobot) to look it up.

### 6. Test one draft

```
python scripts/run_local.py --slot manual
```

If your bot token is correct and Ollama is running, a Telegram message
with three copy-paste blocks lands within ~60s.

### 7. Schedule it on Windows Task Scheduler

Two daily triggers (morning + evening, Asia/Dubai):

| Trigger      | Time   | Command                                                                  |
| ------------ | ------ | ------------------------------------------------------------------------ |
| Morning      | 10:00  | `python C:\path\to\Cyberbriefs\scripts\run_local.py --slot morning --drafts 3` |
| Evening      | 18:00  | `python C:\path\to\Cyberbriefs\scripts\run_local.py --slot evening --drafts 2` |

Action → Start a program:
- Program/script: `python.exe` (or full path)
- Add arguments: `scripts\run_local.py --slot morning --drafts 3`
- Start in: `C:\Users\you\path\to\Cyberbriefs`

Make sure Ollama runs at boot (it does by default on Windows).

## Customising the bot

### Change the base model

Edit `local/cyberbriefs.Modelfile` → change `FROM phi4-mini` to whichever
local model gives you the quality you want. Rebuild:

```
ollama create cyberbriefs:latest -f local/cyberbriefs.Modelfile
```

### Tune the system prompt

Same Modelfile, edit the `SYSTEM """..."""` block. Add your own style
guides, banned phrases, or worked examples. Each example you add makes the
model more consistent on that style (this is in-context "training", not
LoRA fine-tuning, but for a daily cron it is sufficient).

### Use a different daily topic mix

Edit `src/cyberbriefs/topics.py` — there are 100+ curated topics across
17 categories. The `--slot` argument seeds a deterministic picker, so
morning and evening posts on the same day will be on different topics.

## Troubleshooting

| Symptom                                  | Likely cause                                     | Fix                                                                         |
| ---------------------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------- |
| `ConnectError: connection refused`       | Ollama is not running                            | Start the Ollama tray app, or run `ollama serve` in a terminal              |
| `model 'cyberbriefs:latest' not found`   | Modelfile not built yet                          | Run the `ollama create` command in §3                                       |
| `Empty LLM output`                       | qwen3 emitted only a `<think>` block then ran out | Already mitigated by `/no_think` directive in client; try a different model |
| Captions consistently too short          | phi4-mini is conservative on length              | Switch base to qwen3:8b in the Modelfile and rebuild                        |
| Telegram message arrives but is unstyled | Your Telegram client doesn't render HTML         | The bot uses `parse_mode: HTML`. Update your Telegram client.               |

## What is NOT used in this mode

- Cloudflare Worker (`WORKER_BASE_URL`, `WORKER_SHARED_SECRET`)
- Instagram Graph API
- Image storage (GitHub repo upload / Cloudflare R2)
- The approve / reject inline-keyboard buttons in Telegram
- `expire_pending.yml` GitHub Action (no pending state to expire)

If you ever want to switch back to auto-publish, set
`IMAGE_PROVIDER=composite` (or `pollinations` etc) and provide the
Worker + IG credentials. The same codebase serves both flows.
