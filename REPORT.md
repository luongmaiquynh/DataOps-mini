# BÁO CÁO TIẾN ĐỘ DỰ ÁN: Mini DataOps Platform
**Ngày báo cáo:** 12/05/2026  
**Người thực hiện:** Lương Mai Quỳnh  
**Mentor:** *(tên mentor)*

---

## 1. Tổng quan dự án

### Mục tiêu
Xây dựng nền tảng DataOps thu nhỏ (mini) hoàn chỉnh, bao gồm:
- Thu thập dữ liệu từ CSV / REST API
- Xử lý và kiểm tra chất lượng dữ liệu tự động
- Lưu trữ tập trung (PostgreSQL + MinIO)
- Giám sát hệ thống & logging tập trung
- Backup định kỳ và cảnh báo lỗi
- Triển khai bằng container (Docker)
- CI/CD + Infrastructure as Code

### Kiến trúc hệ thống

```
Máy macOS (VS Code + Git + SSH)
         │
         ▼
┌─────────────────────────────────────────────────┐
│  VM1 – DataOps Master (192.168.64.2)           │
│  Airflow | Grafana | Prometheus | Loki          │
└─────────────────────────────────────────────────┘
         │ mạng nội bộ 192.168.64.x
         ▼
┌─────────────────────────────────────────────────┐
│  VM2 – Database + Storage (192.168.64.3)        │
│  PostgreSQL | Redis | MinIO | Airflow Worker    │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  VM3 – Worker / Backup (192.168.64.4)          │
│  Airflow Worker | Node Exporter | Backup        │
└─────────────────────────────────────────────────┘
```

### Stack công nghệ
| Thành phần | Công nghệ |
|---|---|
| OS | Ubuntu Server 22.04 (ARM64, chạy trên UTM – Apple Silicon) |
| Container | Docker + Docker Compose v2 |
| Workflow Orchestration | Apache Airflow 2.7.1 |
| Message Broker | Redis 7 |
| Relational Database | PostgreSQL 15 |
| Object Storage | MinIO |
| Metrics & Monitoring | Prometheus + Grafana + cAdvisor + Node Exporter |
| Logging | Loki + Promtail |
| Alerting | Alertmanager |
| Language | Python 3.11 |
| CI/CD | GitHub Actions |
| IaC | Ansible |
| Test | pytest + flake8 |

---

## 2. Những gì đã hoàn thành

### 2.1 Giai đoạn 1 – Chuẩn bị môi trường

#### ✅ Tạo 3 máy ảo Ubuntu Server 22.04 bằng UTM
- Công cụ sử dụng: **UTM** (phần mềm ảo hóa miễn phí cho macOS Apple Silicon)
- Hệ điều hành: Ubuntu Server 22.04 **ARM64** (phiên bản bắt buộc với chip M-series)
- Mỗi VM được cấu hình:
  - 2 network interface: Shared Network (NAT – ra internet) + Host-Only (SSH từ macOS)
  - IP tĩnh trên interface Host-Only
  - User: `dataops`, SSH key từ macOS

| VM | IP | Vai trò |
|---|---|---|
| vm1 | 192.168.64.2 | DataOps Master: Airflow, Grafana, Prometheus, Loki |
| vm2 | 192.168.64.3 | Database: PostgreSQL, Redis, MinIO |
| vm3 | 192.168.64.4 | Worker + Backup |

#### ✅ Khởi tạo cấu trúc dự án Git

Tạo toàn bộ cây thư mục chuẩn theo kiến trúc đã thiết kế:
```
dataops/
├── .github/workflows/       # CI/CD (placeholder)
├── infra/ansible/           # Infrastructure as Code
├── docker/
│   ├── dataops-vm1/         # Airflow + Monitoring compose
│   ├── dataops-vm2/         # PostgreSQL + Redis + MinIO compose ✅
│   └── dataops-vm3/         # Worker + Backup compose
├── pipeline/
│   ├── dags/                # Airflow DAGs
│   ├── etl/                 # ETL modules
│   └── tests/               # Unit tests
├── monitoring/              # Prometheus, Grafana, Loki, Alertmanager
├── backup/
└── sample_data/
```

