from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

def say_hello():
    print("Chào bạn! Airflow đã vận hành thành công.")

with DAG(
    dag_id="01_hello_world_test",
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False
) as dag:

    task_hello = PythonOperator(
        task_id="hello_task",
        python_callable=say_hello
    )