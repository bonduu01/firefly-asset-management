import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_s3_client():
    """
    Return a boto3 S3 client.
    Reads connection config from environment variables so the same code works
    with both real AWS and LocalStack.
    """
    endpoint_url = os.environ.get("S3_ENDPOINT_URL")          # None → real AWS
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )


def _ensure_bucket(s3_client, bucket_name: str) -> None:
    """Create the S3 bucket if it does not already exist."""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"  🪣  Bucket '{bucket_name}' already exists")
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("404", "NoSuchBucket"):
            s3_client.create_bucket(Bucket=bucket_name)
            print(f"  🪣  Bucket '{bucket_name}' created")
        else:
            raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upload_report(
    local_path: str = None,
    bucket_name: str = None,
    s3_key: str = "comparison_report.json",
) -> dict:
    """
    Upload the comparison report JSON file to S3.

    Parameters
    ----------
    local_path  : path to the local report file.
                  Defaults to <project_root>/reports/comparison_report.json
    bucket_name : S3 bucket name. Defaults to the S3_BUCKET env var or
                  'firefly-reports'.
    s3_key      : object key inside the bucket.

    Returns
    -------
    dict with keys: bucket, key, local_path, endpoint
    """
    # ── Resolve defaults ──────────────────────────────────────────────────────
    if local_path is None:
        local_path = str(
            Path(__file__).parent.parent / "reports" / "comparison_report.json"
        )
    if bucket_name is None:
        bucket_name = os.environ.get("S3_BUCKET", "firefly-reports")

    report_file = Path(local_path)

    if not report_file.exists():
        raise FileNotFoundError(f"Report not found: {local_path}")
    if report_file.stat().st_size == 0:
        raise ValueError(f"Report file is empty: {local_path}")

    # ── Upload ────────────────────────────────────────────────────────────────
    s3 = _get_s3_client()
    _ensure_bucket(s3, bucket_name)

    s3.upload_file(
        Filename=str(report_file),
        Bucket=bucket_name,
        Key=s3_key,
        ExtraArgs={"ContentType": "application/json"},
    )

    endpoint = os.environ.get("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
    print(f"  📤 Uploaded → s3://{bucket_name}/{s3_key}")
    print(f"     Endpoint : {endpoint}")

    return {
        "bucket": bucket_name,
        "key": s3_key,
        "local_path": local_path,
        "endpoint": endpoint,
    }


def verify_upload(bucket_name: str = None, s3_key: str = "comparison_report.json") -> bool:
    """
    Verify that the uploaded object exists in S3 and is non-empty.

    Returns True if verification passes, raises an exception otherwise.
    """
    if bucket_name is None:
        bucket_name = os.environ.get("S3_BUCKET", "firefly-reports")

    s3 = _get_s3_client()
    response = s3.head_object(Bucket=bucket_name, Key=s3_key)
    size = response["ContentLength"]

    if size == 0:
        raise ValueError(f"Uploaded object is empty: s3://{bucket_name}/{s3_key}")

    print(f"  ✅ Verified s3://{bucket_name}/{s3_key}  ({size} bytes)")
    return True


# ---------------------------------------------------------------------------
# Run as a script:  python -m core.s3_uploader
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n🚀 Firefly S3 Uploader\n" + "-" * 40)
    result = upload_report()
    verify_upload(bucket_name=result["bucket"], s3_key=result["key"])
    print("\nDone ✅\n")