from __future__ import annotations

import base64

import httpx


class GitHubImageStorage:
    def __init__(
        self,
        *,
        repository: str,
        token: str,
        branch: str,
        path_prefix: str,
        public_base_url: str | None = None,
    ) -> None:
        self.repository = repository
        self.token = token
        self.branch = branch
        self.path_prefix = path_prefix.strip("/")
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None
        self._client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=120,
        )

    def upload_image(
        self,
        *,
        post_id: str,
        image_bytes: bytes,
        image_format: str = "jpeg",
    ) -> tuple[str, str]:
        extension = "jpg" if image_format == "jpeg" else image_format
        path = f"{self.path_prefix}/{post_id}.{extension}"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        response = self._client.put(
            f"/repos/{self.repository}/contents/{path}",
            json={
                "message": f"Add generated post image {post_id}",
                "content": encoded,
                "branch": self.branch,
            },
        )
        response.raise_for_status()
        return path, self._public_url(path)

    def _public_url(self, path: str) -> str:
        if self.public_base_url:
            return f"{self.public_base_url}/{path}"
        return f"https://raw.githubusercontent.com/{self.repository}/{self.branch}/{path}"
