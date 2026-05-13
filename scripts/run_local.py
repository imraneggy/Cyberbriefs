"""Local prompt-only runner — uses Ollama + Telegram, no cloud LLM/IG.

Wires:
  CONTENT_PROVIDER = ollama
  OLLAMA_MODEL     = cyberbriefs:latest  (built via local/cyberbriefs.Modelfile)
  IMAGE_PROVIDER   = prompt_only         (skips image gen)
  IMAGE_STORAGE_BACKEND = none           (skipped in prompt-only mode)

Required env vars (load from a .env in cwd, or set in Windows Task Scheduler):
  TELEGRAM_BOT_TOKEN
  TELEGRAM_ADMIN_CHAT_ID

That's the whole list. No GitHub repo, no Cloudflare Worker, no Instagram
Graph API. You manually generate the image (your subscription) and post
to Instagram yourself.

Usage:
  python scripts/run_local.py --slot morning
  python scripts/run_local.py --slot evening --drafts 2

Wire to Windows Task Scheduler with two triggers (10:00 and 18:00 Asia/Dubai).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from cyberbriefs.config import Settings
from cyberbriefs.generator import PostGenerator


def main() -> None:
    parser = argparse.ArgumentParser(description="Local CyberBriefs draft runner (Ollama + Telegram only).")
    parser.add_argument("--slot", required=True, choices=["morning", "evening", "manual"])
    parser.add_argument("--drafts", type=int, default=int(os.environ.get("DRAFTS", "1")))
    args = parser.parse_args()

    if args.drafts < 1 or args.drafts > 10:
        print(f"--drafts must be 1-10, got {args.drafts}", file=sys.stderr)
        sys.exit(2)

    # Hard-set the prompt-only knobs so users do not have to remember them.
    os.environ.setdefault("CONTENT_PROVIDER", "ollama")
    os.environ.setdefault("OLLAMA_MODEL", "cyberbriefs:latest")
    os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
    os.environ.setdefault("IMAGE_PROVIDER", "prompt_only")
    # Worker/IG are skipped in prompt_only mode, but Settings.from_env still
    # reads these names — leave them empty.
    os.environ.setdefault("WORKER_BASE_URL", "")
    os.environ.setdefault("WORKER_SHARED_SECRET", "")

    settings = Settings.from_env()
    gen = PostGenerator(settings)

    results: list[dict] = []
    failures: list[str] = []
    for i in range(args.drafts):
        sub_slot = args.slot if i == 0 else f"{args.slot}_{i + 1}"
        try:
            post = gen.run(slot=sub_slot)
            results.append({"draft": i + 1, "slot": sub_slot, "post_id": post.post_id, "topic": post.topic})
            print(f"[draft {i + 1}/{args.drafts}] OK  topic={post.topic[:60]!r}  id={post.post_id}")
        except Exception as exc:
            msg = f"[draft {i + 1}/{args.drafts}] FAIL  {exc}"
            print(msg, file=sys.stderr)
            failures.append(msg)

    print()
    print(json.dumps({"requested": args.drafts, "ok": len(results), "failed": len(failures), "results": results}, indent=2))
    if failures and not results:
        sys.exit(1)
    if failures:
        sys.exit(2)


if __name__ == "__main__":
    main()
