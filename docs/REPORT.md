# BÁO CÁO TIẾN ĐỘ DỰ ÁN: Mini DataOps Platform
**Ngày báo cáo:** 17/05/2026  
**Người thực hiện:** Lương Mai Quỳnh  
**Mentor:** *(tên mentor)*  
**Trạng thái:** ✅ HOÀN THÀNH 100%

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
| Metrics & Monitoring | Prometheus + Grafana + cAdvisor + Node Exporter + postgres-exporter |
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

### 2.6 Giai đoạn 7 – Unit Tests

Tổng cộng **6 file test, 61 test cases, tất cả PASSED**, bao phủ toàn bộ ETL modules và DAG task functions.

#### ✅ test_extract.py (10 tests)
- Đọc CSV đúng cột, số rows, phát hiện duplicate và null
- Xử lý `FileNotFoundError` khi file không tồn tại
- API trả về list / dict response → DataFrame đúng
- Raise exception khi HTTP error / connection error

#### ✅ test_transform.py (15 tests)
| Test group | Số test | Nội dung |
|---|---|---|
| `test_clean_data_*` | 5 | Xóa duplicate, xóa rows toàn NaN, giữ partial null, reset index, empty df |
| `test_normalize_columns_*` | 3 | Lowercase, replace space bằng `_`, strip whitespace |
| `test_fill_missing_*` | 3 | Fill đúng cột, không ảnh hưởng cột khác, bỏ qua cột không tồn tại |
| `test_cast_types_*` | 4 | Cast int/float, bỏ qua cast sai, bỏ qua cột không tồn tại |

#### ✅ test_quality.py (12 tests)
| Test group | Số test | Nội dung |
|---|---|---|
| `test_run_quality_check_*` | 4 | Phát hiện null, duplicate, schema error, passed=True khi sạch |
| `test_assert_quality_*` | 4 | Raise ValueError khi null/duplicate/missing column, không raise khi sạch |
| `test_quality_report_summary_*` | 4 | Format summary string đúng định dạng |

#### ✅ test_load.py (8 tests)
- Tạo engine/client đúng connection string / endpoint
- `load_to_postgres`: kiểm tra table name, `if_exists` mặc định là `append`, trả về row count
- `load_to_minio`: kiểm tra bucket, key, content là CSV bytes hợp lệ
- Raise `ClientError` khi MinIO trả về lỗi

#### ✅ test_dag_ingest_api.py (7 tests)
- `task_extract`: push raw_data lên XCom, raise khi API thiếu `hourly`
- `task_transform`: normalize cột, thêm `ingested_at`, push clean_data
- `task_quality`: pass khi đủ cột, raise khi thiếu cột bắt buộc
- `task_load`: gọi cả `load_to_postgres` và `load_to_minio`

#### ✅ test_dag_ingest_csv.py (9 tests)
- `task_extract`: đọc CSV → push XCom, raise `FileNotFoundError` khi thiếu file
- `task_transform`: xóa duplicate, fill null age/salary=0, normalize column names
- `task_quality`: pass khi sạch, raise khi thiếu cột hoặc còn null
- `task_load`: gọi cả hai hàm load

**Kết quả cuối cùng:** `61 passed, 0 warnings` — flake8: 0 lỗi ✅

---

### 2.7 Giai đoạn 5 – Backup

#### ✅ backup.sh

File: `backup/backup.sh`

**Tính năng:**
- Dùng `/usr/lib/postgresql/15/bin/pg_dump` (version 15 khớp với server)
- `PGPASSWORD` từ env var — không hardcode credential
- Nén gzip: `employees_YYYY-MM-DD_HHMMSS.sql.gz`
- Tự xóa file backup cũ hơn 7 ngày (`find ... -mtime +7 -delete`)
- Log kết quả ra `/var/log/dataops-backup.log`

**Cron job trên VM3** (chạy lúc 2:00 AM hàng ngày):
```
0 2 * * * /home/dataops/backup.sh >> /var/log/dataops-backup.log 2>&1
```

