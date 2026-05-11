from __future__ import annotations

import argparse

import httpx

from cyberbriefs.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Expire old pending posts.")
    parser.add_argument("--max-age-hours", type=int, default=8)
    args = parser.parse_args()

    settings = Settings.from_env()
    response = httpx.post(
        f"{settings.worker_base_url}/api/posts/expire",
        headers={"X-CyberBriefs-Secret": settings.worker_shared_secret},
        json={"max_age_hours": args.max_age_hours},
        timeout=60,
    )
    response.raise_for_status()
    print(response.text)


if __name__ == "__main__":
    main()