#### ✅ Cấu hình `.env.example`

File quản lý toàn bộ biến môi trường cho hệ thống, bao gồm:
- Thông tin kết nối PostgreSQL, Redis, MinIO
- Cấu hình Airflow (Fernet Key, Secret Key, SQLAlchemy Conn, Celery Broker)
- Thông tin Grafana, VM3

**Nguyên tắc bảo mật áp dụng:** Không commit file `.env` thực tế lên Git — chỉ commit `.env.example` làm template.

#### ✅ Cấu hình `.gitignore`

File bảo vệ repository khỏi commit nhầm dữ liệu nhạy cảm, bao gồm:
- `.env` và tất cả biến thể `*.env`
- Thư mục volume Docker (`postgres_data/`, `minio_data/`)
- Python cache (`__pycache__/`, `.venv/`, `.pytest_cache/`)
- Log files, file IDE, file hệ thống macOS (`.DS_Store`)
- Airflow runtime files (`airflow.cfg`, `airflow.db`)
- **Exception:** `sample_data/sample.csv` được giữ lại (dùng `!` rule)

---

### 2.2 Giai đoạn 2 – Triển khai Infrastructure (một phần)

#### ✅ VM2: docker-compose.yml (PostgreSQL + Redis + MinIO)

File: `docker/dataops-vm2/docker-compose.yml`

**Thiết kế và lý do chọn:**

| Service | Image | Cổng | Lý do |
|---|---|---|---|
| PostgreSQL 15 | `postgres:15` | 5432 | Database metadata Airflow + lưu dữ liệu pipeline |
| Redis 7 | `redis:7` | 6379 | Message broker cho Airflow Celery Executor |
| MinIO | `minio/minio` | 9000, 9001 | Object storage tương thích S3, lưu file CSV/Parquet |

**Các kỹ thuật Docker Compose đã áp dụng:**
- `restart: always` — tự khởi động lại khi VM reboot
- `healthcheck` trên PostgreSQL — kiểm tra DB sẵn sàng trước khi các service khác kết nối
- `volumes` named volume — dữ liệu không bị mất khi container restart
- Biến môi trường từ `.env` (`${POSTGRES_USER}`) — không hardcode credential

```yaml
# Ví dụ healthcheck PostgreSQL đã cấu hình:
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
  interval: 10s
  timeout: 5s
  retries: 5
```

#### ✅ Prototype Airflow (docker-compose-airflow.yml)

File thực nghiệm để kiểm tra Airflow kết nối được với PostgreSQL VM2:
- Image: `apache/airflow:2.7.1`
- Executor: `LocalExecutor` (đơn giản, phù hợp bước kiểm tra ban đầu)
- Kết nối: SQLAlchemy Conn trỏ về PostgreSQL tại `192.168.64.3:5432`
- 2 service: `airflow-webserver` (port 8080) + `airflow-scheduler`

> **Ghi chú:** Đây là bản prototype để xác nhận kết nối hoạt động. Bản chính thức cho VM1 sẽ dùng `CeleryExecutor` + Redis.

#### ✅ Test DAG Hello World

File: `dags/hello_world_dag.py`

DAG đơn giản để xác nhận Airflow scheduler + webserver hoạt động đúng:
```python
dag_id="01_hello_world_test"
schedule_interval=None   # chạy thủ công
task: PythonOperator in ra "Airflow đã vận hành thành công"
```

**Mục đích:** Trước khi viết DAG phức tạp, cần xác nhận Airflow có thể:
1. Đọc được DAG file
2. Scheduler parse DAG không lỗi
3. Task chạy thành công trên webserver

