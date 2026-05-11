from __future__ import annotations

import httpx


class InstagramClient:
    def __init__(self, access_token: str, instagram_user_id: str) -> None:
        self.access_token = access_token
        self.instagram_user_id = instagram_user_id
        self._client = httpx.Client(base_url="https://graph.facebook.com/v20.0", timeout=120)

    def publish_image(self, *, image_url: str, caption: str) -> str:
        container_response = self._client.post(
            f"/{self.instagram_user_id}/media",
            data={
                "image_url": image_url,
                "caption": caption,
                "access_token": self.access_token,
            },
        )
        container_response.raise_for_status()
        creation_id = container_response.json()["id"]
        publish_response = self._client.post(
            f"/{self.instagram_user_id}/media_publish",
            data={
                "creation_id": creation_id,
                "access_token": self.access_token,
            },
        )
        publish_response.raise_for_status()
        return str(publish_response.json()["id"])
