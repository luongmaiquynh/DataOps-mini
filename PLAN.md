# KẾ HOẠCH THỰC HIỆN ĐỀ TÀI: Mini DataOps Platform

## MỤC TIÊU TỔNG QUAN
Xây dựng nền tảng DataOps mini hoàn chỉnh bao gồm:
- Thu thập dữ liệu từ CSV / REST API
- Xử lý dữ liệu tự động hằng ngày
- Lưu trữ tập trung (PostgreSQL + MinIO)
- Dashboard monitoring & logging tập trung
- Backup định kỳ + cảnh báo lỗi
- Triển khai bằng container (Docker)
- CI/CD + Infrastructure as Code

---

## PHẦN 1 – KIẾN THỨC CẦN NẮM TRƯỚC KHI LÀM

### 1.1 Linux & VM
| Chủ đề | Nội dung cần biết |
|---|---|
| Ubuntu Server 22.04 | Cài đặt, cấu hình SSH, UFW firewall, systemd |
| Networking | IP tĩnh, /etc/hosts, ping giữa các VM, port forwarding |
| File system | Mount disk, df -h, du, cron, journalctl |
| User & Permission | sudo, adduser, chmod, chown |

### 1.2 Docker & Docker Compose
| Chủ đề | Nội dung cần biết |
|---|---|
| Docker cơ bản | image, container, volume, network, Dockerfile |
| Docker Compose | docker-compose.yml, service dependencies, env_file |
| Networking trong Compose | bridge network, service discovery bằng tên service |
| Persistent Volume | named volume, bind mount |
| Healthcheck | healthcheck trong compose, depends_on: condition |
| Restart Policy | restart: always, on-failure |
| Secret Management | .env file, Docker secrets cơ bản |

### 1.3 Data Pipeline & DataOps
| Chủ đề | Nội dung cần biết |
|---|---|
| Python cơ bản | pandas, requests, logging, argparse |
| ETL concept | Extract → Transform → Load |
| Data validation | kiểm tra null, duplicate, schema, invalid value |
| Apache Airflow | DAG, Operator (PythonOperator, BashOperator), scheduler, webserver |
| Airflow với Docker | docker-compose official Airflow, kết nối PostgreSQL metadata |
| MinIO | Object storage tương thích S3, boto3, bucket, object |
| PostgreSQL | Tạo DB/table, psycopg2, SQLAlchemy, indexing cơ bản |
| Redis | Làm message broker / cache, dùng với Airflow Celery Executor |

### 1.4 Monitoring & Logging
| Chủ đề | Nội dung cần biết |
|---|---|
| Prometheus | scrape config, metrics endpoint, PromQL cơ bản |
| Grafana | dashboard, data source Prometheus, alert rule |
| Loki + Promtail | thu thập log container, query log trong Grafana |
| cAdvisor | metrics container (CPU, RAM, network) |
| Node Exporter | metrics VM (disk, CPU, RAM hệ thống) |
| Alertmanager | gửi alert qua email / webhook |

### 1.5 CI/CD & IaC
| Chủ đề | Nội dung cần biết |
|---|---|
| Git & GitHub | branch, commit, pull request, Actions workflow |
| GitHub Actions | .github/workflows/, jobs, steps, runner |
| Lint | flake8 / ruff cho Python |
| Unit Test | pytest, test ETL function |
| Ansible | inventory, playbook, task, module (apt, docker_compose) |
| Terraform (optional) | provider, resource, variable |

---

## PHẦN 2 – KIẾN TRÚC HỆ THỐNG

```
Máy macOS (chỉ: VS Code + git + ssh)
         │
         ▼
┌──────────────────────────────────────────────────┐
│  VM1 – DataOps Master / CI-CD / Monitoring       │
│  192.168.56.11                                   │
│  Airflow | Grafana | Prometheus | Loki | Alertmgr │
└──────────────────────────────────────────────────┘
         │ mạng nội bộ 192.168.56.x
         ▼
┌──────────────────────────────────────────────────┐
│  VM2 – Database + Data Processing                │
│  192.168.56.12                                   │
│  PostgreSQL | Redis | MinIO | Airflow Worker     │
└──────────────────────────────────────────────────┘
         │ mạng nội bộ 192.168.56.x
         ▼
┌──────────────────────────────────────────────────┐
│  VM3 – Optional Worker / Storage / Backup        │
│  192.168.56.13                                   │
│  Airflow Worker | Node Exporter | Backup         │
└──────────────────────────────────────────────────┘
```

