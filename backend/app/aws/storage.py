"""Lambda data access: mirror S3 into /tmp so the same file-based code runs locally and on AWS.

Reads: `sync_down()` copies new or changed objects under the given prefixes into data_dir. Many Lambda
containers serve the API, so every write bumps a small VERSION_KEY object: each request checks it with one
HEAD and re-syncs only when another container (or a pipeline job) has written since. Writes: `persist(rel)`
uploads data_dir/rel (a file or a whole dataset folder) back to S3, deletes objects the local folder no longer
has (partitioned datasets are rewritten whole) and bumps the version.
Locally (storage = "local") both are no-ops.
"""

import logging
import time
from pathlib import Path

from app.config import get_settings

log = logging.getLogger(__name__)
VERSION_KEY = "_version"
PREFIXES = ("processed/", "backtests/", "raw/news/")
_etags: dict[str, str] = {}
_seen_version: str | None = None


def _client():
    import boto3

    return boto3.client("s3")


def _objects(client, bucket: str, prefix: str):
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        yield from page.get("Contents", [])


def sync_down(prefixes: tuple[str, ...] = PREFIXES, force: bool = False) -> int:
    """Download new/changed objects. Returns how many files were fetched."""
    global _seen_version
    s = get_settings()
    if s.storage != "s3":
        return 0
    client, fetched = _client(), 0
    version = _version(client, s.s3_bucket)
    if not force and version == _seen_version:
        return 0
    for prefix in prefixes:
        for obj in _objects(client, s.s3_bucket, prefix):
            key, etag = obj["Key"], obj["ETag"]
            dest = s.data_dir / key
            if _etags.get(key) == etag and dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(s.s3_bucket, key, str(dest))
            _etags[key] = etag
            fetched += 1
    _seen_version = version
    return fetched


def _version(client, bucket: str) -> str:
    try:
        return client.head_object(Bucket=bucket, Key=VERSION_KEY)["ETag"]
    except client.exceptions.ClientError:
        return "none"


def _bump(client, bucket: str) -> None:
    client.put_object(Bucket=bucket, Key=VERSION_KEY, Body=str(time.time()).encode())


def persist(rel: str) -> None:
    """Upload data_dir/rel (file or folder) to the same key in S3, mirroring deletions inside a folder."""
    s = get_settings()
    if s.storage != "s3":
        return
    client, root = _client(), s.data_dir
    path = root / rel
    if path.is_file():
        client.upload_file(str(path), s.s3_bucket, rel)
        _bump(client, s.s3_bucket)
        return
    local = {str(p.relative_to(root)) for p in path.rglob("*") if p.is_file()}
    for key in local:
        client.upload_file(str(root / key), s.s3_bucket, key)
    stale = [o["Key"] for o in _objects(client, s.s3_bucket, rel.rstrip("/") + "/") if o["Key"] not in local]
    for i in range(0, len(stale), 1000):
        client.delete_objects(
            Bucket=s.s3_bucket, Delete={"Objects": [{"Key": k} for k in stale[i : i + 1000]]}
        )
    _bump(client, s.s3_bucket)
    log.info("persisted", extra={"fields": {"prefix": rel, "files": len(local), "deleted": len(stale)}})


def data_root() -> Path:
    return get_settings().data_dir
