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
│  │  Loki + Promtail │  │                  │  │              │  │
│  │  Alertmanager    │  │                  │  │              │  │
│  │  cAdvisor        │  │                  │  │              │  │
│  │  Node Exporter   │  │                  │  │              │  │
│  │  postgres-exp.   │  │                  │  │              │  │
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
| DB Metrics | postgres-exporter | latest |
| Infrastructure | Docker Compose v2 | - |
| IaC | Ansible | - |
| CI/CD | GitHub Actions | - |
| Test | pytest + flake8 | - |

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
│   └── tests/              # Unit tests (61 tests, 6 files)
│       ├── test_extract.py
│       ├── test_transform.py
│       ├── test_quality.py
│       ├── test_load.py
│       ├── test_dag_ingest_csv.py
│       └── test_dag_ingest_api.py
├── docker/
│   ├── dataops-vm1/        # Airflow + Monitoring compose
│   ├── dataops-vm2/        # PostgreSQL + Redis + MinIO compose
│   └── dataops-vm3/        # Node Exporter compose
├── monitoring/
│   ├── prometheus/         # prometheus.yml + alerts.yml
│   ├── grafana/dashboards/
│   ├── loki/               # loki-config.yml
│   ├── promtail/           # promtail-config.yml
│   └── alertmanager/       # alertmanager.yml
├── infra/ansible/          # Ansible IaC (ansible.cfg, site.yml, 3 playbooks)
├── backup/
│   └── backup.sh           # PostgreSQL backup script
├── .github/workflows/
│   ├── lint-test.yml       # CI: flake8 + pytest
│   └── deploy.yml          # CD: deploy lên VM1
├── docs/
│   ├── PLAN.md             # Kế hoạch thực hiện
│   └── REPORT.md           # Báo cáo kết quả
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

Yêu cầu trên máy điều khiển (macOS): `ansible`, các collection `ansible.posix` và
`community.docker`, cùng **GNU rsync** (`brew install rsync`). Bản `openrsync` mà
macOS cài sẵn không xuất được thông tin thay đổi nên Ansible sẽ luôn báo `changed`.

Secret được quản lý bằng Ansible Vault trong `infra/ansible/group_vars/all/vault.yml`
(đã mã hoá, commit được). Giá trị không nhạy cảm nằm ở `vars.yml` cùng thư mục.
File `.env` trên từng VM do Ansible sinh ra từ template — **không sửa trực tiếp trên VM**.

```bash
cd infra/ansible

# Xem hoặc sửa secret
ansible-vault view group_vars/all/vault.yml
ansible-vault edit group_vars/all/vault.yml

# Kiểm tra kết nối trước khi deploy
ansible all -m ping

# Deploy toàn bộ hệ thống (vm2 → vm1 → vm3)
ansible-playbook site.yml --ask-become-pass --ask-vault-pass

# Hoặc deploy riêng từng VM
ansible-playbook site.yml --limit vm2 --ask-become-pass --ask-vault-pass

# Chỉ cài Docker
ansible-playbook install_docker.yml --ask-become-pass
```

Cấu trúc role:

| Role | Chạy ở | Nhiệm vụ |
|---|---|---|
| `docker` | cả 3 VM | Docker Engine + Compose plugin |
| `app_code` | cả 3 VM | Đồng bộ code từ máy điều khiển |
| `dotenv` | cả 3 VM | Sinh `.env` từ template, secret lấy từ Ansible Vault |
| `database` | vm2 | PostgreSQL, Redis, MinIO |
| `airflow` | vm1 | Airflow CeleryExecutor |
| `monitoring` | vm1 | Prometheus, Grafana, Loki, Alertmanager, các exporter |
| `node_exporter` | vm3 | node-exporter |
| `backup` | vm3 | postgresql-client-15, script backup, cron 2:00 |

### Deploy thủ công

```bash
# VM2 - Database (bật trước)
ssh dataops@192.168.64.3
cd ~/dataops/docker/dataops-vm2
docker compose up -d

# VM1 - Airflow
ssh dataops@192.168.64.2
cd ~/dataops/docker/dataops-vm1
docker compose up -d

# VM1 - Monitoring
docker compose -f docker-compose-monitoring.yml up -d

# VM3 - Node Exporter + Backup
ssh dataops@192.168.64.4
cd ~/dataops/docker/dataops-vm3
docker compose up -d
```

## Data Pipeline

### DAGs

| DAG | Mô tả | Schedule |
|---|---|---|
| `ingest_csv` | Đọc CSV → transform → load PostgreSQL + MinIO | @daily |
| `ingest_weather_api` | Gọi API thời tiết Hà Nội → transform → load | @hourly |
| `data_quality_check` | Kiểm tra chất lượng dữ liệu | @daily |

### Chạy DAG thủ công

```bash
# Trigger DAG từ Airflow UI: http://192.168.64.2:8080
# hoặc CLI:
docker exec -it airflow_webserver airflow dags trigger ingest_csv
```

## Unit Tests

```bash
cd pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Lint check
flake8 etl/ dags/ tests/

# Chạy tất cả tests
pytest tests/ -v

# Kết quả: 61 passed, 0 warnings
```

| File | Tests | Phạm vi |
|---|---|---|
| `test_extract.py` | 10 | extract_from_csv, extract_from_api |
| `test_transform.py` | 15 | clean_data, normalize_columns, fill_missing, cast_types |
| `test_quality.py` | 12 | run_quality_check, assert_quality, QualityReport |
| `test_load.py` | 8 | load_to_postgres, load_to_minio |
| `test_dag_ingest_csv.py` | 9 | task_extract/transform/quality/load (CSV DAG) |
| `test_dag_ingest_api.py` | 7 | task_extract/transform/quality/load (API DAG) |

## Monitoring

| Service | URL | Mô tả |
|---|---|---|
| Airflow UI | http://192.168.64.2:8080 | Quản lý DAGs |
| Grafana | http://192.168.64.2:3000 | Dashboard metrics (admin / ***REMOVED***) |
| Prometheus | http://192.168.64.2:9090 | Metrics scraping (5 targets UP) |
| Alertmanager | http://192.168.64.2:9093 | Alert routing |
| Flower | http://192.168.64.2:5555 | Celery worker monitor |
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
- `pytest` unit tests (61 tests)

### CD (GitHub Actions)
Deploy lên VM1 khi push `main` — dùng **self-hosted runner** cài trên VM1:
- Không cần GitHub Secrets SSH (runner chạy trực tiếp trên VM1)
- Runner được cài như systemd service, tự khởi động khi VM1 reboot
- Kiểm tra runner: `sudo systemctl status actions.runner.*.service`

## Tiến độ

| Giai đoạn | Mô tả | Trạng thái |
|---|---|---|
| GĐ1 | Môi trường (VM, Git, .env) | ✅ Hoàn thành |
| GĐ2 | Infrastructure (Airflow, PostgreSQL, Redis, MinIO) | ✅ Hoàn thành |
| GĐ3 | Data Pipeline (ETL + 3 DAGs) | ✅ Hoàn thành |
| GĐ4 | Monitoring (Prometheus, Grafana, Loki, Alertmanager) | ✅ Hoàn thành |
| GĐ5 | Backup (script + cron trên VM3) | ✅ Hoàn thành |
| GĐ6 | CI/CD (GitHub Actions + Ansible playbooks) | ✅ Hoàn thành |
| GĐ7 | Unit Tests (61/61 passed, 6 files, flake8 clean) | ✅ Hoàn thành |
| GĐ8 | Documentation | ✅ Hoàn thành |
