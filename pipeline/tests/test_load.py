import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest  # noqa: E402
import pandas as pd  # noqa: E402
from unittest.mock import patch, MagicMock, call  # noqa: E402
from etl.load import (  # noqa: E402
    load_to_postgres, load_to_minio, get_postgres_engine, get_minio_client
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
            secret_key='***REMOVED***',
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
            secret_key='***REMOVED***',
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
                secret_key='***REMOVED***',
            )
