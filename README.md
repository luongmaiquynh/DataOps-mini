# Mini DataOps Platform

Nền tảng DataOps thu nhỏ triển khai trên 3 VM Ubuntu 22.04 (ARM64) chạy qua UTM trên macOS Apple Silicon.

## Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────────────┐
│                        macOS Host (UTM)                         │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │      VM1         │  │      VM2         │  │     VM3      │  │
│  │  192.168.64.2    │  │  192.168.64.3    │  │ 192.168.64.4 │  │
│  │                  │  │                  │  │              │  │
│  │  Apache Airflow  │  │  PostgreSQL 15   │  │  Backup      │  │
│  │  (CeleryExecutor)│  │  Redis 7         │  │  Node        │  │
│  │  Prometheus      │  │  MinIO           │  │  Exporter    │  │
│  │  Grafana         │  │                  │  │              │  │
│  │  Loki            │  │                  │  │              │  │
│  │  Alertmanager    │  │                  │  │              │  │
│  │  cAdvisor        │  │                  │  │              │  │
│  │  Node Exporter   │  │                  │  │              │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Công nghệ sử dụng

| Thành phần | Công nghệ | Version |
|---|---|---|
| Orchestration | Apache Airflow | 2.7.1 |
| Message Broker | Redis | 7 |
| Database | PostgreSQL | 15 |
| Object Storage | MinIO | latest |
| Metrics | Prometheus + Grafana | latest |
| Log Aggregation | Loki + Promtail | latest |
| Alerting | Alertmanager | latest |
| Container Metrics | cAdvisor | latest |
| Infrastructure | Docker Compose v2 | - |
| IaC | Ansible | - |
| CI/CD | GitHub Actions | - |

## Cấu trúc thư mục

```
dataops/
├── pipeline/
│   ├── dags/               # Airflow DAGs
│   │   ├── ingest_csv_dag.py
│   │   ├── ingest_api_dag.py
│   │   └── data_quality_dag.py
│   ├── etl/                # ETL modules
│   │   ├── extract.py
│   │   ├── transform.py
│   │   ├── load.py
│   │   └── quality_check.py
│   └── tests/              # Unit tests
│       ├── test_transform.py
│       └── test_quality.py
├── docker/
│   ├── dataops-vm1/        # Airflow + Monitoring compose
│   ├── dataops-vm2/        # PostgreSQL + Redis + MinIO compose
│   └── dataops-vm3/        # Node Exporter compose
├── monitoring/
│   ├── prometheus/         # prometheus.yml + alerts.yml
│   ├── grafana/dashboards/
│   ├── loki/               # loki-config.yml
│   └── alertmanager/       # alertmanager.yml
├── infra/ansible/          # Ansible playbooks (vm1, vm2, vm3)
├── backup/
│   └── backup.sh           # PostgreSQL backup script
├── .github/workflows/
│   ├── lint-test.yml       # CI: flake8 + pytest
│   └── deploy.yml          # CD: deploy lên VM1
└── sample_data/
    └── sample.csv
```

## Thiết lập môi trường

### Yêu cầu
- macOS với UTM + 3 VM Ubuntu 22.04 ARM64
- Docker + Docker Compose v2 trên mỗi VM
- Ansible trên máy host
- Python 3.8+

### Biến môi trường

Tạo file `.env` tại root (xem `.env.example`):

```env
POSTGRES_HOST=192.168.64.3
POSTGRES_PORT=5432
POSTGRES_DB=dataops
POSTGRES_USER=dataops
POSTGRES_PASSWORD=your_password

MINIO_ENDPOINT=192.168.64.3:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=your_minio_password
MINIO_BUCKET=dataops-lake

REDIS_HOST=192.168.64.3
REDIS_PORT=6379
```

### Deploy bằng Ansible

```bash
# Deploy VM1 (Airflow + Monitoring)
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/playbook-vm1.yml

# Deploy VM2 (PostgreSQL + Redis + MinIO)
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/playbook-vm2.yml

# Deploy VM3 (Node Exporter + Backup)
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/playbook-vm3.yml
```

### Deploy thủ công

```bash
# VM1 - Airflow
ssh dataops@192.168.64.2
cd ~/dataops/docker/dataops-vm1
docker compose up -d

# VM1 - Monitoring
docker compose -f docker-compose-monitoring.yml up -d

# VM2
ssh dataops@192.168.64.3
cd ~/dataops/docker/dataops-vm2
docker compose up -d
```

## Data Pipeline

### DAGs

| DAG | Mô tả | Schedule |
|---|---|---|
| `ingest_csv_dag` | Đọc CSV → transform → load PostgreSQL + MinIO | @daily |
| `ingest_api_dag` | Gọi API → transform → load | @hourly |
| `data_quality_dag` | Kiểm tra chất lượng dữ liệu | @daily |

### Chạy DAG thủ công

```bash
# Trigger DAG từ Airflow UI: http://192.168.64.2:8080
# hoặc CLI:
docker exec -it airflow-webserver airflow dags trigger ingest_csv_dag
```

## Unit Tests

```bash
cd pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Chạy tất cả tests
pytest tests/ -v

# Kết quả: 28 tests PASSED
```

## Monitoring

| Service | URL | Mô tả |
|---|---|---|
| Airflow UI | http://192.168.64.2:8080 | Quản lý DAGs |
| Grafana | http://192.168.64.2:3000 | Dashboard metrics |
| Prometheus | http://192.168.64.2:9090 | Metrics scraping |
| Alertmanager | http://192.168.64.2:9093 | Alert routing |
| MinIO Console | http://192.168.64.3:9001 | Object storage UI |

## Backup

Script backup PostgreSQL chạy tự động lúc 2:00 AM hàng ngày trên VM3:

```bash
# Chạy thủ công
ssh dataops@192.168.64.4
bash /home/dataops/backup.sh

# Xem log
tail -f /var/log/dataops-backup.log

# File backup lưu tại:
ls /opt/backup/postgres/
```

Giữ backup 7 ngày gần nhất, tự động xóa file cũ hơn.

## CI/CD

### CI (GitHub Actions)
Tự động chạy khi push lên nhánh `main`:
- `flake8` lint check
- `pytest` unit tests (28 tests)

### CD (GitHub Actions)
Deploy lên VM1 khi push `main` (cần cấu hình GitHub Secrets):
- `VM1_HOST`: IP của VM1
- `VM1_USER`: username SSH
- `VM1_SSH_KEY`: nội dung private key

## Tiến độ

| Giai đoạn | Mô tả | Trạng thái |
|---|---|---|
| GĐ1 | Môi trường (VM, Git, .env) | ✅ Hoàn thành |
| GĐ2 | Infrastructure (Airflow, PostgreSQL, Redis, MinIO) | ✅ Hoàn thành |
| GĐ3 | Data Pipeline (ETL + 3 DAGs) | ✅ Hoàn thành |
| GĐ4 | Monitoring (Prometheus, Grafana, Loki, Alertmanager) | ✅ Hoàn thành |
| GĐ5 | Backup (script + cron trên VM3) | ✅ Hoàn thành |
| GĐ6 | CI/CD (GitHub Actions + Ansible playbooks) | ✅ Hoàn thành |
| GĐ7 | Unit Tests (28/28 passed) | ✅ Hoàn thành |
| GĐ8 | Documentation | ✅ Hoàn thành |
