import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Không đặt giá trị mặc định chứa mật khẩu.
POSTGRES_CONN = os.getenv('AIRFLOW__DATABASE__SQL_ALCHEMY_CONN', '')

default_args = {
    'owner': 'dataops',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


def check_employees(**context):
    """Kiểm tra bảng employees trong PostgreSQL."""
    import pandas as pd
    from etl.load import get_postgres_engine
    from etl.quality_check import run_quality_check
    engine = get_postgres_engine(POSTGRES_CONN)
    try:
        df = pd.read_sql('SELECT * FROM employees', engine)
        report = run_quality_check(df, expected_columns=['id', 'name', 'age', 'city', 'salary'])
        print(report.summary())
        if not report.passed:
            raise ValueError(f"employees table quality check failed: {report.summary()}")
    except Exception as e:
        # Bảng chưa tồn tại thì skip
        if 'does not exist' in str(e):
            print("Table 'employees' not found — skipping check")
        else:
            raise


def check_weather(**context):
    """Kiểm tra bảng weather_hanoi trong PostgreSQL."""
    import pandas as pd
    from etl.load import get_postgres_engine
    from etl.quality_check import run_quality_check
    engine = get_postgres_engine(POSTGRES_CONN)
    try:
        df = pd.read_sql('SELECT * FROM weather_hanoi', engine)
        report = run_quality_check(df, expected_columns=['time', 'temperature_2m', 'windspeed_10m'])
        print(report.summary())
        if not report.passed:
            raise ValueError(f"weather_hanoi table quality check failed: {report.summary()}")
    except Exception as e:
        if 'does not exist' in str(e):
            print("Table 'weather_hanoi' not found — skipping check")
        else:
            raise


with DAG(
    dag_id='data_quality_check',
    default_args=default_args,
    description='Kiểm tra chất lượng dữ liệu trong PostgreSQL hàng ngày',
    schedule_interval='@daily',
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['quality', 'monitoring'],
) as dag:

    check_emp     = PythonOperator(task_id='check_employees', python_callable=check_employees)
    check_weather = PythonOperator(task_id='check_weather',   python_callable=check_weather)
