import pandas as pd
import logging
import io
import boto3
from sqlalchemy import create_engine
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def get_postgres_engine(conn_str: str):
    """Tạo SQLAlchemy engine kết nối PostgreSQL."""
    return create_engine(conn_str)


def load_to_postgres(df: pd.DataFrame, table: str, conn_str: str, if_exists: str = 'append') -> int:
    """Lưu DataFrame vào bảng PostgreSQL.

    if_exists: 'append' (thêm vào) | 'replace' (ghi đè) | 'fail'
    """
    engine = get_postgres_engine(conn_str)
    df.to_sql(table, engine, if_exists=if_exists, index=False)
    logger.info(f"Loaded {len(df)} rows into PostgreSQL table '{table}'")
    return len(df)


def get_minio_client(endpoint: str, access_key: str, secret_key: str):
    """Tạo boto3 client kết nối MinIO."""
    return boto3.client(
        's3',
        endpoint_url=f'http://{endpoint}',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def load_to_minio(df: pd.DataFrame, bucket: str, object_name: str,
                  endpoint: str, access_key: str, secret_key: str) -> None:
    """Upload DataFrame dưới dạng CSV lên MinIO (S3-compatible).

    object_name: đường dẫn trong bucket, ví dụ 'raw/employees/2026-05-11.csv'
    """
    client = get_minio_client(endpoint, access_key, secret_key)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    body = csv_buffer.getvalue().encode('utf-8')
    try:
        client.put_object(Bucket=bucket, Key=object_name, Body=body)
        logger.info(f"Uploaded {len(df)} rows to s3://{bucket}/{object_name}")
    except ClientError as e:
        logger.error(f"MinIO upload failed: {e}")
        raise