> **QUAN TRỌNG:** Tất cả service chạy trên VM. Máy macOS chỉ dùng để viết code, git, ssh.

---

## PHẦN 3 – CẤU TRÚC THƯ MỤC DỰ ÁN

```
dataops/
├── .github/workflows/
│   ├── lint-test.yml
│   └── deploy.yml
├── infra/ansible/
│   ├── inventory.ini
│   ├── playbook-vm1.yml
│   ├── playbook-vm2.yml
│   └── playbook-vm3.yml
├── docker/
│   ├── dataops-vm1/
│   │   ├── docker-compose.yml           # Airflow
│   │   └── docker-compose-monitoring.yml
│   ├── dataops-vm2/
│   │   └── docker-compose.yml           # PostgreSQL + Redis + MinIO
│   └── dataops-vm3/
│       └── docker-compose.yml           # Airflow Worker + Backup
├── pipeline/
│   ├── dags/
│   │   ├── ingest_api_dag.py
│   │   ├── ingest_csv_dag.py
│   │   └── data_quality_dag.py
│   ├── etl/
│   │   ├── extract.py
│   │   ├── transform.py
│   │   ├── load.py
│   │   └── quality_check.py
│   ├── tests/
│   │   ├── test_transform.py
│   │   └── test_quality.py
│   └── requirements.txt
├── monitoring/
│   ├── prometheus/prometheus.yml
│   ├── grafana/dashboards/
│   ├── loki/loki-config.yml
│   └── alertmanager/alertmanager.yml
├── backup/backup.sh
├── sample_data/sample.csv
├── .env.example
├── .gitignore
└── README.md
```

---

## PHẦN 4 – CÁC BƯỚC THỰC HIỆN CHI TIẾT

### GIAI ĐOẠN 1 – Chuẩn bị môi trường (1–2 ngày)

#### Bước 1.1 – Tạo và cấu hình VM (dùng UTM)