---

### 2.3 Giai đoạn 6 – Infrastructure as Code (một phần)

#### ✅ Ansible Inventory (`infra/ansible/inventory.ini`)

Khai báo 3 VM để Ansible quản lý tập trung:
```ini
[dataops_nodes]
vm1 ansible_host=192.168.64.2 ansible_user=dataops
vm2 ansible_host=192.168.64.3 ansible_user=dataops
vm3 ansible_host=192.168.64.4 ansible_user=dataops
```

#### ✅ Ansible Playbook: Cài Docker (`install_docker.yml`)

Playbook tự động hóa việc cài Docker lên tất cả VM, bao gồm:
1. Cài các package phụ thuộc (`apt-transport-https`, `ca-certificates`, `curl`...)
2. Thêm Docker GPG key và repository
3. Cài `docker-ce`
4. Cài Docker Python module (cho Ansible quản lý container)

**Lý do dùng Ansible thay vì cài tay:** Đảm bảo cấu hình đồng nhất trên cả 3 VM, có thể tái thực thi (idempotent), dễ kiểm tra lại.

---

### 2.4 Giai đoạn 2 (tiếp) – Triển khai VM1 Airflow CeleryExecutor

#### ✅ VM1: docker-compose.yml (Airflow CeleryExecutor)

File: `docker/dataops-vm1/docker-compose.yml`

**Kiến trúc CeleryExecutor đã triển khai:**

| Service | Image | Cổng | Vai trò |
|---|---|---|---|
| airflow-webserver | `apache/airflow:2.7.1` | 8080 | Giao diện quản lý DAG |
| airflow-scheduler | `apache/airflow:2.7.1` | — | Lên lịch và phân phối task |
| airflow-worker | `apache/airflow:2.7.1` | — | Thực thi task từ Redis queue |
| airflow-flower | `apache/airflow:2.7.1` | 5555 | Monitor Celery worker |
| airflow-init | `apache/airflow:2.7.1` | — | Khởi tạo DB + tạo admin user |

**Cấu hình quan trọng đã áp dụng:**
- `AIRFLOW__CORE__EXECUTOR: CeleryExecutor`
- `AIRFLOW__CELERY__BROKER_URL: redis://192.168.64.3:6379/0` (Redis trên VM2)
- `AIRFLOW__CELERY__RESULT_BACKEND: db+postgresql://...` (PostgreSQL trên VM2)
- `_PIP_ADDITIONAL_REQUIREMENTS`: Cài thêm package Python khi container khởi động
- Volume mounts: `./pipeline/etl` → `/opt/airflow/etl`, `./sample_data` → `/opt/airflow/sample_data`

**Sự cố đã xử lý:**
- Permission denied `/opt/airflow/logs`: Sửa bằng `sudo chown -R 50000:0 logs/`
- YAML folding syntax error trong `airflow-init` command: Sửa từ `>` sang array syntax
- Python 3.8 incompatibility: Downgrade `pandas==2.0.3`, `sqlalchemy==1.4.52`

#### ✅ Tạo MinIO bucket `dataops-lake`

