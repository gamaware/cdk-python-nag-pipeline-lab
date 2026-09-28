"""Sample Lambda handler: counts objects in the data bucket, up to 100."""

import json
import os

import boto3

s3 = boto3.client("s3")


def handler(event, context):
    bucket = os.environ["BUCKET_NAME"]
    response = s3.list_objects_v2(Bucket=bucket, MaxKeys=100)
    body = {"bucket": bucket, "objects": response.get("KeyCount", 0)}
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