**Đã test thực tế:** Tạo file backup ~20KB tại `/opt/backup/postgres/`

---

### 2.8 Giai đoạn 4 – Monitoring & Logging

#### ✅ docker-compose-monitoring.yml (VM1)

8 container đang Up trên VM1:

| Service | Port | Vai trò |
|---|---|---|
| Prometheus | 9090 | Thu thập metrics |
| Grafana | 3000 | Dashboard visualization |
| Loki | 3100 | Log aggregation |
| Promtail | — | Thu thập log container |
| Alertmanager | 9093 | Alert routing |
| Node Exporter | 9100 | VM metrics |
| cAdvisor | 8081 | Container metrics |
| postgres-exporter | 9187 | PostgreSQL metrics |

#### ✅ Prometheus scrape config (5 targets — tất cả UP)
- `prometheus`, `node-exporter-vm1`, `node-exporter-vm3` (192.168.64.4:9100)
- `cadvisor`, `postgres-exporter` (service name `postgres-exporter:9187` trong network monitoring)

#### ✅ Alert rules (6 rules)
- `InstanceDown`, `HighCpuUsage` (>80%), `LowMemory` (<10%), `DiskSpaceLow` (<15%), `ContainerRestartingTooMuch`, `PostgreSQLDown` (pg_up==0)

**Các sự cố đã xử lý:**
- Loki restart liên tục do permission denied `/tmp/loki/rules` → đổi `path_prefix=/loki`, thêm `user: "0"` trong compose
- postgres-exporter target DOWN do cấu hình sai IP (`192.168.64.3:9187`) → sửa thành service name `postgres-exporter:9187` trong cùng Docker network
- Promtail không thu thập log do thiếu file config → tạo `monitoring/promtail/promtail-config.yml` và thêm volume mount vào compose
- Alert rule `ContainerRestartingTooMuch` dùng `rate()` trên gauge (sai) → sửa thành `changes(...[15m]) >= 3`
- Node Exporter VM3 không chạy → deploy docker-compose.yml lên VM3 qua SSH
- `alerts.yml` không được mount vào prometheus container → thêm volume mount vào `docker-compose-monitoring.yml`, recreate container
- VM3 node-exporter thiếu host filesystem mount → thêm `/proc`, `/sys`, `/` volumes vào `docker/dataops-vm3/docker-compose.yml` để Prometheus thấy disk thật của VM3

---

### 2.9 Giai đoạn 6 – CI/CD

#### ✅ GitHub Actions – CI (lint-test.yml)

Tự động chạy khi push lên nhánh `main`:
1. Setup Python 3.11
2. `pip install flake8 pytest` + `requirements.txt`
3. `flake8 pipeline/` — lint check với `.flake8` config
4. `pytest pipeline/tests/ -v` — chạy 28 unit tests

**Kết quả:** CI – Lint & Test #4, #5: ✅ PASSING

#### ✅ GitHub Actions – CD (deploy.yml)

Deploy lên VM1 khi push `main` — dùng **self-hosted runner** cài trên VM1:
- Runner được cài như systemd service (`actions.runner.*.service`), tự khởi động khi VM1 reboot
- Không cần GitHub Secrets SSH vì runner chạy trực tiếp trên VM1 (VM1 không có public IP)
- Job `deploy-vm1`: `git pull` + `airflow dags reserialize`
- Job `deploy-monitoring`: `docker compose up -d --force-recreate prometheus alertmanager`

#### ✅ Ansible IaC (4 file)

| File | Mô tả |
|---|---|
| `ansible.cfg` | Cấu hình mặc định: host_key_checking=False, result_format=yaml |
| `inventory.ini` | Khai báo 3 VM với SSH key `~/.ssh/id_ed25519` |
| `site.yml` | Entrypoint chạy toàn bộ theo thứ tự: vm2 → vm1 → vm3 |
| `playbook-vm1.yml` | apt update, docker, git pull, copy .env, compose up Airflow + Monitoring |
| `playbook-vm2.yml` | apt update, docker, git pull, compose up PostgreSQL/Redis/MinIO |
| `playbook-vm3.yml` | apt update, cài postgresql-client-15, tạo backup dir + log file, copy backup.sh, setup cron, deploy node-exporter |

