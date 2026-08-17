import base64
import binascii
import re
import secrets
from pathlib import Path

import anyio
import boto3

from ..config import get_settings
from ..schemas import ImagePayload

ALLOWED_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}


def _upload(payload: ImagePayload, product_id: int) -> str:
    settings = get_settings()
    if not settings.s3_bucket:
        raise ValueError("Object storage is not configured")
    match = re.fullmatch(r"data:([^;,]+);base64,(.+)", payload.data_url, flags=re.DOTALL)
    if not match or match.group(1) not in ALLOWED_TYPES:
        raise ValueError("Unsupported image format")
    try:
        data = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid image encoding") from exc
    if not data or len(data) > 8 * 1024 * 1024:
        raise ValueError("Image must be between 1 byte and 8 MB")
    extension = ALLOWED_TYPES[match.group(1)]
    clean_stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", Path(payload.name).stem).strip("-")[:40] or "image"
    key = f"products/{product_id}/{secrets.token_hex(8)}-{clean_stem}{extension}"
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id or None,
        aws_secret_access_key=settings.s3_secret_access_key or None,
    )
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=data,
        ContentType=match.group(1),
        CacheControl="public, max-age=31536000, immutable",
    )
    origin = settings.asset_origin.rstrip("/")
    return f"{origin}/{key}" if origin else key


async def upload_product_image(product_id: int, payload: ImagePayload) -> dict:
    return {"url": await anyio.to_thread.run_sync(_upload, payload, product_id)}
