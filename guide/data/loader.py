"""Dataset readers: local directory or Amazon S3 (Req. 8.5, 8.6)."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Protocol

import pandas as pd

from guide.config import Config


class DataSource(Protocol):
    def read_csv(self, name: str) -> pd.DataFrame: ...


class LocalSource:
    """Reads Dataset files from a local directory (default /workshop/Agent52/data)."""

    def __init__(self, data_dir: str | Path = "/workshop/Agent52/data") -> None:
        self.data_dir = Path(data_dir)

    def read_csv(self, name: str) -> pd.DataFrame:
        return pd.read_csv(self.data_dir / name)


class S3Source:
    """Reads ``s3://{bucket}/{prefix}/{name}``. Uses the default AWS credential chain."""

    def __init__(self, bucket: str, prefix: str = "", client=None, region: str | None = None) -> None:
        if not bucket:
            raise ValueError("S3 bucket is not configured")
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        if client is None:
            import boto3

            client = boto3.client("s3", region_name=region)
        self._client = client

    def key(self, name: str) -> str:
        return f"{self.prefix}/{name}" if self.prefix else name

    def read_csv(self, name: str) -> pd.DataFrame:
        obj = self._client.get_object(Bucket=self.bucket, Key=self.key(name))
        return pd.read_csv(io.BytesIO(obj["Body"].read()))


def get_source(config: Config, client=None) -> DataSource:
    if config.data_location == "s3":
        return S3Source(config.s3_bucket, config.s3_prefix, client=client, region=config.aws_region)
    return LocalSource(config.data_dir)
