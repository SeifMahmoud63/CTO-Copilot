"""Create S3 buckets on the object-storage service (S3Mock/MinIO), waiting for readiness.

Used by the `storage-init` compose service (runs on the already-built app image,
so no extra image pulls) and locally via `python scripts/ensure_buckets.py`.
"""
import sys
import time

sys.path.insert(0, "/app")

from app.services.storage_service import storage_service  # noqa: E402


def main() -> None:
    for attempt in range(1, 31):
        try:
            storage_service.ensure_buckets()
            # Explicit verification (head_bucket raises when missing).
            for bucket in storage_service.all_buckets():
                storage_service.client().head_bucket(Bucket=bucket)
            print(f"S3 buckets ready: {storage_service.all_buckets()}", flush=True)
            return
        except Exception as exc:
            print(f"[{attempt}/30] storage not ready yet: {exc}", flush=True)
            time.sleep(2)
    raise SystemExit("S3 storage did not become ready in time.")


if __name__ == "__main__":
    main()
