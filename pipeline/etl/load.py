import io
import logging
from typing import Any

import boto3
import pandas as pd
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

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


def _insert_on_conflict_update(key_column: str):
    """Tạo hàm chèn cho `to_sql(method=...)`: INSERT ... ON CONFLICT DO UPDATE.

    Dòng trùng khoá thì cập nhật các cột còn lại thay vì chèn thêm. PostgreSQL
    tự khoá theo từng khoá, nên hai lần chạy ghi cùng lúc vẫn ra đúng một dòng.
    """
    def method(table, conn, keys, data_iter):
        rows = [dict(zip(keys, row)) for row in data_iter]
        stmt = pg_insert(table.table).values(rows)
        update_cols = {c: stmt.excluded[c] for c in keys if c != key_column}
        if update_cols:
            stmt = stmt.on_conflict_do_update(index_elements=[key_column], set_=update_cols)
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=[key_column])
        return conn.execute(stmt).rowcount
    return method


def upsert_dataframe(df: pd.DataFrame, table: str, conn_str: str,
                     key_column: str) -> int:
    """Ghi DataFrame vào bảng: dòng mới thì chèn, dòng trùng khoá thì cập nhật.

    Tự tạo bảng nếu chưa tồn tại, nên chạy được trên database trống — đây là
    kịch bản deploy lại từ đầu. Khoá được bảo đảm duy nhất bằng unique index,
    tạo ở lần ghi đầu tiên.

    Trước đây hàm dùng delete-insert trong một transaction. Cách đó đúng khi chỉ
    một tiến trình ghi, nhưng hai lần chạy DAG ghi cùng lúc (Airflow chạy bù sau
    khi hệ thống hồi phục) thì cả hai cùng xoá lúc chưa có gì để xoá rồi cùng
    chèn: ngày 17/09 và 19/09 bảng weather_hanoi bị nhân đôi theo đúng cách đó.

    Returns số dòng đã ghi.
    """
    engine = get_postgres_engine(conn_str)
    # ON CONFLICT không cho một câu lệnh đụng cùng một khoá hai lần.
    df = df.drop_duplicates(subset=[key_column], keep="last")
    try:
        with engine.begin() as conn:
            # to_sql với if_exists='append' tự tạo bảng nếu chưa có;
            # head(0) chỉ tạo cấu trúc, không chèn dòng nào.
            df.head(0).to_sql(table, conn, if_exists="append", index=False)
            # Chỉ tạo index khi chưa có. KHÔNG gọi thẳng CREATE ... IF NOT EXISTS
            # mỗi lần: lệnh đó vẫn khoá bảng dù index đã tồn tại, và hai lần ghi
            # đồng thời sẽ deadlock (đã thử trên PostgreSQL 15: 1 bên bị huỷ).
            # Bảng đang có dòng trùng thì lệnh tạo hỏng và task fail — cố ý:
            # phải dọn dữ liệu trước, không âm thầm ghi tiếp lên dữ liệu sai.
            index = f'uq_{table}_{key_column}'
            if conn.execute(text("SELECT to_regclass(:name)"),
                            {"name": f'"{index}"'}).scalar() is None:
                conn.execute(text(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS "{index}" '
                    f'ON "{table}" ("{key_column}")'
                ))
            df.to_sql(table, conn, if_exists="append", index=False,
                      method=_insert_on_conflict_update(key_column))
        logger.info("Upserted %d rows into '%s' on key '%s'", len(df), table, key_column)
        return len(df)
    except Exception as e:
        logger.error("Failed to upsert into '%s': %s", table, e)
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