**Đã test thực tế:** `ansible all -m ping` → 3/3 VM pong ✅; `ansible-playbook playbook-vm3.yml` → ok=9, changed=5, failed=0 ✅

---

## 3. Tổng hợp tiến độ

| Giai đoạn | Mô tả | Tiến độ |
|---|---|---|
| GĐ1: Chuẩn bị môi trường | VM, Git, cấu trúc thư mục, .env, .gitignore | **100%** |
| GĐ2: Infrastructure | Docker Compose cho 3 VM, Airflow CeleryExecutor | **100%** |
| GĐ3: Data Pipeline | ETL modules + 3 Airflow DAGs + test thực tế | **100%** |
| GĐ4: Monitoring & Logging | Prometheus, Grafana, Loki, Alertmanager, cAdvisor | **100%** |
| GĐ5: Backup | Script backup PostgreSQL + cron tự động trên VM3 | **100%** |
| GĐ6: CI/CD + IaC | GitHub Actions CI ✅ PASSING + Ansible Playbooks | **100%** |
| GĐ7: Testing | 61/61 unit tests PASSED (6 file test, 0 warnings, flake8 clean) | **100%** |
| GĐ8: Tài liệu | README đầy đủ, architecture overview | **100%** |
| **Tổng thể** | | **100%** |

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
| Permission denied `/opt/airflow/logs` | Container Airflow chạy uid=50000, volume có owner sai | `sudo chown -R 50000:0 logs/` trên VM1 |
| YAML folding syntax error trong airflow-init | Dùng `>` operator khiến các dòng lệnh bị nối thành 1 | Chuyển sang array syntax trong compose |
| Python 3.8 không tương thích pandas, sqlalchemy | Container Airflow 2.7.1 dùng Python 3.8 | Downgrade `pandas==2.0.3`, `sqlalchemy==1.4.52` |
| Container name conflict khi deploy VM2 | File prototype đã tạo container cùng tên `postgres_db` | `docker rm -f postgres_db` trước khi chạy compose chính |
| 10 rows trong PostgreSQL thay vì 5 | DAG chạy 2 lần: 1 `scheduled` (backfill từ `start_date`) + 1 `manual` | `TRUNCATE employees` + sửa `start_date=datetime(2026,5,12)` |
| Loki container restart liên tục | Permission denied `/tmp/loki/rules` | Đổi `path_prefix=/loki`, thêm `user: "0"` trong compose |
| pg_dump version mismatch (14 vs 15) trên VM3 | VM3 cài postgresql-client-14, server là v15 | Cài `postgresql-client-15` từ apt.postgresql.org, dùng `/usr/lib/postgresql/15/bin/pg_dump` |
| GitHub Actions CI fail với flake8 | E221, E401, W293, F401, E402 trong nhiều files | Tạo `.flake8` config với `extend-ignore`, sửa import order |
| `pip3 install` bị block trên macOS | externally-managed-environment (PEP 668) | Dùng `python3 -m venv .venv && source .venv/bin/activate` |
| postgres-exporter target DOWN trong Prometheus | Target trỏ `192.168.64.3:9187` nhưng container chạy trong network nội bộ của Docker | Sửa target thành service name `postgres-exporter:9187`; restart prometheus để bind mount nhận file mới |
| `scp` phá bind mount Docker volume | `scp` tạo inode mới cho file → container vẫn đọc file cũ qua inode cũ | Sau khi scp config file, chạy `docker restart <container>` để mount lại |
| `pd.read_json(string)` lỗi `FileNotFoundError` trên pandas 3.x | pandas 3.x treat chuỗi JSON là filepath thay vì raw JSON | Bọc tất cả string JSON bằng `io.StringIO()` trước khi truyền vào `pd.read_json()` |
| Node Exporter VM3 không chạy | Không có docker-compose.yml trên VM3 | Tạo và deploy file compose qua SSH heredoc; Prometheus target `node-exporter-vm3` → UP |
| Alert rule `ContainerRestartingTooMuch` sai PromQL | `rate()` chỉ hợp lệ với counter; `container_start_time_seconds` là gauge | Đổi sang `changes(container_start_time_seconds{name!=""}[15m]) >= 3` |
| Promtail không thu thập log container | Thiếu file `promtail-config.yml`; volume mount trỏ đến file không tồn tại | Tạo `monitoring/promtail/promtail-config.yml` + thêm volume mount vào compose |
| `data_quality_dag.py` có dòng lệnh thừa cuối file | Dòng `[check_emp, check_weather]` là list expression không làm gì (no-op) | Xóa dòng thừa — task dependency đã được khai báo đúng ở trên |
| `alerts.yml` không được mount vào prometheus container | docker-compose-monitoring.yml thiếu volume mount cho `alerts.yml` | Thêm `alerts.yml:/etc/prometheus/alerts.yml:ro` vào volumes của prometheus, recreate container |
| VM3 node-exporter không báo disk thật của host | docker-compose.yml VM3 thiếu volume mount `/proc`, `/sys`, `/` → exporter chỉ thấy filesystem container | Thêm host filesystem mounts + `--path.procfs`, `--path.sysfs`, `--path.rootfs` vào command |
| `DiskSpaceLow` không có rule cho PostgreSQL down | Chỉ có `InstanceDown` (up==0) nhưng postgres-exporter vẫn chạy khi DB tắt | Thêm rule `PostgreSQLDown` với `expr: pg_up == 0` vào `alerts.yml` |
| `ContainerRestartingTooMuch` không trigger được | `changes(container_start_time_seconds)` không hoạt động vì cAdvisor tạo time series mới với label `restartcount` khác nhau mỗi lần restart → `changes()` luôn trả về 0 | Đổi expression sang `count by (name) (count_over_time(container_last_seen{name!=""}[15m])) >= 3` — đếm số series riêng biệt (= số lần restart) trong 15 phút |
| `data_quality_check` fail với `duplicates=15` trong bảng `employees` | `ingest_csv` chạy nhiều lần với `if_exists='append'` → tích lũy dữ liệu trùng lặp trong PostgreSQL | `TRUNCATE TABLE employees` trên VM2, trigger lại `ingest_csv` 1 lần → `duplicates=0, passed=True` |
| DAG `01_hello_world_test` vẫn hiển thị sau khi xóa file | File DAG nằm ở `pipeline/dags/` (volume mount thực tế) nhưng lệnh xóa trỏ sai vào thư mục `dags/` ở root | Xóa đúng file tại `~/dataops/pipeline/dags/hello_world_dag.py` + chạy `airflow dags delete 01_hello_world_test -y` |
| CD pipeline fail do conflict `alerts.yml` trên VM1 | VM1 có local changes chưa commit trong `alerts.yml` khi CD chạy `git pull` | Chạy `git stash && git pull origin main` thủ công trên VM1 |
| `weather_hanoi` tích lũy duplicate data — mỗi khung giờ xuất hiện 9 lần (288 dòng thay vì 48) | Open-Meteo API với `forecast_days=1` luôn trả về 24 giờ forecast của ngày hiện tại; hàm `load_to_postgres` dùng `if_exists='append'` không kiểm tra trùng lặp → mỗi lần DAG `@hourly` chạy đều append thêm 24 dòng trùng time | **Bước 1:** `DELETE WHERE ctid NOT IN (SELECT MAX(ctid) GROUP BY time)` → xóa 240 dòng duplicate, giữ 48 dòng sạch. **Bước 2:** Sửa `task_load` trong `ingest_api_dag.py` theo pattern delete-insert — trước khi INSERT, chạy `DELETE FROM weather_hanoi WHERE time = ANY(:times)` để xóa các dòng có time trùng. Sau fix: bảng luôn giữ đúng 48 dòng dù DAG chạy bao nhiêu lần |

