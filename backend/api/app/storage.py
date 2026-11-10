from pathlib import PurePosixPath

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


class ObjectStorage:
    def __init__(
        self,
        endpoint: str,
        public_endpoint: str,
        access_key: str,
        secret_key: str,
        allowed_origins: list[str] | None = None,
    ):
        self.allowed_origins = allowed_origins
        options = dict(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=3,
                read_timeout=10,
                retries={"max_attempts": 2},
            ),
        )
        self.client = boto3.client("s3", endpoint_url=endpoint, **options)
        self.signer = boto3.client("s3", endpoint_url=public_endpoint, **options)

    def initialize(self):
        for bucket in ("legal", "private"):
            try:
                self.client.create_bucket(Bucket=bucket)
            except ClientError as exc:
                if exc.response["Error"]["Code"] not in (
                    "BucketAlreadyOwnedByYou",
                    "BucketAlreadyExists",
                ):
                    raise

        if self.allowed_origins:
            self.client.put_bucket_cors(
                Bucket="legal",
                CORSConfiguration={
                    "CORSRules": [
                        {
                            "AllowedOrigins": self.allowed_origins,
                            "AllowedMethods": ["GET", "HEAD"],
                            "AllowedHeaders": ["Accept", "Range"],
                            "ExposeHeaders": ["ETag"],
                            "MaxAgeSeconds": 300,
                        }
                    ]
                },
            )

    @staticmethod
    def validate_key(key):
        if not key or key.startswith("/") or ".." in PurePosixPath(key).parts or "\\" in key:
            raise ValueError("Invalid object key")

    def put(self, key: str, body: bytes, content_type: str, private: bool) -> str:
        self.validate_key(key)
        self.client.put_object(
            Bucket="private" if private else "legal", Key=key, Body=body, ContentType=content_type
        )
        return key

    def signed_get(self, key: str, private: bool) -> str:
        self.validate_key(key)
        return self.signer.generate_presigned_url(
            "get_object",
            Params={"Bucket": "private" if private else "legal", "Key": key},
            ExpiresIn=300,
        )

    def get(self, key: str, private: bool) -> bytes:
        self.validate_key(key)
        return self.client.get_object(Bucket="private" if private else "legal", Key=key)[
            "Body"
        ].read()
