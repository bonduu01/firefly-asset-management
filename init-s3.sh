#!/bin/bash
awslocal s3 mb s3://firefly-reports --region us-east-1
awslocal s3api put-bucket-versioning \
  --bucket firefly-reports \
  --versioning-configuration Status=Enabled
