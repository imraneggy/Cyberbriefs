from __future__ import annotations

import argparse
import json
import os
import sys

from cyberbriefs.config import Settings
from cyberbriefs.generator import PostGenerator


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate one or more CyberBriefs draft posts.")
    parser.add_argument(
        "--slot",
        required=True,
        choices=["morning", "evening", "manual"],
        help="Slot label — also seeds the deterministic topic picker.",
    )
    parser.add_argument(
        "--drafts",
        type=int,
        default=int(os.environ.get("DRAFTS", "1")),
        help=(
            "How many independent drafts to generate this run. Each draft picks "
            "a different topic and sends its own Telegram approval message. "
            "Default 1 (single post per cron). Set 3 for a morning batch of 3."
        ),
    )
    args = parser.parse_args()

    if args.drafts < 1 or args.drafts > 10:
        print(f"--drafts must be 1-10, got {args.drafts}", file=sys.stderr)
        sys.exit(2)

    settings = Settings.from_env()
    gen = PostGenerator(settings)
    results: list[dict] = []
    failures: list[str] = []
    for i in range(args.drafts):
        try:
            # Suffix the slot label per-draft so the deterministic topic seed
            # differs (slot:morning -> slot:morning_2 etc.). Keeps within slot
            # for analytics but ensures distinct topics within a batch.
            sub_slot = args.slot if i == 0 else f"{args.slot}_{i + 1}"
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
        # Partial success — exit code 2 so CI flags it but doesn't hide
        # already-published drafts.
        sys.exit(2)


if __name__ == "__main__":
    main()
