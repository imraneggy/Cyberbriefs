from __future__ import annotations

import argparse
import json

from cyberbriefs.config import Settings
from cyberbriefs.generator import PostGenerator


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate one CyberBriefs draft post.")
    parser.add_argument("--slot", required=True, choices=["morning", "evening", "manual"])
    args = parser.parse_args()

    settings = Settings.from_env()
    post = PostGenerator(settings).run(slot=args.slot)
    print(json.dumps(post.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
