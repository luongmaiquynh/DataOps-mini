import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest  # noqa: E402
import pandas as pd  # noqa: E402
from unittest.mock import patch, MagicMock, call  # noqa: E402
from etl.load import (  # noqa: E402
    load_to_postgres, load_to_minio, get_postgres_engine, get_minio_client,
    upsert_dataframe
)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        'id': [1, 2, 3],
        'name': ['An', 'Binh', 'Cuong'],
        'salary': [1000.0, 2000.0, 1500.0],
    })


# ─── get_postgres_engine ─────────────────────────────────────

def test_get_postgres_engine_returns_engine():
    """Phải trả về SQLAlchemy engine từ connection string."""
    with patch('etl.load.create_engine') as mock_create:
        mock_create.return_value = MagicMock()
        engine = get_postgres_engine('postgresql://user:pass@localhost/db')
        mock_create.assert_called_once_with('postgresql://user:pass@localhost/db')
        assert engine is not None


# ─── load_to_postgres ─────────────────────────────────────────

def test_load_to_postgres_returns_row_count(sample_df):
    """Phải trả về số rows đã load."""
    with patch('etl.load.create_engine') as mock_engine:
        mock_engine.return_value = MagicMock()
        with patch.object(pd.DataFrame, 'to_sql'):
            result = load_to_postgres(sample_df, 'employees', 'postgresql://x/y')
            assert result == 3


def test_load_to_postgres_calls_to_sql_with_correct_args(sample_df):
    """to_sql phải được gọi với table name và if_exists đúng."""
    with patch('etl.load.create_engine') as mock_engine:
        engine_instance = MagicMock()
        mock_engine.return_value = engine_instance
        with patch.object(pd.DataFrame, 'to_sql') as mock_to_sql:
            load_to_postgres(sample_df, 'test_table', 'postgresql://x/y',
                             if_exists='replace')
            mock_to_sql.assert_called_once_with(
                'test_table', engine_instance,
                if_exists='replace', index=False
            )


def test_load_to_postgres_default_if_exists_is_append(sample_df):
    """if_exists mặc định phải là 'append'."""
    with patch('etl.load.create_engine') as mock_engine:
        mock_engine.return_value = MagicMock()
        with patch.object(pd.DataFrame, 'to_sql') as mock_to_sql:
            load_to_postgres(sample_df, 'tbl', 'postgresql://x/y')
            _, kwargs = mock_to_sql.call_args
            assert kwargs['if_exists'] == 'append'


# ─── get_minio_client ─────────────────────────────────────────

def test_get_minio_client_returns_client():
    """Phải trả về boto3 S3 client đúng endpoint."""
    with patch('etl.load.boto3.client') as mock_client:
        mock_client.return_value = MagicMock()
        client = get_minio_client('192.168.64.3:9000', 'user', 'pass')
        mock_client.assert_called_once_with(
            's3',
            endpoint_url='http://192.168.64.3:9000',
            aws_access_key_id='user',
            aws_secret_access_key='pass',
        )
        assert client is not None


# ─── load_to_minio ────────────────────────────────────────────

def test_load_to_minio_calls_put_object(sample_df):
    """Phải gọi put_object với đúng bucket và key."""
    mock_client = MagicMock()
    with patch('etl.load.get_minio_client', return_value=mock_client):
        load_to_minio(
            sample_df,
            bucket='dataops-lake',
            object_name='raw/employees/2026-05-13.csv',
            endpoint='192.168.64.3:9000',
            access_key='minioadmin',
            secret_key='test-secret-key',
        )
        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args[1]
        assert call_kwargs['Bucket'] == 'dataops-lake'
        assert call_kwargs['Key'] == 'raw/employees/2026-05-13.csv'


def test_load_to_minio_uploads_csv_content(sample_df):
    """Body upload phải là CSV bytes hợp lệ."""
    mock_client = MagicMock()
    with patch('etl.load.get_minio_client', return_value=mock_client):
        load_to_minio(
            sample_df,
            bucket='dataops-lake',
            object_name='raw/test.csv',
            endpoint='192.168.64.3:9000',
            access_key='minioadmin',
            secret_key='test-secret-key',
        )
        body = mock_client.put_object.call_args[1]['Body']
        assert isinstance(body, bytes)
        content = body.decode('utf-8')
        assert 'id' in content
        assert 'An' in content


def test_load_to_minio_raises_on_client_error(sample_df):
    """Phải raise ClientError khi MinIO trả về lỗi."""
    from botocore.exceptions import ClientError
    mock_client = MagicMock()
    mock_client.put_object.side_effect = ClientError(
        {'Error': {'Code': 'NoSuchBucket', 'Message': 'bucket not found'}},
        'PutObject'
    )
    with patch('etl.load.get_minio_client', return_value=mock_client):
        with pytest.raises(ClientError):
            load_to_minio(
                sample_df,
                bucket='nonexistent-bucket',
                object_name='test.csv',
                endpoint='192.168.64.3:9000',
                access_key='minioadmin',
                secret_key='test-secret-key',
            )


# ─── upsert_dataframe ─────────────────────────────────────────

def _mock_engine_with_conn():
    """Trả về (patcher create_engine, connection giả trong transaction)."""
    conn = MagicMock()
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn
    return engine, conn


def test_upsert_dataframe_returns_row_count(sample_df):
    """Phải trả về số dòng đã ghi."""
    engine, _ = _mock_engine_with_conn()
    with patch('etl.load.create_engine', return_value=engine):
        with patch.object(pd.DataFrame, 'to_sql'):
            result = upsert_dataframe(sample_df, 'employees', 'postgresql://x/y', 'id')
    assert result == 3


