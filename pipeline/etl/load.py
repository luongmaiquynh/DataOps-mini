import io
import logging
from typing import Any

import boto3
import pandas as pd
from botocore.exceptions import ClientError
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)


def get_postgres_engine(conn_str: str):
    """Tạo SQLAlchemy engine kết nối PostgreSQL."""
    return create_engine(conn_str)


def load_to_postgres(df: pd.DataFrame, table: str, conn_str: str, if_exists: str = "append") -> int:
    """Lưu DataFrame vào bảng PostgreSQL.

    Returns number of rows written.
    """
    engine = get_postgres_engine(conn_str)
    try:
        df.to_sql(table, engine, if_exists=if_exists, index=False)
        logger.info("Loaded %d rows into PostgreSQL table '%s'", len(df), table)
        return len(df)
    except Exception as e:
        logger.error("Failed to load data into PostgreSQL table '%s': %s", table, e)
        raise


def get_minio_client(endpoint: str, access_key: str, secret_key: str):
    """Tạo boto3 S3 client cho MinIO (S3-compatible)."""
    return boto3.client(
        "s3",
        endpoint_url=f"http://{endpoint}",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def load_to_minio(df: pd.DataFrame, bucket: str, object_name: str,
                  endpoint: str, access_key: str, secret_key: str) -> None:
    """Upload DataFrame dưới dạng CSV lên MinIO.

    object_name: ví dụ 'raw/employees/2026-05-11.csv'
    """
    client = get_minio_client(endpoint, access_key, secret_key)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    body = csv_buffer.getvalue().encode("utf-8")
    try:
        client.put_object(Bucket=bucket, Key=object_name, Body=body)
        logger.info("Uploaded %d rows to s3://%s/%s", len(df), bucket, object_name)
    except ClientError as e:
        logger.error("MinIO upload failed: %s", e)
        raise
