#!/bin/bash
set -e

echo "🪣  Creating Firefly S3 bucket..."

awslocal s3 mb s3://firefly-reports --region us-east-1

awslocal s3api put-bucket-versioning \
  --bucket firefly-reports \
  --versioning-configuration Status=Enabled

echo "✅ Bucket 'firefly-reports' is ready (versioning enabled)"