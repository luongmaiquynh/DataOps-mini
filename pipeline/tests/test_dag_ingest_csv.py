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
    store = xcom_store or {}
    ti = MagicMock()
    ti.xcom_push.side_effect = lambda key, value: store.update({key: value})
    ti.xcom_pull.side_effect = lambda key, task_ids=None: store.get(key)
    return {'ti': ti}, store


SAMPLE_DF = pd.DataFrame({
    'id':         [1, 2, 3, 1, 4, 5],
    'name':       ['Nguyen Van A', 'Tran Thi B', 'Le Van C',
                   'Nguyen Van A', 'Pham Thi D', 'Hoang Van E'],
    'age':        [25, 30, 28, 25, None, 35],
    'city':       ['Hanoi', 'HCMC', 'Hanoi', 'Hanoi', 'Danang', 'HCMC'],
    'salary':     [15e6, 20e6, 18e6, 15e6, 12e6, None],
    'created_at': ['2026-01-01'] * 6,
})


# ─── task_extract ─────────────────────────────────────────────

def test_task_extract_reads_csv_and_pushes_xcom():
    """task_extract phải đọc CSV và push raw_data lên XCom."""
    from dags.ingest_csv_dag import task_extract

    context, store = make_context()
    with patch('etl.extract.pd.read_csv', return_value=SAMPLE_DF):
        task_extract(**context)

    assert 'raw_data' in store
    df = pd.read_json(io.StringIO(store['raw_data']))
    assert len(df) == 6
    assert 'name' in df.columns


def test_task_extract_raises_if_csv_missing():
    """task_extract phải raise FileNotFoundError nếu CSV không tồn tại."""
    from dags.ingest_csv_dag import task_extract

    context, _ = make_context()
    with patch('etl.extract.pd.read_csv',
               side_effect=FileNotFoundError('not found')):
        with pytest.raises(FileNotFoundError):
            task_extract(**context)


# ─── task_transform ───────────────────────────────────────────

def test_task_transform_removes_duplicate():
    """task_transform phải xóa dòng duplicate."""
    from dags.ingest_csv_dag import task_transform

    context, store = make_context({'raw_data': SAMPLE_DF.to_json()})
    task_transform(**context)

    df = pd.read_json(io.StringIO(store['clean_data']))
    assert df.duplicated().sum() == 0


def test_task_transform_fills_missing_age_and_salary():
    """task_transform phải điền 0 cho age và salary bị null."""
    from dags.ingest_csv_dag import task_transform

    context, store = make_context({'raw_data': SAMPLE_DF.to_json()})
    task_transform(**context)

    df = pd.read_json(io.StringIO(store['clean_data']))
    assert df['age'].isnull().sum() == 0
    assert df['salary'].isnull().sum() == 0


def test_task_transform_normalizes_column_names():
    """task_transform phải normalize tên cột sang lowercase."""
    from dags.ingest_csv_dag import task_transform

    raw = pd.DataFrame({
        'ID': [1], 'Name': ['An'], 'Age': [25],
        'City': ['Hanoi'], 'Salary': [1000], 'Created_At': ['2026-01-01']
    })
    context, store = make_context({'raw_data': raw.to_json()})
    task_transform(**context)

    df = pd.read_json(io.StringIO(store['clean_data']))
    for col in df.columns:
        assert col == col.lower()


# ─── task_quality ─────────────────────────────────────────────

def test_task_quality_passes_with_clean_data():
    """task_quality không raise khi data đạt chất lượng."""
    from dags.ingest_csv_dag import task_quality

    clean_df = pd.DataFrame({
        'id': [1, 2], 'name': ['An', 'Binh'], 'age': [25, 30],
        'city': ['Hanoi', 'HCMC'], 'salary': [15e6, 20e6],
        'created_at': ['2026-01-01', '2026-01-02'],
    })
    context, _ = make_context({'clean_data': clean_df.to_json()})

    task_quality(**context)  # không raise


def test_task_quality_raises_on_missing_required_columns():
    """task_quality phải raise khi thiếu cột bắt buộc."""
    from dags.ingest_csv_dag import task_quality

    bad_df = pd.DataFrame({'id': [1, 2], 'name': ['An', 'Binh']})
    context, _ = make_context({'clean_data': bad_df.to_json()})

    with pytest.raises(ValueError):
        task_quality(**context)


def test_task_quality_raises_on_nulls():
    """task_quality phải raise khi còn null sau transform."""
    from dags.ingest_csv_dag import task_quality

    df_with_null = pd.DataFrame({
        'id': [1, None], 'name': ['An', 'Binh'], 'age': [25, 30],
        'city': ['Hanoi', 'HCMC'], 'salary': [15e6, 20e6],
        'created_at': ['2026-01-01', '2026-01-02'],
    })
    context, _ = make_context({'clean_data': df_with_null.to_json()})

    with pytest.raises(ValueError):
        task_quality(**context)


# ─── task_load ────────────────────────────────────────────────

def test_task_load_calls_postgres_and_minio():
    """task_load phải gọi cả load_to_postgres và load_to_minio."""
    from dags.ingest_csv_dag import task_load

    clean_df = pd.DataFrame({
        'id': [1], 'name': ['An'], 'age': [25],
        'city': ['Hanoi'], 'salary': [15e6], 'created_at': ['2026-01-01'],
    })
    context, _ = make_context({'clean_data': clean_df.to_json()})

    with patch('etl.load.create_engine'), \
         patch('etl.load.boto3.client') as mock_boto, \
         patch.object(pd.DataFrame, 'to_sql'):
        mock_boto.return_value = MagicMock()
        task_load(**context)