> Cần cài trước: **UTM** (miễn phí, https://mac.getutm.app) + Ubuntu Server 22.04 **ARM64** ISO (https://cdimage.ubuntu.com/releases/22.04/release/) — chọn file `ubuntu-22.04.x-live-server-arm64.iso` (bắt buộc với Apple Silicon M-series)

**A. Tạo VM1 trong UTM**
1. Mở UTM → nhấn **+** (Create a New Virtual Machine)
2. Chọn **Virtualize** (không phải Emulate — bắt buộc với Apple Silicon)
3. Chọn **Linux** → nhấn **Browse** → chọn file `ubuntu-22.04.x-live-server-arm64.iso` → Continue
4. Hardware:
   - Memory: **8192 MB** (8 GB)
   - CPU Cores: **4**
5. Storage: **80 GB** → Continue
6. Shared Directory: bỏ qua (Skip) → Continue
7. Summary: đặt tên `dataops-vm1` → **Save**
8. Cấu hình Network (quan trọng):
   - Vào Settings VM → **Network** → Interface 1: **Shared Network** (NAT – để VM ra internet)
   - Nhấn **New** → thêm Interface 2: **Host Only** (để SSH từ macOS)
9. Nhấn **▶ (Play)** để Start → boot từ ISO

**B. Cài Ubuntu Server 22.04**
```
1. Ngôn ngữ: English
2. Type: Ubuntu Server (không chọn minimized)
3. Network: DHCP tự động
4. Storage: Use entire disk → 80GB
5. VM1: server name: vm1 | username: dataops
   VM2: server name: vm2 | username: dataops
   VM3: server name: vm3 | username: dataops
6. SSH: ✅ Install OpenSSH server
7. Reboot → tháo ISO
```

**C. Tạo VM2 và VM3** – Lặp lại A+B, hoặc Clone VM1 trong UTM (chuột phải vào VM trong danh sách → **Clone**):

Sau khi clone/cài xong, đổi hostname trên từng VM:
```bash
# Trên VM2
sudo hostnamectl set-hostname vm2
sudo sed -i 's/vm1/vm2/g' /etc/hosts

# Trên VM3
sudo hostnamectl set-hostname vm3
sudo sed -i 's/vm1/vm3/g' /etc/hosts
```

**D. Đặt IP tĩnh (Host-Only interface)**

> Trước tiên, kiểm tra tên interface thực tế trong VM:
> ```bash
> ip addr show
> ```
> UTM thường dùng `enp0s1` (NAT/Shared) và `enp0s2` (Host-only), nhưng có thể là `eth0`/`eth1` tùy phiên bản Ubuntu.

Trên VM1:
```bash
sudo nano /etc/netplan/00-installer-config.yaml
```
```yaml
network:
  version: 2
  ethernets:
    enp0s1:              # Adapter 1 – Shared Network (NAT)
      dhcp4: true
    enp0s2:              # Adapter 2 – Host Only (SSH từ macOS)
      dhcp4: no
      addresses:
        - 192.168.56.11/24
```
```bash
sudo netplan apply
```

> **Lưu ý:** Kiểm tra subnet Host Only của UTM trên macOS:
> ```bash
> # Chạy trên macOS
> ifconfig | grep -A2 bridge
> ```
> Nếu subnet khác `192.168.56.x`, điều chỉnh IP cho phù hợp.

Trên VM2 (thay `.11` thành `.12`):
```bash
sudo netplan apply
ping 192.168.56.11   # test từ VM2
```

**E. Thêm hostname /etc/hosts (cả 3 VM)**
```bash
sudo tee -a /etc/hosts << 'EOF'
192.168.56.11   vm1 dataops-master
192.168.56.12   vm2 dataops-db
192.168.56.13   vm3 dataops-worker
EOF
```

**F. SSH key từ macOS**
```bash
ssh-keygen -t ed25519 -C "dataops"
ssh-copy-id dataops@192.168.56.11
ssh-copy-id dataops@192.168.56.12
ssh-copy-id dataops@192.168.56.13
```

Thêm vào `~/.ssh/config`:
```
Host vm1
    HostName 192.168.56.11
    User dataops
    IdentityFile ~/.ssh/id_ed25519

Host vm2
    HostName 192.168.56.12
    User dataops
    IdentityFile ~/.ssh/id_ed25519

Host vm3
    HostName 192.168.56.13
    User dataops
    IdentityFile ~/.ssh/id_ed25519
```

**G. Mở port UFW**

VM1:
```bash
sudo ufw allow OpenSSH
sudo ufw allow 8080/tcp && sudo ufw allow 3000/tcp
sudo ufw allow 9090/tcp && sudo ufw allow 3100/tcp
sudo ufw enable
```

VM2:
```bash
sudo ufw allow OpenSSH
sudo ufw allow 5432/tcp && sudo ufw allow 6379/tcp
sudo ufw allow 9000/tcp && sudo ufw allow 9001/tcp
sudo ufw enable
```

VM3:
```bash
sudo ufw allow OpenSSH
sudo ufw allow 9100/tcp   # node-exporter
sudo ufw enable
```

**H. Cập nhật hệ thống (cả 3 VM)**
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git htop net-tools
```

**I. Tóm tắt 3 VM**

| | VM1 | VM2 | VM3 |
|---|---|---|---|
| IP | 192.168.56.11 | 192.168.56.12 | 192.168.56.13 |
| Hostname | vm1 | vm2 | vm3 |
| Username | dataops | dataops | dataops |
| Vai trò | DataOps Master / CI-CD / Monitoring | Database + Data Processing | Optional Worker / Storage / Backup |
| Services | Airflow, Grafana, Prometheus, Loki, Alertmanager | PostgreSQL, Redis, MinIO, Airflow Worker | Airflow Worker, Node Exporter, Backup |

---

#### Bước 1.2 – Cài Docker (cả 3 VM)
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
docker --version && docker compose version
```

---

#### Bước 1.3 – Khởi tạo Git Repository

**A. Tạo repo trên GitHub**
1. github.com → + → New repository
2. Name: `dataops-platform` | Visibility: Private
3. KHÔNG tick Add README → Create repository

**B. Cài Git trên macOS**
```bash
git --version
brew install git   # nếu chưa có
git config --global user.name "Tên của bạn"
git config --global user.email "email@github.com"
```

**C. Tạo cấu trúc thư mục**
```bash
cd /Users/luongmaiquynh/Documents/dataops

mkdir -p .github/workflows infra/ansible \
         docker/dataops-vm1 docker/dataops-vm2 docker/dataops-vm3 \
         pipeline/dags pipeline/etl pipeline/tests \
         monitoring/prometheus monitoring/grafana/dashboards \
         monitoring/loki monitoring/alertmanager \
         backup sample_data

find . -type d -not -path './.git/*' | xargs -I{} touch {}/.gitkeep
touch pipeline/requirements.txt
```

**D. Tạo .gitignore**
```bash
cat > .gitignore << 'EOF'
.env
__pycache__/
*.py[cod]
.venv/
venv/
*.log
.DS_Store
*.csv
!sample_data/sample.csv
EOF
```

**E. Tạo .env.example**
```bash
cat > .env.example << 'EOF'
POSTGRES_USER=dataops
POSTGRES_PASSWORD=***REMOVED***
POSTGRES_DB=dataops_db
POSTGRES_HOST=192.168.56.12
POSTGRES_PORT=5432
REDIS_HOST=192.168.56.12
REDIS_PORT=6379
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=***REMOVED***
MINIO_HOST=192.168.56.12
MINIO_PORT=9000
MINIO_BUCKET=dataops-lake
AIRFLOW__CORE__FERNET_KEY=your-fernet-key-here
AIRFLOW__WEBSERVER__SECRET_KEY=your-secret-key-here
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://dataops:***REMOVED***@192.168.56.12:5432/airflow_db
AIRFLOW__CELERY__BROKER_URL=redis://192.168.56.12:6379/0
AIRFLOW__CELERY__RESULT_BACKEND=db+postgresql://dataops:***REMOVED***@192.168.56.12:5432/airflow_db
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=***REMOVED***
VM3_HOST=192.168.56.13
BACKUP_DIR=/opt/backup
EOF
```

**F. Commit và push**
```bash
git init
git branch -M main
git add .
git commit -m "feat: initial project structure"
git remote add origin https://github.com/YOUR_USERNAME/dataops-platform.git
git push -u origin main
```

> Lần đầu push: dùng Personal Access Token thay mật khẩu
> GitHub → Settings → Developer settings → Personal access tokens → Generate → tick `repo`

---

### GIAI ĐOẠN 2 – Triển khai Infrastructure (2–3 ngày)

#### Bước 2.1 – VM2: docker/dataops-vm2/docker-compose.yml
```yaml
services:
  postgres:
    image: postgres:15
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      retries: 5
    networks:
      - dataops-net

  redis:
    image: redis:7-alpine
    restart: always
    networks:
      - dataops-net

  minio:
    image: minio/minio:latest
    restart: always
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    networks:
      - dataops-net

volumes:
  postgres_data:
  minio_data:

networks:
  dataops-net:
    driver: bridge
```

Deploy lên VM2:
```bash
scp -r . dataops@192.168.56.12:/opt/dataops
ssh vm2
cd /opt/dataops && cp .env.example .env && nano .env
docker compose -f docker/dataops-vm2/docker-compose.yml up -d
docker compose -f docker/dataops-vm2/docker-compose.yml ps
```

#### Bước 2.2 – VM1: Apache Airflow
- [ ] Tải docker-compose.yaml chính thức từ Airflow
- [ ] Chỉnh AIRFLOW__DATABASE__SQL_ALCHEMY_CONN trỏ về PostgreSQL VM2
- [ ] Chỉnh AIRFLOW__CELERY__BROKER_URL trỏ về Redis VM2
- [ ] Mount pipeline/dags/ vào container
- [ ] Chạy: `docker compose up airflow-init` rồi `docker compose up -d`

Truy cập: http://192.168.56.11:8080

#### Bước 2.3 – VM1: Monitoring Stack
```bash
docker compose -f docker/dataops-vm1/docker-compose-monitoring.yml up -d
# Grafana: http://192.168.56.11:3000
```

#### Bước 2.4 – VM3: Airflow Worker + Backup (docker/dataops-vm3/docker-compose.yml)
```yaml
services:
  airflow-worker:
    image: apache/airflow:2.9.0
    restart: always
    command: celery worker
    environment:
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: ${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN}
      AIRFLOW__CELERY__BROKER_URL: ${AIRFLOW__CELERY__BROKER_URL}
      AIRFLOW__CELERY__RESULT_BACKEND: ${AIRFLOW__CELERY__RESULT_BACKEND}
    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
    networks:
      - dataops-net

  node-exporter:
    image: prom/node-exporter:latest
    restart: always
    ports:
      - "9100:9100"
    networks:
      - dataops-net

networks:
  dataops-net:
    driver: bridge
```

Deploy lên VM3:
```bash
ssh vm3
mkdir -p /opt/dataops && cd /opt/dataops
# copy .env từ VM1 hoặc tạo mới
docker compose -f docker/dataops-vm3/docker-compose.yml up -d
```

---

### GIAI ĐOẠN 3 – Xây dựng Data Pipeline (3–4 ngày)

#### Bước 3.1 – Nguồn dữ liệu

| API | URL | Ghi chú |
|---|---|---|
| Open-Meteo | https://api.open-meteo.com | Thời tiết, miễn phí, không cần key |
| CoinGecko | https://api.coingecko.com | Giá crypto |
| REST Countries | https://restcountries.com | Dữ liệu quốc gia |

#### Bước 3.2 – Module ETL

**pipeline/etl/extract.py**
```python
import requests, pandas as pd, logging
logger = logging.getLogger(__name__)

def extract_from_api(url: str, params: dict = None) -> pd.DataFrame:
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        logger.info(f"Extracted from {url}")
        return pd.DataFrame(resp.json())
    except Exception as e:
        logger.error(f"Extract failed: {e}")
        raise

def extract_from_csv(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    logger.info(f"Loaded {len(df)} rows from {filepath}")
    return df
```

**pipeline/etl/transform.py**
```python
import pandas as pd, logging
logger = logging.getLogger(__name__)

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    initial = len(df)
    df = df.drop_duplicates().dropna(how='all')
    logger.info(f"Removed {initial - len(df)} rows")
    return df

def normalize_data(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    for col, dtype in schema.items():
        if col in df.columns:
            df[col] = df[col].astype(dtype)
    return df
```

**pipeline/etl/quality_check.py**
```python
import pandas as pd
from dataclasses import dataclass
from typing import List

@dataclass
class QualityReport:
    null_count: dict
    duplicate_count: int
    schema_errors: List[str]
    invalid_values: dict
    passed: bool

def run_quality_check(df: pd.DataFrame, expected_schema: dict) -> QualityReport:
    null_count = df.isnull().sum().to_dict()
    duplicate_count = int(df.duplicated().sum())
    schema_errors = [c for c in expected_schema if c not in df.columns]
    invalid_values = {}
    passed = (
        all(v == 0 for v in null_count.values()) and
        duplicate_count == 0 and
        len(schema_errors) == 0
    )
    return QualityReport(null_count, duplicate_count, schema_errors, invalid_values, passed)
```

**pipeline/etl/load.py**
```python
import pandas as pd, logging
logger = logging.getLogger(__name__)

def load_to_postgres(df: pd.DataFrame, table: str, engine):
    df.to_sql(table, engine, if_exists='append', index=False)
    logger.info(f"Loaded {len(df)} rows to '{table}'")

def load_to_minio(df: pd.DataFrame, bucket: str, object_name: str, client):
    body = df.to_csv(index=False).encode()
    client.put_object(Bucket=bucket, Key=object_name, Body=body)
    logger.info(f"Uploaded to s3://{bucket}/{object_name}")
```

#### Bước 3.3 – Airflow DAG

**pipeline/dags/ingest_api_dag.py**
```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from etl.extract import extract_from_api
from etl.transform import clean_data
from etl.load import load_to_postgres, load_to_minio
from etl.quality_check import run_quality_check

default_args = {
    'owner': 'dataops',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='ingest_weather_api',
    default_args=default_args,
    schedule_interval='@hourly',
    start_date=datetime(2026, 1, 1),
    catchup=False,
) as dag:
    extract   = PythonOperator(task_id='extract',       python_callable=extract_from_api)
    quality   = PythonOperator(task_id='quality_check', python_callable=run_quality_check)
    transform = PythonOperator(task_id='transform',     python_callable=clean_data)
    load      = PythonOperator(task_id='load',          python_callable=load_to_postgres)

    extract >> quality >> transform >> load
```

#### Bước 3.4 – pipeline/requirements.txt
```
apache-airflow==2.9.0
pandas==2.2.0
requests==2.31.0
sqlalchemy==2.0.0
psycopg2-binary==2.9.9
boto3==1.34.0
redis==5.0.0
```

---

### GIAI ĐOẠN 4 – Monitoring & Logging (1–2 ngày)

#### Bước 4.1 – monitoring/prometheus/prometheus.yml
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100', '192.168.56.12:9100']
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
  - job_name: 'postgres-exporter'
    static_configs:
      - targets: ['postgres-exporter:9187']
```

#### Bước 4.2 – Grafana Dashboard
- [ ] Datasource Prometheus: http://prometheus:9090
- [ ] Datasource Loki: http://loki:3100
- [ ] Import Node Exporter dashboard (ID: 1860)
- [ ] Import cAdvisor dashboard (ID: 14282)
- [ ] Tạo custom dashboard: job status, rows ingested, runtime

#### Bước 4.3 – monitoring/alertmanager/alertmanager.yml
```yaml
route:
  receiver: 'email-alert'
receivers:
  - name: 'email-alert'
    email_configs:
      - to: 'your@email.com'
        from: 'alertmanager@dataops.local'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'your@email.com'
        auth_password: 'app-password'
```

---

### GIAI ĐOẠN 5 – Backup (0.5 ngày)

**backup/backup.sh**
```bash
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backup/postgres"
mkdir -p $BACKUP_DIR

docker exec postgres pg_dumpall -U $POSTGRES_USER > "$BACKUP_DIR/backup_$TIMESTAMP.sql"
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
echo "[$(date)] Backup completed: backup_$TIMESTAMP.sql"
```

Cron trên VM2:
```bash
chmod +x /opt/dataops/backup/backup.sh
crontab -e
# Thêm dòng:
0 2 * * * /opt/dataops/backup/backup.sh >> /var/log/dataops-backup.log 2>&1
```

---

### GIAI ĐOẠN 6 – CI/CD (1–2 ngày)

#### .github/workflows/lint-test.yml
```yaml
name: CI – Lint & Test
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
jobs:
  lint-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r pipeline/requirements.txt flake8 pytest
      - run: flake8 pipeline/ --max-line-length=100
      - run: pytest pipeline/tests/ -v
```

#### .github/workflows/deploy.yml
```yaml
name: CD – Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VM1_HOST }}
          username: ${{ secrets.VM1_USER }}
          key: ${{ secrets.VM1_SSH_KEY }}
          script: |
            cd /opt/dataops
            git pull origin main
            docker compose -f docker/dataops-vm1/docker-compose.yml up -d --force-recreate