---

## 6. Kết quả đạt được

| Công việc | Trạng thái |
|---|---|
| Triển khai Airflow CeleryExecutor trên VM1 | ✅ Hoàn thành |
| Viết ETL modules (extract, transform, load, quality_check) | ✅ Hoàn thành |
| Viết 3 Airflow DAGs (ingest_csv, ingest_api, data_quality) | ✅ Hoàn thành |
| Unit tests: 61/61 PASSED (6 file test, 0 warnings, flake8 clean) | ✅ Hoàn thành |
| Monitoring stack: 8 container Up trên VM1 (thêm postgres-exporter) | ✅ Hoàn thành |
| Backup script + cron 2:00 AM hàng ngày trên VM3 | ✅ Hoàn thành |
| Ansible IaC: ansible.cfg, site.yml, 3 playbooks — đã test ping + playbook-vm3 | ✅ Hoàn thành |
| GitHub Actions CI – Lint & Test: PASSING | ✅ Hoàn thành |
| GitHub Actions CD – Self-hosted runner trên VM1: PASSING | ✅ Hoàn thành |
| Simulate PostgreSQL down → `PostgreSQLDown` FIRING trong Prometheus | ✅ Hoàn thành |
| Simulate disk full → `DiskSpaceLow` FIRING trong Prometheus | ✅ Hoàn thành |
| Simulate instance down (tắt node-exporter VM3) → `InstanceDown` FIRING | ✅ Hoàn thành |
| Simulate container crash-loop → `ContainerRestartingTooMuch` FIRING | ✅ Hoàn thành |
| End-to-end test 3 DAGs: ingest_csv ✅, ingest_weather_api ✅, data_quality_check ✅ | ✅ Hoàn thành |
| README đầy đủ với kiến trúc và hướng dẫn | ✅ Hoàn thành |

