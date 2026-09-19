import os
from datetime import datetime, timedelta, timezone
from airflow import DAG
from airflow.operators.python import PythonOperator

# --- Nguồn dữ liệu: Open-Meteo (miễn phí, không cần API key) ---
API_URL = 'https://api.open-meteo.com/v1/forecast'
API_PARAMS = {
    'latitude': 21.0285,    # Hà Nội
    'longitude': 105.8542,
    'hourly': 'temperature_2m,windspeed_10m',
    'forecast_days': 1,
}

# Không đặt giá trị mặc định chứa mật khẩu: thiếu biến thì task phải fail
# rõ ràng thay vì âm thầm thử một credential đã biết.
POSTGRES_CONN = os.getenv('AIRFLOW__DATABASE__SQL_ALCHEMY_CONN', '')
MINIO_ENDPOINT = os.getenv('MINIO_HOST', '') + ':' + os.getenv('MINIO_PORT', '')
MINIO_ACCESS   = os.getenv('MINIO_ROOT_USER', '')
MINIO_SECRET   = os.getenv('MINIO_ROOT_PASSWORD', '')
MINIO_BUCKET   = os.getenv('MINIO_BUCKET', '')

default_args = {
    'owner': 'dataops',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}


def task_extract(**context):
    import requests
    import pandas as pd
    resp = requests.get(API_URL, params=API_PARAMS, timeout=30)
    resp.raise_for_status()
    hourly = resp.json().get('hourly', {})
    if not hourly:
        raise ValueError('API response missing hourly data')
    df = pd.DataFrame(hourly)
    context['ti'].xcom_push(key='raw_data', value=df.to_json())


def task_transform(**context):
    import io
    import pandas as pd
    from etl.transform import clean_data, normalize_columns
    raw_json = context['ti'].xcom_pull(key='raw_data', task_ids='extract')
    df = pd.read_json(io.StringIO(raw_json))
    df = normalize_columns(df)
    df = clean_data(df)
    # Thêm cột ngày ingest
    df['ingested_at'] = datetime.now(timezone.utc).isoformat()
    context['ti'].xcom_push(key='clean_data', value=df.to_json())


def task_quality(**context):
    import io
    import pandas as pd
    from etl.quality_check import assert_quality
    clean_json = context['ti'].xcom_pull(key='clean_data', task_ids='transform')
    df = pd.read_json(io.StringIO(clean_json))
    assert_quality(df, expected_columns=['time', 'temperature_2m', 'windspeed_10m'])


def task_load(**context):
    import io
    import pandas as pd
    from datetime import date
    from etl.load import upsert_dataframe, load_to_minio
    clean_json = context['ti'].xcom_pull(key='clean_data', task_ids='transform')
    df = pd.read_json(io.StringIO(clean_json))

    # Cột time lưu dạng chuỗi trong PostgreSQL; ép kiểu để khoá so khớp đúng.
    df['time'] = df['time'].astype(str)

    # Chèn mới hoặc cập nhật theo time (INSERT ... ON CONFLICT); hàm tự tạo
    # bảng nếu chưa có nên chạy được cả trên database trống.
    upsert_dataframe(df, table='weather_hanoi', conn_str=POSTGRES_CONN, key_column='time')
    object_name = f'raw/weather/{date.today()}.csv'
    load_to_minio(df, MINIO_BUCKET, object_name, MINIO_ENDPOINT, MINIO_ACCESS, MINIO_SECRET)


with DAG(
    dag_id='ingest_weather_api',
    default_args=default_args,
    description='Ingest dữ liệu thời tiết Hà Nội từ Open-Meteo API',
    schedule_interval='@hourly',
    start_date=datetime(2026, 5, 12),
    catchup=False,
    tags=['ingest', 'api', 'weather'],
    # Hai lần chạy ghi cùng lúc từng nhân đôi dữ liệu; chạy lần lượt cho chắc.
    max_active_runs=1,
) as dag:

    extract   = PythonOperator(task_id='extract',   python_callable=task_extract)
    transform = PythonOperator(task_id='transform', python_callable=task_transform)
    quality   = PythonOperator(task_id='quality',   python_callable=task_quality)
    load      = PythonOperator(task_id='load',      python_callable=task_load)

    extract >> transform >> quality >> load
