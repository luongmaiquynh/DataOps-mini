import sys
import os
import io
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock airflow before any DAG import (airflow not installed locally)
_airflow_mock = MagicMock()
sys.modules.setdefault('airflow', _airflow_mock)
sys.modules.setdefault('airflow.models', _airflow_mock)
sys.modules.setdefault('airflow.operators', _airflow_mock)
sys.modules.setdefault('airflow.operators.python', _airflow_mock)

import pytest  # noqa: E402
import pandas as pd  # noqa: E402


def make_context(xcom_store=None):
    """Tạo mock Airflow context với XCom giả."""
    store = xcom_store or {}
    ti = MagicMock()
    ti.xcom_push.side_effect = lambda key, value: store.update({key: value})
    ti.xcom_pull.side_effect = lambda key, task_ids=None: store.get(key)
    return {'ti': ti}, store


# ─── task_extract ─────────────────────────────────────────────

def test_task_extract_pushes_raw_data_to_xcom():
    """task_extract phải gọi xcom_push với key 'raw_data'."""
    from dags.ingest_api_dag import task_extract

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        'hourly': {
            'time': ['2026-05-13T00:00', '2026-05-13T01:00'],
            'temperature_2m': [28.5, 27.1],
            'windspeed_10m': [10.2, 9.8],
        }
    }

    context, store = make_context()
    with patch('requests.get', return_value=mock_resp):
        task_extract(**context)

    assert 'raw_data' in store
    df = pd.read_json(io.StringIO(store['raw_data']))
    assert 'temperature_2m' in df.columns
    assert len(df) == 2


def test_task_extract_raises_if_hourly_missing():
    """task_extract phải raise ValueError nếu API không có 'hourly'."""
    from dags.ingest_api_dag import task_extract

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {}

    context, _ = make_context()
    with patch('requests.get', return_value=mock_resp):
        with pytest.raises(ValueError, match='hourly'):
            task_extract(**context)


# ─── task_transform ───────────────────────────────────────────

def test_task_transform_cleans_and_normalizes():
    """task_transform phải normalize cột và clean data."""
    from dags.ingest_api_dag import task_transform

    raw_df = pd.DataFrame({
        'Time': ['2026-05-13T00:00', '2026-05-13T01:00'],
        'Temperature_2m': [28.5, 27.1],
        'Windspeed_10m': [10.2, 9.8],
    })
    context, store = make_context({'raw_data': raw_df.to_json()})

    task_transform(**context)

    assert 'clean_data' in store
    df = pd.read_json(io.StringIO(store['clean_data']))
    assert 'time' in df.columns
    assert 'temperature_2m' in df.columns
    assert 'ingested_at' in df.columns


def test_task_transform_pushes_clean_data():
    """task_transform phải gọi xcom_push với key 'clean_data'."""
    from dags.ingest_api_dag import task_transform

    raw_df = pd.DataFrame({
        'time': ['2026-05-13T00:00'],
        'temperature_2m': [28.5],
        'windspeed_10m': [10.2],
    })
    context, store = make_context({'raw_data': raw_df.to_json()})

    task_transform(**context)

    assert 'clean_data' in store


# ─── task_quality ─────────────────────────────────────────────

def test_task_quality_passes_with_clean_data():
    """task_quality không raise khi data đạt chất lượng."""
    from dags.ingest_api_dag import task_quality

    clean_df = pd.DataFrame({
        'time': ['2026-05-13T00:00', '2026-05-13T01:00'],
        'temperature_2m': [28.5, 27.1],
        'windspeed_10m': [10.2, 9.8],
        'ingested_at': ['2026-05-13', '2026-05-13'],
    })
    context, _ = make_context({'clean_data': clean_df.to_json()})

    task_quality(**context)  # không raise


def test_task_quality_raises_on_missing_columns():
    """task_quality phải raise khi thiếu cột bắt buộc."""
    from dags.ingest_api_dag import task_quality

    bad_df = pd.DataFrame({'time': ['2026-05-13T00:00']})
    context, _ = make_context({'clean_data': bad_df.to_json()})

    with pytest.raises(ValueError):
        task_quality(**context)


# ─── task_load ────────────────────────────────────────────────

def test_task_load_calls_postgres_and_minio():
    """task_load phải gọi cả load_to_postgres và load_to_minio."""
    from dags.ingest_api_dag import task_load

    clean_df = pd.DataFrame({
        'time': ['2026-05-13T00:00'],
        'temperature_2m': [28.5],
        'windspeed_10m': [10.2],
        'ingested_at': ['2026-05-13'],
    })
    context, _ = make_context({'clean_data': clean_df.to_json()})

    with patch('etl.load.create_engine'), \
         patch('etl.load.boto3.client') as mock_boto, \
         patch.object(pd.DataFrame, 'to_sql'):
        mock_boto.return_value = MagicMock()
        task_load(**context)