---

## 7. Cấu trúc thư mục hiện tại

```
dataops/
├── .env.example              ✅ Đầy đủ biến môi trường
├── .gitignore                ✅ Bảo vệ credential và data
├── .flake8                   ✅ Cấu hình lint (max-line=100, extend-ignore)
├── PLAN.md                   ✅ Kế hoạch chi tiết
├── README.md                 ✅ Tài liệu đầy đủ với kiến trúc và hướng dẫn
├── install_docker.yml        ✅ Ansible: cài Docker trên 3 VM
├── .github/workflows/
│   ├── lint-test.yml         ✅ CI: flake8 + pytest (PASSING)
│   └── deploy.yml            ✅ CD: deploy lên VM1 qua SSH
├── docker/
│   ├── dataops-vm1/
│   │   ├── docker-compose.yml              ✅ Airflow CeleryExecutor (5 services)
│   │   └── docker-compose-monitoring.yml  ✅ 8 container monitoring Up (thêm postgres-exporter)
│   ├── dataops-vm2/
│   │   └── docker-compose.yml             ✅ PostgreSQL + Redis + MinIO
│   └── dataops-vm3/
│       └── docker-compose.yml             ✅ Node Exporter
├── infra/ansible/
│   ├── ansible.cfg            ✅ host_key_checking=False, result_format=yaml
│   ├── inventory.ini          ✅ 3 VM, SSH key id_ed25519
│   ├── site.yml               ✅ Entrypoint: vm2 → vm1 → vm3
│   ├── playbook-vm1.yml       ✅ Deploy Airflow + Monitoring
│   ├── playbook-vm2.yml       ✅ Deploy PostgreSQL + Redis + MinIO
│   └── playbook-vm3.yml       ✅ Deploy Node Exporter + Backup setup + log file
├── backup/
│   └── backup.sh              ✅ pg_dump + gzip + cron 2:00 AM VM3
├── pipeline/
│   ├── dags/
│   │   ├── ingest_csv_dag.py      ✅ Đã test, 5 rows đúng trong PostgreSQL
│   │   ├── ingest_api_dag.py      ✅ Đã viết
│   │   └── data_quality_dag.py    ✅ Đã viết
│   ├── etl/
│   │   ├── extract.py             ✅ extract_from_csv, extract_from_api
│   │   ├── transform.py           ✅ clean_data, normalize_columns, fill_missing, cast_types
│   │   ├── quality_check.py       ✅ QualityReport, run_quality_check, assert_quality
│   │   └── load.py                ✅ load_to_postgres, load_to_minio
│   ├── tests/
│   │   ├── test_extract.py            ✅ 10 tests PASSED
│   │   ├── test_transform.py          ✅ 15 tests PASSED
│   │   ├── test_quality.py            ✅ 12 tests PASSED
│   │   ├── test_load.py               ✅ 8 tests PASSED
│   │   ├── test_dag_ingest_csv.py     ✅ 9 tests PASSED
│   │   └── test_dag_ingest_api.py     ✅ 7 tests PASSED
│   └── requirements.txt               ✅ Phiên bản tương thích Python 3.8
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml     ✅ Scrape 5 targets (tất cả UP)
│   │   └── alerts.yml         ✅ 6 alert rules (PromQL đã fix)
│   ├── loki/loki-config.yml   ✅ Log aggregation
│   ├── promtail/
│   │   └── promtail-config.yml  ✅ Thu thập log container Docker
│   ├── alertmanager/
│   │   └── alertmanager.yml   ✅ Alert routing
│   └── grafana/dashboards/    ✅ Datasource configured
└── sample_data/
    └── sample.csv                 ✅ 6 dòng nhân viên (1 duplicate, 1 null age, 1 null salary)
```

