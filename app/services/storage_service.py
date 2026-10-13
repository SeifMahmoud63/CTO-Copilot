"""Central object storage: S3-compatible (S3Mock in compose, MinIO works too).
ALL files live here — nothing on disk.

Buckets (auto-created on first use):
- cto-reports      → daily CTO PDFs (daily-report-YYYY-MM-DD.pdf)
- mlflow-artifacts → Eval Lab artefacts (results.json, …)
- eval-progress    → fallback for eval X-of-Y progress if Redis is down

DB columns (e.g. daily_reports.pdf_path) store S3 URIs like:
    s3://cto-reports/daily-report-2026-10-12.pdf
Legacy local paths (/app/reports/….pdf, reports/….pdf) are still READ
for backward compat (old rows) but never WRITTEN anymore.
"""
from __future__ import annotations

import io
import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("cto-copilot.storage")


def parse_s3_uri(uri: str) -> Tuple[str, str]:
    """Split s3://bucket/key → (bucket, key). Raises ValueError on bad input."""
    if not uri or not uri.startswith("s3://"):
        raise ValueError(f"Not an S3 URI: {uri!r}")
    rest = uri[len("s3://"):]
    parts = rest.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Bad S3 URI (need s3://bucket/key): {uri!r}")
    return parts[0], parts[1]


def is_s3_uri(value: Optional[str]) -> bool:
    return bool(value and str(value).startswith("s3://"))


class StorageService:
    """Thin boto3 wrapper around MinIO. Lazy client (tests without MinIO still import)."""

    def __init__(self):
        self._client = None

    def _settings(self):
        from app.core.config import settings

        return settings

    def _s3_endpoint(self) -> str:
        s = self._settings()
        # Explicit MLflow endpoint wins, else the generic MinIO endpoint.
        return (getattr(s, "mlflow_s3_endpoint_url", "") or "").strip() or s.minio_endpoint.strip()

    def client(self):
        if self._client is not None:
            return self._client
        import boto3
        from botocore.config import Config

        s = self._settings()
        self._client = boto3.client(
            "s3",
            endpoint_url=self._s3_endpoint(),
            aws_access_key_id=s.minio_access_key,
            aws_secret_access_key=s.minio_secret_key,
            region_name="us-east-1",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                # Fast fallback when storage is down (tests / cold start):
                # one attempt, short timeouts — production retries live above us.
                connect_timeout=2, read_timeout=3,
                retries={"max_attempts": 1},
                # Checksums only when required — keeps compat S3 servers happy.
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
            use_ssl=bool(s.minio_secure),
        )
        return self._client

    def reset_client(self):
        """Forget cached client (tests / credential rotation)."""
        self._client = None

    # ---------- buckets ---------- #

    def all_buckets(self) -> List[str]:
        s = self._settings()
        return [s.minio_bucket_reports, s.minio_bucket_mlflow, s.minio_bucket_progress]

    def ensure_buckets(self) -> None:
        c = self.client()
        for bucket in self.all_buckets():
            try:
                c.head_bucket(Bucket=bucket)
            except Exception:
                try:
                    c.create_bucket(Bucket=bucket)
                    logger.info(f"Created S3 bucket: {bucket}")
                except Exception as e:
                    # Already exists (race) → fine, anything else → warn loudly.
                    if "BucketAlreadyOwnedByYou" in str(e) or "BucketAlreadyExists" in str(e):
                        pass
                    else:
                        logger.warning(f"ensure bucket {bucket} failed: {e}")

    # ---------- objects ---------- #

    def upload_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload → returns s3://bucket/key URI."""
        self.ensure_buckets()
        self.client().put_object(
            Bucket=bucket, Key=key, Body=data,
            ContentType=content_type,
        )
        return f"s3://{bucket}/{key}"

    def download_bytes(self, bucket: str, key: str) -> bytes:
        resp = self.client().get_object(Bucket=bucket, Key=key)
        return resp["Body"].read()

    def download_uri(self, uri: str) -> bytes:
        bucket, key = parse_s3_uri(uri)
        return self.download_bytes(bucket, key)

    def exists(self, bucket: str, key: str) -> bool:
        try:
            self.client().head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    def exists_uri(self, uri: str) -> bool:
        try:
            bucket, key = parse_s3_uri(uri)
            return self.exists(bucket, key)
        except Exception:
            return False

    def delete(self, bucket: str, key: str) -> bool:
        try:
            self.client().delete_object(Bucket=bucket, Key=key)
            return True
        except Exception as e:
            logger.warning(f"MinIO delete s3://{bucket}/{key} failed: {e}")
            return False

    def list_keys(self, bucket: str, prefix: str = "") -> List[str]:
        out: List[str] = []
        try:
            paginator = self.client().get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []) or []:
                    out.append(obj["Key"])
        except Exception as e:
            logger.warning(f"MinIO list s3://{bucket}/{prefix} failed: {e}")
        return out

    # ---------- report helpers ---------- #

    def report_key(self, day: str) -> str:
        return f"daily-report-{day}.pdf"

    def upload_report(self, day: str, pdf_bytes: bytes) -> str:
        s = self._settings()
        return self.upload_bytes(
            s.minio_bucket_reports, self.report_key(day),
            pdf_bytes, content_type="application/pdf",
        )

    def download_report(self, day_or_uri: str) -> bytes:
        """Accept a full s3:// URI or a bare YYYY-MM-DD day."""
        if is_s3_uri(day_or_uri):
            return self.download_uri(day_or_uri)
        s = self._settings()
        return self.download_bytes(s.minio_bucket_reports, self.report_key(day_or_uri))

    def report_exists(self, day_or_uri: str) -> bool:
        if is_s3_uri(day_or_uri):
            return self.exists_uri(day_or_uri)
        s = self._settings()
        return self.exists(s.minio_bucket_reports, self.report_key(day_or_uri))

    # ---------- legacy local-file bridge ---------- #

    def read_any_path(self, path_or_uri: str) -> bytes:
        """Read from MinIO (s3://…) or legacy local disk path. Never writes to disk."""
        if is_s3_uri(path_or_uri):
            return self.download_uri(path_or_uri)
        # Backward compat: rows created before the MinIO migration.
        if os.path.exists(path_or_uri):
            with open(path_or_uri, "rb") as f:
                return f.read()
        raise FileNotFoundError(f"Report file not found: {path_or_uri}")

    def exists_any_path(self, path_or_uri: Optional[str]) -> bool:
        if not path_or_uri:
            return False
        if is_s3_uri(path_or_uri):
            return self.exists_uri(path_or_uri)
        return os.path.exists(path_or_uri)


storage_service = StorageService()
