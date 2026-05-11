from __future__ import annotations

import boto3


class R2Client:
    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        public_base_url: str,
    ) -> None:
        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def upload_image(
        self,
        *,
        post_id: str,
        image_bytes: bytes,
        image_format: str = "jpeg",
    ) -> tuple[str, str]:
        extension = "jpg" if image_format == "jpeg" else image_format
        content_type = "image/jpeg" if image_format == "jpeg" else f"image/{image_format}"
        key = f"posts/{post_id}.{extension}"
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=image_bytes,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
        return key, f"{self.public_base_url}/{key}"