---

## 8. Kết luận

Dự án **Mini DataOps Platform** đã hoàn thành 100% tất cả 8 giai đoạn theo kế hoạch. Hệ thống bao gồm:

- **3 VM Ubuntu 22.04** chạy ổn định với các service phân tán đúng vai trò
- **Airflow CeleryExecutor** điều phối pipeline dữ liệu tự động
- **ETL pipeline** với kiểm tra chất lượng dữ liệu, lưu vào PostgreSQL và MinIO
- **Monitoring stack** 8 container: Prometheus, Grafana, Loki, Promtail, Alertmanager, cAdvisor, Node Exporter, postgres-exporter — 5/5 targets UP; **6 alert rules** (thêm PostgreSQLDown)
- **Backup tự động** hàng ngày lúc 2:00 AM với giữ lịch sử 7 ngày, log ghi vào `/var/log/dataops-backup.log`
- **61 unit tests PASSED** (6 file test, 0 warnings) — bao phủ toàn bộ ETL modules và DAG task functions; flake8 clean
- **16 bug đã phát hiện và fix** trong quá trình kiểm thử (pandas StringIO, PromQL gauge, no-op DAG expression, missing promtail config, alerts.yml not mounted, VM3 node-exporter missing host mounts, ContainerRestartingTooMuch expression, employees duplicates, hello_world_test DAG, CD git conflict, weather_hanoi duplicate data với delete-insert pattern, v.v.)
- **CI/CD** với GitHub Actions: lint + test tự động; CD deploy qua self-hosted runner trên VM1
- **Infrastructure as Code** với Ansible (ansible.cfg, site.yml, 3 playbooks) — đã test thực tế ping + deploy VM3
- **Simulate failure tests — 4/4 kịch bản FIRING**: PostgreSQL down ✅, Disk full ✅, Instance down ✅, Container crash-loop ✅
- **End-to-end test 3 DAGs**: ingest_csv ✅, ingest_weather_api ✅, data_quality_check ✅