def test_upsert_dataframe_creates_table_before_insert(sample_df):
    """Gọi to_sql hai lần: một lần tạo cấu trúc bảng, một lần chèn dữ liệu."""
    engine, _ = _mock_engine_with_conn()
    with patch('etl.load.create_engine', return_value=engine):
        with patch.object(pd.DataFrame, 'to_sql') as mock_to_sql:
            upsert_dataframe(sample_df, 'employees', 'postgresql://x/y', 'id')
    assert mock_to_sql.call_count == 2


def test_upsert_dataframe_creates_unique_index_when_missing(sample_df):
    """Chưa có index thì tạo: khoá được bảo đảm duy nhất ở phía database."""
    engine, conn = _mock_engine_with_conn()
    conn.execute.return_value.scalar.return_value = None  # to_regclass: chưa có
    with patch('etl.load.create_engine', return_value=engine):
        with patch.object(pd.DataFrame, 'to_sql'):
            upsert_dataframe(sample_df, 'employees', 'postgresql://x/y', 'id')
    assert conn.execute.call_count == 2
    sql = str(conn.execute.call_args_list[1][0][0])
    assert 'CREATE UNIQUE INDEX IF NOT EXISTS' in sql
    assert '"uq_employees_id"' in sql and '("id")' in sql


def test_upsert_dataframe_skips_index_ddl_when_present(sample_df):
    """Index đã có thì không chạy DDL: CREATE ... IF NOT EXISTS vẫn khoá bảng
    và làm hai lần ghi đồng thời deadlock."""
    engine, conn = _mock_engine_with_conn()
    conn.execute.return_value.scalar.return_value = 'uq_employees_id'
    with patch('etl.load.create_engine', return_value=engine):
        with patch.object(pd.DataFrame, 'to_sql'):
            upsert_dataframe(sample_df, 'employees', 'postgresql://x/y', 'id')
    conn.execute.assert_called_once()
    assert 'to_regclass' in str(conn.execute.call_args[0][0])


def test_upsert_dataframe_inserts_with_on_conflict_method(sample_df):
    """Lần to_sql thứ hai (chèn dữ liệu) phải dùng hàm chèn ON CONFLICT."""
    engine, _ = _mock_engine_with_conn()
    with patch('etl.load.create_engine', return_value=engine):
        with patch.object(pd.DataFrame, 'to_sql') as mock_to_sql:
            upsert_dataframe(sample_df, 'employees', 'postgresql://x/y', 'id')
    assert 'method' not in mock_to_sql.call_args_list[0][1]
    assert callable(mock_to_sql.call_args_list[1][1]['method'])


def test_upsert_dataframe_drops_duplicate_keys_in_batch():
    """Cùng một khoá xuất hiện hai lần trong lô thì chỉ giữ bản sau cùng."""
    df = pd.DataFrame({'id': [1, 1, 2], 'name': ['cu', 'moi', 'b']})
    engine, _ = _mock_engine_with_conn()
    with patch('etl.load.create_engine', return_value=engine):
        with patch.object(pd.DataFrame, 'to_sql'):
            result = upsert_dataframe(df, 'employees', 'postgresql://x/y', 'id')
    assert result == 2


def _compiled_on_conflict_sql(columns, key_column):
    """Chạy hàm chèn trên một bảng giả, trả về câu SQL PostgreSQL nó sinh ra."""
    from sqlalchemy import Column, Integer, MetaData, Table
    from sqlalchemy.dialects import postgresql
    from etl.load import _insert_on_conflict_update
    sa_table = Table('t', MetaData(), *[Column(c, Integer) for c in columns])
    pd_table = MagicMock()
    pd_table.table = sa_table
    conn = MagicMock()
    _insert_on_conflict_update(key_column)(pd_table, conn, columns, iter([(1,) * len(columns)]))
    stmt = conn.execute.call_args[0][0]
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_on_conflict_method_updates_non_key_columns():
    """Trùng khoá thì cập nhật các cột còn lại, không chèn thêm dòng."""
    sql = _compiled_on_conflict_sql(['id', 'name'], 'id')
    assert 'ON CONFLICT (id) DO UPDATE SET name = excluded.name' in sql


def test_on_conflict_method_does_nothing_when_only_key_column():
    """Bảng chỉ có cột khoá thì không có gì để cập nhật: bỏ qua dòng trùng."""
    sql = _compiled_on_conflict_sql(['id'], 'id')
    assert 'ON CONFLICT (id) DO NOTHING' in sql


def test_upsert_dataframe_runs_in_single_transaction(sample_df):
    """Toàn bộ thao tác nằm trong một engine.begin() duy nhất."""
    engine, _ = _mock_engine_with_conn()
    with patch('etl.load.create_engine', return_value=engine):
        with patch.object(pd.DataFrame, 'to_sql'):
            upsert_dataframe(sample_df, 'employees', 'postgresql://x/y', 'id')
    engine.begin.assert_called_once()


def test_upsert_dataframe_raises_on_db_error(sample_df):
    """Lỗi database phải được ném ra để Airflow đánh dấu task fail."""
    engine, conn = _mock_engine_with_conn()
    conn.execute.side_effect = RuntimeError('connection lost')
    with patch('etl.load.create_engine', return_value=engine):
        with patch.object(pd.DataFrame, 'to_sql'):
            with pytest.raises(RuntimeError):
                upsert_dataframe(sample_df, 'employees', 'postgresql://x/y', 'id')