```

> Thêm secrets: GitHub repo → Settings → Secrets → VM1_HOST, VM1_USER, VM1_SSH_KEY

#### infra/ansible/inventory.ini
```ini
[vm1]
192.168.56.11 ansible_user=dataops

[vm2]
192.168.56.12 ansible_user=dataops

[vm3]
192.168.56.13 ansible_user=dataops

[all:vars]
ansible_python_interpreter=/usr/bin/python3
```

---

### GIAI ĐOẠN 7 – Testing (1 ngày)

**pipeline/tests/test_transform.py**
```python
import pandas as pd
from etl.transform import clean_data

def test_remove_duplicates():
    df = pd.DataFrame({'a': [1, 1, 2], 'b': ['x', 'x', 'y']})
    assert len(clean_data(df)) == 2

def test_remove_all_null_rows():
    df = pd.DataFrame({'a': [1, None], 'b': [2, None]})
    assert len(clean_data(df)) == 1
```

**Kiểm tra vận hành**

| Test | Cách làm | Kết quả mong đợi |
|---|---|---|
| Restart VM | `sudo reboot` | Services tự start lại |
| Restart container | `docker restart postgres` | Kết nối lại tự động |
| Simulate failure | `docker stop airflow-scheduler` | Alert gửi email |
| Disk full | `fallocate -l 70G /tmp/fill` | Alert disk > 90% |

---

### GIAI ĐOẠN 8 – Tài liệu (0.5 ngày)
- [ ] Viết README.md đầy đủ (cài đặt, cấu hình, chạy)
- [ ] Vẽ sơ đồ kiến trúc (draw.io)
- [ ] Kiểm tra .env.example đủ biến
- [ ] Kiểm tra không commit credential: `git log --all --full-history -- .env`

---

## PHẦN 5 – TIMELINE TỔNG THỂ

| Giai đoạn | Thời gian ước tính | Mức độ khó |
|---|---|---|
| GĐ1: Chuẩn bị môi trường | 1–2 ngày | ⭐⭐ |
| GĐ2: Triển khai Infrastructure | 2–3 ngày | ⭐⭐⭐ |
| GĐ3: Xây dựng Data Pipeline | 3–4 ngày | ⭐⭐⭐⭐ |
| GĐ4: Monitoring & Logging | 1–2 ngày | ⭐⭐⭐ |
| GĐ5: Backup | 0.5 ngày | ⭐⭐ |
| GĐ6: CI/CD + IaC | 1–2 ngày | ⭐⭐⭐ |
| GĐ7: Testing | 1 ngày | ⭐⭐ |
| GĐ8: Tài liệu | 0.5 ngày | ⭐ |
| **Tổng** | **10–15 ngày** | |

---

## PHẦN 6 – STACK CÔNG NGHỆ

| Layer | Công nghệ | Chạy ở đâu |
|---|---|---|
| OS | Ubuntu Server 22.04 | VM1 + VM2 + VM3 |
| Container | Docker + Compose v2 | VM1 + VM2 + VM3 |
| Workflow | Apache Airflow 2.x (CeleryExecutor) | VM1 (scheduler/webserver) + VM2 & VM3 (worker) |
| Message Broker | Redis 7 | VM2 |
| Relational DB | PostgreSQL 15 | VM2 |
| Object Storage | MinIO | VM2 |
| Metrics | Prometheus + Node Exporter + cAdvisor | VM1 |
| Dashboard | Grafana | VM1 |
| Logging | Loki + Promtail | VM1 |
| Alerting | Alertmanager | VM1 |
| Language | Python 3.11 | VM1 |
| CI/CD | GitHub Actions | Cloud |
| IaC | Ansible | macOS |
| Test | pytest + flake8 | macOS / CI |
| Backup | bash + cron | VM3 |

---

## PHẦN 7 – DELIVERABLES CHECKLIST

- [ ] Source code ETL (extract, transform, load, quality_check)
- [ ] Airflow DAGs (ingest API + CSV, data quality)
- [ ] Docker Compose files (VM1 + VM2 + VM3)
- [ ] Prometheus + Grafana config + dashboards
- [ ] Loki + Promtail config
- [ ] Alertmanager config
- [ ] Ansible playbooks
- [ ] GitHub Actions workflows (CI + CD)
- [ ] Backup script + cron
- [ ] Sample dataset (sample_data/sample.csv)
- [ ] README.md
- [ ] .env.example
