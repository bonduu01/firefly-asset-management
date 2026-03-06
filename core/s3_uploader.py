import os
import json
import boto3
from pathlib import Path
from botocore.exceptions import ClientError


def get_s3_client():
    """
    Returns a boto3 S3 client.
    Uses S3_ENDPOINT_URL env var to point at LocalStack when set.
    """
    endpoint_url = os.environ.get("S3_ENDPOINT_URL")  # e.g. http://localhost:4566
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )


def ensure_bucket_exists(s3_client, bucket_name: str):
    """Creates the S3 bucket if it does not already exist."""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"✅ Bucket '{bucket_name}' already exists")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ("404", "NoSuchBucket"):
            s3_client.create_bucket(Bucket=bucket_name)
            print(f"🪣  Bucket '{bucket_name}' created")
        else:
            raise


def upload_report(
    local_path: str = None,
    bucket_name: str = None,
    s3_key: str = "comparison_report.json"
):
    """
    Uploads the comparison report JSON file to S3.

    Args:
        local_path:  Path to the local JSON report file.
        bucket_name: Target S3 bucket name.
        s3_key:      Key (filename) to use in S3.
    """
    # Resolve defaults from environment / project structure
    if local_path is None:
        local_path = str(Path(__file__).parent.parent / "reports" / "comparison_report.json")
    if bucket_name is None:
        bucket_name = os.environ.get("S3_BUCKET", "firefly-reports")

    report_file = Path(local_path)
    if not report_file.exists():
        raise FileNotFoundError(f"Report not found at: {local_path}")
    if report_file.stat().st_size == 0:
        raise ValueError(f"Report file is empty: {local_path}")

    s3 = get_s3_client()
    ensure_bucket_exists(s3, bucket_name)

    s3.upload_file(
        Filename=str(report_file),
        Bucket=bucket_name,
        Key=s3_key,
        ExtraArgs={"ContentType": "application/json"}
    )

    endpoint = os.environ.get("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
    print(f"📤 Report uploaded → s3://{bucket_name}/{s3_key}")
    print(f"   Endpoint: {endpoint}/{bucket_name}/{s3_key}")

    return {
        "bucket": bucket_name,
        "key": s3_key,
        "local_path": local_path,
        "endpoint": endpoint,
    }


def verify_upload(bucket_name: str = None, s3_key: str = "comparison_report.json"):
    """Verifies the uploaded file exists and is non-empty in S3."""
    if bucket_name is None:
        bucket_name = os.environ.get("S3_BUCKET", "firefly-reports")

    s3 = get_s3_client()
    response = s3.head_object(Bucket=bucket_name, Key=s3_key)
    size = response["ContentLength"]

    print(f"✅ Verified: s3://{bucket_name}/{s3_key} ({size} bytes)")
    return size > 0


# ── Run as a standalone script ────────────────────────────────────────────────
if __name__ == "__main__":
    result = upload_report()
    verify_upload(bucket_name=result["bucket"], s3_key=result["key"])