Tạo bucket qua MinIO Console (http://192.168.64.3:9001), đây là nơi lưu trữ file CSV/Parquet sau khi ETL.

---

### 2.5 Giai đoạn 3 – Data Pipeline

#### ✅ ETL Modules

**`pipeline/etl/extract.py`**
- `extract_from_csv(filepath)` → pd.DataFrame
- `extract_from_api(url, params=None)` → pd.DataFrame (HTTP GET với timeout=30s)

**`pipeline/etl/transform.py`**
- `clean_data(df)` → Xóa duplicate rows + rows toàn NaN
- `normalize_columns(df)` → Chuẩn hóa tên cột (lowercase + underscore)
- `fill_missing(df, fill_values)` → Fill NaN theo dict cho trước
- `cast_types(df, schema)` → Chuyển đổi kiểu dữ liệu theo schema

**`pipeline/etl/quality_check.py`**
- `QualityReport` dataclass: null_count, duplicate_count, schema_errors, passed
- `run_quality_check(df)` → Trả về QualityReport (không blocking)
- `assert_quality(df)` → Raise exception nếu có lỗi (blocking pipeline)

**`pipeline/etl/load.py`**
- `load_to_postgres(df, table, conn_str)` → Dùng SQLAlchemy, `if_exists='append'`
- `load_to_minio(df, bucket, object_name, ...)` → Dùng boto3 S3 client

#### ✅ Sample Data (`sample_data/sample.csv`)

6 dòng dữ liệu nhân viên với các lỗi cố ý để test pipeline:
- 1 dòng trùng lặp (ID=1 xuất hiện 2 lần)
- 1 dòng thiếu `age` (Pham Thi D)
- 1 dòng thiếu `salary` (Hoang Van E)

#### ✅ Airflow DAGs

**`pipeline/dags/ingest_csv_dag.py`** — `@daily`, đã test thành công
- 4 task: `extract` → `transform` → `quality` → `load`
- Đọc CSV từ `/opt/airflow/sample_data/sample.csv`
- Load kết quả vào PostgreSQL table `employees` + MinIO bucket `dataops-lake`

**`pipeline/dags/ingest_api_dag.py`** — `@hourly`
- Pipeline thời tiết từ REST API

**`pipeline/dags/data_quality_dag.py`** — `@daily`
- Kiểm tra chất lượng dữ liệu trong PostgreSQL hàng ngày

#### ✅ Pipeline đã chạy thành công và xác minh kết quả

- 4 task của `ingest_csv` chạy thành công (extract → transform → quality → load)
- PostgreSQL: bảng `employees` có **5 rows** đúng (sau khi loại bỏ duplicate ID=1)
- MinIO: file `dataops-lake/raw/employees/2026-05-12.csv` đã được upload

```
 id |     name     | age |  city  |  salary  |     created_at
----+--------------+-----+--------+----------+---------------------
  1 | Nguyen Van A |  25 | Hanoi  | 15000000 | 2026-01-01 00:00:00
  2 | Tran Thi B   |  30 | HCMC   | 20000000 | 2026-01-02 00:00:00
  3 | Le Van C     |  28 | Hanoi  | 18000000 | 2026-01-03 00:00:00
  4 | Pham Thi D   |   0 | Danang | 12000000 | 2026-01-04 00:00:00
  5 | Hoang Van E  |  35 | HCMC   |        0 | 2026-01-05 00:00:00
(5 rows)
```

#### ✅ Debug và sửa lỗi trùng dữ liệu

**Vấn đề:** Sau lần chạy đầu tiên, PostgreSQL có 10 rows thay vì 5.

**Điều tra:**
1. Kiểm tra lịch sử DAG: `airflow dags list-runs -d ingest_csv`
2. Phát hiện DAG chạy **2 lần**: 1 lần `scheduled` (backfill từ `start_date=2026-01-01`) + 1 lần `manual` (trigger thủ công)
3. Mỗi lần load 5 rows → 5 × 2 = 10 rows

**Giải pháp:**
- `TRUNCATE employees` trên PostgreSQL để xóa dữ liệu cũ
- Sửa `start_date=datetime(2026, 5, 12)` để Airflow không backfill các ngày trước
- Giữ `schedule_interval='@daily'` theo đúng yêu cầu PLAN.md
- Trigger lại DAG 1 lần → 5 rows chính xác

---

## 3. Tổng hợp tiến độ

| Giai đoạn | Mô tả | Tiến độ |
|---|---|---|
| GĐ1: Chuẩn bị môi trường | VM, Git, cấu trúc thư mục, .env, .gitignore | **100%** |
| GĐ2: Infrastructure | Docker Compose cho 3 VM | **95%** |
| GĐ3: Data Pipeline | ETL modules + Airflow DAGs + test thực tế | **90%** |
| GĐ4: Monitoring & Logging | Prometheus, Grafana, Loki, Alertmanager | **0%** |
| GĐ5: Backup | Script backup PostgreSQL + cron | **0%** |
| GĐ6: CI/CD + IaC | GitHub Actions + Ansible Playbooks | **30%** |
| GĐ7: Testing | Unit test ETL | **0%** |
| GĐ8: Tài liệu | README, architecture diagram | **0%** |
| **Tổng thể** | | **~52%** |

---

## 4. Những kiến thức đã học và áp dụng

### Infrastructure & Virtualization
- Tạo và cấu hình VM Ubuntu Server 22.04 ARM64 trên UTM (Apple Silicon)
- Cấu hình dual network interface (NAT + Host-Only) cho VM
- Đặt IP tĩnh bằng Netplan, SSH key-based authentication

### Docker & Docker Compose
- Viết `docker-compose.yml` với multiple services
- Named volumes để persist data
- Healthcheck để đảm bảo service dependency
- Biến môi trường từ `.env` file (không hardcode credential)
- `restart: always` policy
- Triển khai Airflow CeleryExecutor với Redis broker

### Apache Airflow
- Hiểu cấu trúc DAG, Operator, Task, XCom
- CeleryExecutor với Redis broker và Flower monitor
- Debugging DAG run history, phân biệt scheduled vs manual trigger
- `catchup=False` và tác động của `start_date` đến backfill
- `_PIP_ADDITIONAL_REQUIREMENTS` để cài package bên trong container

### Data Engineering
- Viết ETL modules tách biệt (extract, transform, load, quality_check)
- Xử lý duplicate rows, null values, type casting
- Data quality reporting với dataclass
- Upload file CSV lên MinIO (S3-compatible) bằng boto3
- Load DataFrame vào PostgreSQL bằng SQLAlchemy

### Security Best Practices
- Không commit credential lên Git (`.env` trong `.gitignore`)
- Dùng `.env.example` làm template an toàn
- Phân tách thông tin cấu hình khỏi code

### Infrastructure as Code
- Ansible inventory với multiple hosts
- Ansible playbook với apt module, apt_key, apt_repository

---

## 5. Vấn đề gặp phải và hướng xử lý

| Vấn đề | Nguyên nhân | Hướng xử lý |
|---|---|---|
| IP subnet UTM khác kế hoạch (`192.168.64.x` thay vì `192.168.56.x`) | UTM tự cấp subnet Host-Only khác với mặc định VirtualBox | Cập nhật toàn bộ IP trong PLAN.md, `.env.example`, `inventory.ini` |
| `docker-compose-airflow.yml` dùng LocalExecutor | Bản prototype chỉ để kiểm tra kết nối ban đầu | Bản chính thức (`docker/dataops-vm1/`) dùng CeleryExecutor + Redis |
| Credentials hardcoded trong file prototype | Viết nhanh để test | Cần refactor dùng `.env` file trước khi deploy chính thức |
| Permission denied `/opt/airflow/logs` | Container Airflow chạy uid=50000, volume có owner sai | `sudo chown -R 50000:0 logs/` trên VM1 |
| YAML folding syntax error trong airflow-init | Dùng `>` operator khiến các dòng lệnh bị nối thành 1 | Chuyển sang array syntax trong compose |
| Python 3.8 không tương thích pandas, sqlalchemy | Container Airflow 2.7.1 dùng Python 3.8 | Downgrade `pandas==2.0.3`, `sqlalchemy==1.4.52` |
| Container name conflict khi deploy VM2 | File prototype đã tạo container cùng tên `postgres_db` | `docker rm -f postgres_db` trước khi chạy compose chính |
| 10 rows trong PostgreSQL thay vì 5 | DAG chạy 2 lần: 1 `scheduled` (backfill từ `start_date`) + 1 `manual` | `TRUNCATE employees` + sửa `start_date=datetime(2026,5,12)` |

---

## 6. Kế hoạch tiếp theo (ưu tiên)

| Thứ tự | Công việc | Lý do ưu tiên |
|---|---|---|
| 1 | ~~Hoàn thiện `docker/dataops-vm1/docker-compose.yml`~~ | ✅ Hoàn thành |
| 2 | ~~Viết ETL modules + Airflow DAGs~~ | ✅ Hoàn thành |
| 3 | Viết unit tests (`test_transform.py`, `test_quality.py`) | Xác nhận logic ETL đúng |
| 4 | Hoàn thiện `docker/dataops-vm1/docker-compose-monitoring.yml` | Cần monitoring sớm để theo dõi hệ thống |
| 5 | Viết backup script + cron job trên VM3 | Bảo vệ dữ liệu PostgreSQL |
| 6 | Viết Ansible playbooks cho VM1, VM2, VM3 | Tự động hóa deploy |
| 7 | GitHub Actions (CI lint/test + CD deploy) | Sau khi có test |
| 8 | README + architecture diagram | Tài liệu hóa dự án |

---

## 7. Cấu trúc thư mục hiện tại

```
dataops/
├── .env.example              ✅ Đầy đủ biến môi trường
├── .gitignore                ✅ Bảo vệ credential và data
├── PLAN.md                   ✅ Kế hoạch chi tiết (đã cập nhật IP thực tế)
├── install_docker.yml        ✅ Ansible: cài Docker trên 3 VM
├── docker-compose-airflow.yml  ✅ Prototype Airflow (test)
├── docker-compose-postgres.yml ✅ Prototype PostgreSQL (test)
├── dags/
│   └── hello_world_dag.py    ✅ DAG test xác nhận Airflow hoạt động
├── docker/
│   ├── dataops-vm1/
│   │   ├── docker-compose.yml              ⏳ Chưa làm
│   │   └── docker-compose-monitoring.yml  ⏳ Chưa làm
│   ├── dataops-vm2/
│   │   └── docker-compose.yml             ✅ PostgreSQL + Redis + MinIO
│   └── dataops-vm3/
│       └── docker-compose.yml             ⏳ Chưa làm
├── infra/ansible/
│   ├── inventory.ini          ✅ 3 VM đã khai báo
│   ├── playbook-vm1.yml       ⏳ Chưa làm
│   ├── playbook-vm2.yml       ⏳ Chưa làm
│   └── playbook-vm3.yml       ⏳ Chưa làm
├── pipeline/
│   ├── dags/
│   │   ├── ingest_csv_dag.py      ✅ Đã test, 5 rows đúng trong PostgreSQL
│   │   ├── ingest_api_dag.py      ✅ Đã viết, chưa test
│   │   └── data_quality_dag.py    ✅ Đã viết, chưa test
│   ├── etl/
│   │   ├── extract.py             ✅ extract_from_csv, extract_from_api
│   │   ├── transform.py           ✅ clean_data, normalize_columns, fill_missing, cast_types
│   │   ├── quality_check.py       ✅ QualityReport, run_quality_check, assert_quality
│   │   └── load.py                ✅ load_to_postgres, load_to_minio
│   ├── tests/
│   │   ├── test_transform.py      ⏳ Chưa viết
│   │   └── test_quality.py        ⏳ Chưa viết
│   └── requirements.txt           ✅ Đã viết (phiên bản tương thích Python 3.8)
└── monitoring/
    ├── prometheus/prometheus.yml      ⏳ Chưa viết
    ├── loki/loki-config.yml           ⏳ Chưa viết
    ├── alertmanager/alertmanager.yml  ⏳ Chưa viết
    └── grafana/dashboards/            ⏳ Chưa cấu hình
```
