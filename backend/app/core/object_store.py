"""Optional S3-compatible object storage (MinIO or any S3 API).

Unset endpoint/bucket/keys means this is a no-op, which is what tests and
local runs without MinIO need. Object keys always start with
``tenants/{owner}/`` where owner is the same actor id the request path uses
for tenant isolation.
"""
from __future__ import annotations

import asyncio
import io
import logging
import re
from typing import Optional
from urllib.parse import urlparse

from app.config import settings

logger = logging.getLogger("sangam.storage")

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


class _UnsetType:
    pass


_UNSET = _UnsetType()


def _segment(value: str, fallback: str) -> str:
    piece = str(value or "").replace("\\", "_").replace("/", "_").replace("..", "_")
    piece = _SAFE.sub("_", piece).strip("._") or fallback
    return piece[:200]


def tenant_object_key(owner: str, *parts: str) -> str:
    safe_owner = _segment(owner, "unassigned")
    cleaned = [_segment(part, "object") for part in parts]
    return "tenants/" + "/".join([safe_owner, *cleaned])


def _put_sync(client, bucket: str, key: str, data: bytes, content_type: str) -> None:
    if hasattr(client, "bucket_exists") and not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    client.put_object(
        bucket,
        key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type or "application/octet-stream",
    )


class ObjectStore:
    def __init__(
        self,
        client=None,
        *,
        endpoint: Optional[str] = None,
        bucket: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self._client = client
        # _UNSET means "read the current setting", so a process started before
        # the environment is overridden (tests) does not keep a stale client.
        self._endpoint: Optional[str] | _UnsetType = _UNSET if endpoint is None else endpoint
        self._bucket: Optional[str] | _UnsetType = _UNSET if bucket is None else bucket
        self._access_key: Optional[str] | _UnsetType = _UNSET if access_key is None else access_key
        self._secret_key: Optional[str] | _UnsetType = _UNSET if secret_key is None else secret_key
        self._region: Optional[str] | _UnsetType = _UNSET if region is None else region

    @property
    def endpoint(self) -> Optional[str]:
        if isinstance(self._endpoint, _UnsetType):
            return settings.s3_endpoint_url
        return self._endpoint

    @property
    def bucket(self) -> Optional[str]:
        if isinstance(self._bucket, _UnsetType):
            return settings.s3_bucket
        return self._bucket

    @property
    def access_key(self) -> Optional[str]:
        if isinstance(self._access_key, _UnsetType):
            return settings.s3_access_key
        return self._access_key

    @property
    def secret_key(self) -> Optional[str]:
        if isinstance(self._secret_key, _UnsetType):
            return settings.s3_secret_key
        return self._secret_key

    @property
    def region(self) -> Optional[str]:
        if isinstance(self._region, _UnsetType):
            return settings.s3_region
        return self._region

    @property
    def enabled(self) -> bool:
        if self._client is not None:
            return bool(self.bucket)
        return bool(self.endpoint and self.bucket and self.access_key and self.secret_key)

    def build_client(self):
        from minio import Minio

        raw = self.endpoint or ""
        parsed = urlparse(raw if "://" in raw else f"http://{raw}")
        host = parsed.netloc or parsed.path
        secure = parsed.scheme == "https"
        kwargs = {
            "access_key": self.access_key or "",
            "secret_key": self.secret_key or "",
            "secure": secure,
        }
        if self.region:
            kwargs["region"] = self.region
        return Minio(host, **kwargs)

    async def put_bytes(
        self,
        *,
        owner: str,
        filename: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        document_id: str = "",
    ) -> Optional[str]:
        if not self.enabled:
            return None
        parts = tuple(p for p in (document_id, filename) if p)
        key = tenant_object_key(owner, *parts)
        client = self._client or self.build_client()
        bucket = self.bucket or ""
        await asyncio.to_thread(_put_sync, client, bucket, key, data, content_type)
        return key


object_store = ObjectStore()
