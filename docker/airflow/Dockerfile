# Image Airflow có sẵn thư viện cho pipeline.
#
# Vì sao cần: trước đây compose dùng _PIP_ADDITIONAL_REQUIREMENTS, nghĩa là MỖI
# container Airflow tải lại 5 thư viện từ Internet ở mỗi lần khởi động. Hệ quả đo
# được: 419 giây từ lúc `up -d` tới khi webserver healthy, và một lần triển khai
# đã fail hẳn vì pip tải dở dang khi mạng chập chờn.
FROM apache/airflow:2.7.1

COPY requirements.txt /tmp/requirements.txt

# --retries và --timeout cao vì mạng của lab hay đứt giữa chừng: đã fail thật
# hai lần khi tải psycopg2 và SQLAlchemy. Không có chúng thì một cú nghẽn mạng
# thoáng qua cũng làm hỏng cả lần build.
# Kiểm tra import ngay trong cùng lệnh: thiếu thư viện thì hỏng lúc build, không
# phải lúc DAG chạy. Gộp vào một RUN để image bớt một lớp.
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r /tmp/requirements.txt && \
    python -c "import boto3, psycopg2, pandas, requests, sqlalchemy; print('deps OK')"
