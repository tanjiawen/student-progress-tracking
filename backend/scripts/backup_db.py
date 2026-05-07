#!/usr/bin/env python3
"""Daily PostgreSQL backup to MinIO with 30-day retention."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from minio import Minio
from minio.error import S3Error

# Configuration
POSTGRES_USER = os.getenv("POSTGRES_USER", "student")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "progress_tracking")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
MINIO_BUCKET = os.getenv("BACKUP_BUCKET", "backups")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "/tmp/backups"))


def create_backup() -> Path:
    """Run pg_dump to create a backup file."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{POSTGRES_DB}_{timestamp}.sql.gz"
    filepath = BACKUP_DIR / filename

    env = os.environ.copy()
    env["PGPASSWORD"] = POSTGRES_PASSWORD

    cmd = [
        "pg_dump",
        "-h", POSTGRES_HOST,
        "-p", POSTGRES_PORT,
        "-U", POSTGRES_USER,
        "-d", POSTGRES_DB,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
    ]

    print(f"Creating backup: {filename}")
    with open(filepath, "wb") as f:
        dump_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env)
        gzip_proc = subprocess.Popen(["gzip", "-c"], stdin=dump_proc.stdout, stdout=f)
        dump_proc.stdout.close()
        gzip_proc.communicate()
        dump_proc.wait()

    if dump_proc.returncode != 0 or gzip_proc.returncode != 0:
        filepath.unlink(missing_ok=True)
        raise RuntimeError("pg_dump failed")

    print(f"Backup created: {filepath} ({filepath.stat().st_size} bytes)")
    return filepath


def upload_to_minio(filepath: Path) -> str:
    """Upload backup file to MinIO."""
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )

    # Ensure bucket exists
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)
        print(f"Created bucket: {MINIO_BUCKET}")

    object_name = f"db/{filepath.name}"
    client.fput_object(
        MINIO_BUCKET,
        object_name,
        str(filepath),
        content_type="application/gzip",
    )
    print(f"Uploaded to MinIO: {object_name}")
    return object_name


def cleanup_old_backups() -> None:
    """Remove backups older than RETENTION_DAYS."""
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    removed = 0

    try:
        objects = client.list_objects(MINIO_BUCKET, prefix="db/", recursive=False)
        for obj in objects:
            # Parse timestamp from filename: progress_tracking_20240115_120000.sql.gz
            if obj.last_modified < cutoff:
                client.remove_object(MINIO_BUCKET, obj.object_name)
                print(f"Removed old backup: {obj.object_name}")
                removed += 1
    except S3Error as e:
        print(f"Cleanup warning: {e}")

    print(f"Cleanup complete. Removed {removed} old backups.")


def main() -> int:
    """Run backup workflow."""
    if not POSTGRES_PASSWORD:
        print("ERROR: POSTGRES_PASSWORD not set", file=sys.stderr)
        return 1

    if not MINIO_ACCESS_KEY or not MINIO_SECRET_KEY:
        print("ERROR: MinIO credentials not set", file=sys.stderr)
        return 1

    try:
        filepath = create_backup()
        upload_to_minio(filepath)
        cleanup_old_backups()
        # Clean up local temp file
        filepath.unlink(missing_ok=True)
        print("Backup completed successfully.")
        return 0
    except Exception as e:
        print(f"ERROR: Backup failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
