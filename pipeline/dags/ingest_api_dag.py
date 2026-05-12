import os
from datetime import datetime, timedelta
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

POSTGRES_CONN = os.getenv(
    'AIRFLOW__DATABASE__SQL_ALCHEMY_CONN',
    'postgresql+psycopg2://dataops:***REMOVED***@192.168.64.3:5432/dataops_db'
)
MINIO_ENDPOINT = os.getenv('MINIO_HOST', '192.168.64.3') + ':' + os.getenv('MINIO_PORT', '9000')
MINIO_ACCESS   = os.getenv('MINIO_ROOT_USER', 'minioadmin')
MINIO_SECRET   = os.getenv('MINIO_ROOT_PASSWORD', '***REMOVED***')
MINIO_BUCKET   = os.getenv('MINIO_BUCKET', 'dataops-lake')

default_args = {
    'owner': 'dataops',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}


def task_extract(**context):
    from etl.extract import extract_from_api
    df = extract_from_api(API_URL, params=API_PARAMS)
    # Open-Meteo trả về dict với key 'hourly' chứa data
    import requests, pandas as pd
    resp = requests.get(API_URL, params=API_PARAMS, timeout=30)
    hourly = resp.json().get('hourly', {})
    df = pd.DataFrame(hourly)
    context['ti'].xcom_push(key='raw_data', value=df.to_json())


def task_transform(**context):
    import pandas as pd
    from etl.transform import clean_data, normalize_columns
    raw_json = context['ti'].xcom_pull(key='raw_data', task_ids='extract')
    df = pd.read_json(raw_json)
    df = normalize_columns(df)
    df = clean_data(df)
    # Thêm cột ngày ingest
    df['ingested_at'] = datetime.utcnow().isoformat()
    context['ti'].xcom_push(key='clean_data', value=df.to_json())


def task_quality(**context):
    import pandas as pd
    from etl.quality_check import assert_quality
    clean_json = context['ti'].xcom_pull(key='clean_data', task_ids='transform')
    df = pd.read_json(clean_json)
    assert_quality(df, expected_columns=['time', 'temperature_2m', 'windspeed_10m'])


def task_load(**context):
    import pandas as pd
    from datetime import date
    from etl.load import load_to_postgres, load_to_minio
    clean_json = context['ti'].xcom_pull(key='clean_data', task_ids='transform')
    df = pd.read_json(clean_json)
    load_to_postgres(df, table='weather_hanoi', conn_str=POSTGRES_CONN)
    object_name = f'raw/weather/{date.today()}.csv'
    load_to_minio(df, MINIO_BUCKET, object_name, MINIO_ENDPOINT, MINIO_ACCESS, MINIO_SECRET)


with DAG(
    dag_id='ingest_weather_api',
    default_args=default_args,
    description='Ingest dữ liệu thời tiết Hà Nội từ Open-Meteo API',
    schedule_interval='@hourly',
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['ingest', 'api', 'weather'],
) as dag:

    extract   = PythonOperator(task_id='extract',   python_callable=task_extract)
    transform = PythonOperator(task_id='transform', python_callable=task_transform)
    quality   = PythonOperator(task_id='quality',   python_callable=task_quality)
    load      = PythonOperator(task_id='load',      python_callable=task_load)

    extract >> transform >> quality >> load
