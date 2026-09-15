import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# --- Cấu hình kết nối lấy từ biến môi trường ---
# Không đặt giá trị mặc định chứa mật khẩu: thiếu biến thì task phải fail
# rõ ràng thay vì âm thầm thử một credential đã biết.
POSTGRES_CONN = os.getenv('AIRFLOW__DATABASE__SQL_ALCHEMY_CONN', '')
MINIO_ENDPOINT = os.getenv('MINIO_HOST', '') + ':' + os.getenv('MINIO_PORT', '')
MINIO_ACCESS   = os.getenv('MINIO_ROOT_USER', '')
MINIO_SECRET   = os.getenv('MINIO_ROOT_PASSWORD', '')
MINIO_BUCKET   = os.getenv('MINIO_BUCKET', '')
CSV_PATH       = '/opt/airflow/sample_data/sample.csv'

default_args = {
    'owner': 'dataops',
    'retries': 2,
    'retry_delay': timedelta(minutes=3),
}


def task_extract(**context):
    from etl.extract import extract_from_csv
    df = extract_from_csv(CSV_PATH)
    # Lưu tạm vào XCom dưới dạng JSON
    context['ti'].xcom_push(key='raw_data', value=df.to_json(date_format='iso'))


def task_transform(**context):
    import io
    import pandas as pd
    from etl.transform import clean_data, normalize_columns, fill_missing
    raw_json = context['ti'].xcom_pull(key='raw_data', task_ids='extract')
    df = pd.read_json(io.StringIO(raw_json))
    df = normalize_columns(df)
    df = clean_data(df)
    df = fill_missing(df, {'age': 0, 'salary': 0.0})
    context['ti'].xcom_push(key='clean_data', value=df.to_json(date_format='iso'))


def task_quality(**context):
    import io
    import pandas as pd
    from etl.quality_check import assert_quality
    clean_json = context['ti'].xcom_pull(key='clean_data', task_ids='transform')
    df = pd.read_json(io.StringIO(clean_json))
    assert_quality(df, expected_columns=['id', 'name', 'age', 'city', 'salary', 'created_at'])


def task_load(**context):
    import io
    import pandas as pd
    from datetime import date
    from etl.load import upsert_dataframe, load_to_minio
    clean_json = context['ti'].xcom_pull(key='clean_data', task_ids='transform')
    df = pd.read_json(io.StringIO(clean_json))

    # Delete-insert theo id trong một transaction; hàm tự tạo bảng nếu
    # chưa có nên chạy được cả trên database trống.
    upsert_dataframe(df, table='employees', conn_str=POSTGRES_CONN, key_column='id')
    object_name = f'raw/employees/{date.today()}.csv'
    load_to_minio(df, MINIO_BUCKET, object_name, MINIO_ENDPOINT, MINIO_ACCESS, MINIO_SECRET)


with DAG(
    dag_id='ingest_csv',
    default_args=default_args,
    description='Ingest dữ liệu từ CSV vào PostgreSQL và MinIO',
    schedule_interval='@daily',
    start_date=datetime(2026, 5, 12),
    catchup=False,
    tags=['ingest', 'csv'],
) as dag:

    extract   = PythonOperator(task_id='extract',   python_callable=task_extract)
    transform = PythonOperator(task_id='transform', python_callable=task_transform)
    quality   = PythonOperator(task_id='quality',   python_callable=task_quality)
    load      = PythonOperator(task_id='load',      python_callable=task_load)

    extract >> transform >> quality >> load
