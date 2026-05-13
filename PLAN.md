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
│  192.168.64.2                                   │
│  Airflow | Grafana | Prometheus | Loki | Alertmgr │
└──────────────────────────────────────────────────┘
         │ mạng nội bộ 192.168.64.x
         ▼
┌──────────────────────────────────────────────────┐
│  VM2 – Database + Data Processing                │
│  192.168.64.3                                   │
│  PostgreSQL | Redis | MinIO | Airflow Worker     │
└──────────────────────────────────────────────────┘
         │ mạng nội bộ 192.168.64.x
         ▼
┌──────────────────────────────────────────────────┐
│  VM3 – Optional Worker / Storage / Backup        │
│  192.168.64.4                                   │
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
        - 192.168.64.2/24
```
```bash
sudo netplan apply
```

> **Lưu ý:** Kiểm tra subnet Host Only của UTM trên macOS:
> ```bash
> # Chạy trên macOS
> ifconfig | grep -A2 bridge
> ```
> Nếu subnet khác `192.168.64.x`, điều chỉnh IP cho phù hợp.

Trên VM2 (thay `.11` thành `.12`):
```bash
sudo netplan apply
ping 192.168.64.2   # test từ VM2
```

**E. Thêm hostname /etc/hosts (cả 3 VM)**
```bash
sudo tee -a /etc/hosts << 'EOF'
192.168.64.2   vm1 dataops-master
192.168.64.3   vm2 dataops-db
192.168.64.4   vm3 dataops-worker
EOF
```

**F. SSH key từ macOS**
```bash
ssh-keygen -t ed25519 -C "dataops"
ssh-copy-id dataops@192.168.64.2
ssh-copy-id dataops@192.168.64.3
ssh-copy-id dataops@192.168.64.4
```

Thêm vào `~/.ssh/config`:
```
Host vm1
    HostName 192.168.64.2
    User dataops
    IdentityFile ~/.ssh/id_ed25519

Host vm2
    HostName 192.168.64.3
    User dataops
    IdentityFile ~/.ssh/id_ed25519

Host vm3
    HostName 192.168.64.4
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
| IP | 192.168.64.2 | 192.168.64.3 | 192.168.64.4 |
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
POSTGRES_HOST=192.168.64.3
POSTGRES_PORT=5432
REDIS_HOST=192.168.64.3
REDIS_PORT=6379
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=***REMOVED***
MINIO_HOST=192.168.64.3
MINIO_PORT=9000
MINIO_BUCKET=dataops-lake
AIRFLOW__CORE__FERNET_KEY=your-fernet-key-here
AIRFLOW__WEBSERVER__SECRET_KEY=your-secret-key-here
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://dataops:***REMOVED***@192.168.64.3:5432/airflow_db
AIRFLOW__CELERY__BROKER_URL=redis://192.168.64.3:6379/0
AIRFLOW__CELERY__RESULT_BACKEND=db+postgresql://dataops:***REMOVED***@192.168.64.3:5432/airflow_db
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=***REMOVED***
VM3_HOST=192.168.64.4
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
scp -r . dataops@192.168.64.3:/opt/dataops
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

Truy cập: http://192.168.64.2:8080

#### Bước 2.3 – VM1: Monitoring Stack
```bash
docker compose -f docker/dataops-vm1/docker-compose-monitoring.yml up -d
# Grafana: http://192.168.64.2:3000
```

#### Bước 2.4 – VM3: Airflow Worker + Backup (docker/dataops-vm3/docker-compose.yml)
```yaml
services:
  airflow-worker:
    image: apache/airflow:2.7.1
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
apache-airflow==2.7.1
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
      - targets: ['node-exporter:9100', '192.168.64.3:9100']
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
192.168.64.2 ansible_user=dataops

[vm2]
192.168.64.3 ansible_user=dataops

[vm3]
192.168.64.4 ansible_user=dataops

[all:vars]
ansible_python_interpreter=/usr/bin/python3
```

---

### GIAI ĐOẠN 7 – Testing (1 ngày)

#### 7.1 – Unit Tests

Có 4 file test, tổng cộng **61 test cases**, tất cả đều pass:

| File test | Số tests | Module được test |
|---|---|---|
| `tests/test_extract.py` | 10 | `etl/extract.py` – CSV + API extraction |
| `tests/test_load.py` | 8 | `etl/load.py` – PostgreSQL + MinIO load |
| `tests/test_quality.py` | 12 | `etl/quality_check.py` – QualityReport, assert |
| `tests/test_transform.py` | 15 | `etl/transform.py` – clean, normalize, fill, cast |
| `tests/test_dag_ingest_api.py` | 7 | `dags/ingest_api_dag.py` – task functions |
| `tests/test_dag_ingest_csv.py` | 9 | `dags/ingest_csv_dag.py` – task functions |

Chạy:
```bash
cd /Users/luongmaiquynh/Documents/dataops/pipeline
source .venv/bin/activate
flake8 etl/ dags/ tests/ --statistics   # 0 lỗi
pytest tests/ -v                         # 61 passed
```

#### 7.2 – Kiểm tra vận hành

| Test | Cách làm | Kết quả mong đợi |
|---|---|---|
| Restart VM | `sudo reboot` | Services tự start lại |
| Restart container | `docker restart postgres_db` | Kết nối lại tự động |
| Simulate failure | `docker stop airflow_scheduler` | Alert gửi ntfy |
| Disk full | `fallocate -l 70G /tmp/fill` | Alert disk > 85% |
| Backup thủ công | `bash /home/dataops/backup.sh` trên VM3 | File .sql.gz trong `/opt/backup/postgres/` |
| Trigger DAG | `docker exec airflow_scheduler airflow dags trigger ingest_weather_api` | State: success |

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
| Metrics | Prometheus + Node Exporter + cAdvisor + postgres-exporter | VM1 |
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

- [x] Source code ETL (extract, transform, load, quality_check)
- [x] Airflow DAGs (ingest API + CSV, data quality)
- [x] Docker Compose files (VM1 + VM2 + VM3)
- [x] Prometheus + Grafana config + dashboards
- [x] Loki + Promtail config (bao gồm `monitoring/promtail/promtail-config.yml`)
- [x] Alertmanager config
- [x] Ansible playbooks
- [x] GitHub Actions workflows (CI + CD)
- [x] Backup script + cron (chạy 2:00 AM hàng ngày trên VM3)
- [x] Sample dataset (sample_data/sample.csv)
- [x] Unit tests – 61 tests, 4 file ETL + 2 file DAG
- [x] .env.example
- [ ] README.md
- [ ] Sơ đồ kiến trúc (draw.io)

---

## PHẦN 8 – HƯỚNG DẪN SỬ DỤNG HỆ THỐNG

### 8.1 Cách hệ thống hoạt động (tổng quan)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     LUỒNG DỮ LIỆU                                   │
│                                                                     │
│  Nguồn dữ liệu          Xử lý               Lưu trữ                │
│  ─────────────          ──────               ────────               │
│  CSV file        ──►                                                │
│                        Airflow DAG    ──►   PostgreSQL              │
│  REST API        ──►   (ETL Pipeline)  ──►   MinIO (Data Lake)      │
│                        trên VM1                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     LUỒNG GIÁM SÁT                                  │
│                                                                     │
│  VM1, VM2, VM3                                                      │
│  (containers, CPU, RAM, disk)                                       │
│        │                                                            │
│        ▼                                                            │
│  Prometheus (thu thập metrics mỗi 15s)                              │
│        │                    │                                       │
│        ▼                    ▼                                       │
│  Grafana (dashboard)   Alertmanager ──► ntfy.sh ──► Điện thoại     │
│                                                                     │
│  Loki (log container) ──► Grafana (xem log)                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 8.2 Tắt hệ thống đúng kỹ thuật

Tắt theo thứ tự **ngược lại** với khởi động: **VM3 → VM1 → VM2**

> **Lý do:** VM2 chứa PostgreSQL (metadata của Airflow) và Redis (broker). Nếu tắt VM2 trước khi Airflow dừng, các task đang chạy sẽ bị mất trạng thái.

**Bước 1 – Dừng VM3 (Node Exporter + Backup)**
```bash
ssh dataops@192.168.64.4
cd ~/dataops/docker/dataops-vm3
docker compose down
sudo shutdown now
```

**Bước 2 – Dừng VM1 (Airflow + Monitoring)**
```bash
ssh dataops@192.168.64.2

# Dừng Airflow trước (đợi task đang chạy hoàn thành)
cd ~/dataops/docker/dataops-vm1
docker compose down

# Dừng Monitoring
docker compose -f docker-compose-monitoring.yml down

sudo shutdown now
```

**Bước 3 – Dừng VM2 (Database + Storage) — tắt sau cùng**
```bash
ssh dataops@192.168.64.3
cd ~/dataops/docker/dataops-vm2
docker compose down
sudo shutdown now
```

> **Lưu ý:** Dữ liệu PostgreSQL và MinIO được lưu trong Docker named volumes (`postgres_data`, `minio_data`) — **không bị mất** khi tắt container hoặc VM đúng cách.

---

### 8.3 Khởi động hệ thống từ đầu

Nếu tất cả VM đang tắt, khởi động theo thứ tự: **VM2 trước → VM1 → VM3**

**Bước 1 – Bật VM2 (Database + Storage)**
```bash
# Bật VM2 trong UTM, sau đó:
ssh dataops@192.168.64.3
cd ~/dataops/docker/dataops-vm2
docker compose up -d

# Kiểm tra:
docker ps
# Phải thấy: postgres_db, redis_cache, minio_storage đều Up
```

**Bước 2 – Bật VM1 (Airflow + Monitoring)**
```bash
ssh dataops@192.168.64.2

# Khởi động Airflow
cd ~/dataops/docker/dataops-vm1
docker compose up -d

# Khởi động Monitoring
docker compose -f docker-compose-monitoring.yml up -d

# Kiểm tra:
docker ps
# Phải thấy: airflow_webserver (healthy), airflow_scheduler,
#            airflow_worker, airflow_flower, prometheus,
#            grafana, loki, alertmanager, cadvisor, node_exporter
```

**Bước 3 – Bật VM3 (Node Exporter + Backup)**
```bash
ssh dataops@192.168.64.4
cd ~/dataops/docker/dataops-vm3
docker compose up -d
```

---

### 8.3 Truy cập các giao diện web

| Giao diện | URL | Tài khoản mặc định | Mô tả |
|---|---|---|---|
| **Airflow UI** | http://192.168.64.2:8080 | admin / admin | Quản lý, trigger, xem log DAGs |
| **Grafana** | http://192.168.64.2:3000 | admin / admin | Dashboard metrics & logs |
| **Prometheus** | http://192.168.64.2:9090 | — | Query metrics, xem alert rules |
| **Alertmanager** | http://192.168.64.2:9093 | — | Xem alert đang firing |
| **Celery Flower** | http://192.168.64.2:5555 | — | Monitor Celery workers |
| **MinIO Console** | http://192.168.64.3:9001 | minioadmin / (từ .env) | Xem file trong data lake |

---

### 8.4 Vận hành Data Pipeline

#### Xem danh sách DAGs
```bash
ssh dataops@192.168.64.2
docker exec airflow_scheduler airflow dags list
```

| DAG | Nguồn | Lịch chạy | Đích |
|---|---|---|---|
| `ingest_csv` | `sample_data/sample.csv` | Hàng ngày lúc 0:00 | PostgreSQL `employees` + MinIO |
| `ingest_weather_api` | Open-Meteo API (Hà Nội) | Mỗi giờ | PostgreSQL `weather_hanoi` + MinIO |
| `data_quality` | PostgreSQL | Hàng ngày lúc 1:00 | Báo cáo chất lượng |

#### Bật/tắt DAG
```bash
# Bật DAG
docker exec airflow_scheduler airflow dags unpause <dag_id>

# Tắt DAG
docker exec airflow_scheduler airflow dags pause <dag_id>
```

#### Trigger DAG thủ công
```bash
docker exec airflow_scheduler airflow dags trigger ingest_weather_api
```

#### Xem lịch sử chạy
```bash
docker exec airflow_scheduler airflow dags list-runs -d ingest_weather_api
```

#### Xem log task cụ thể
```bash
docker exec airflow_scheduler airflow tasks logs ingest_weather_api extract <run_id>
```

---

### 8.5 Truy vấn dữ liệu trong PostgreSQL

```bash
# Kết nối từ macOS
ssh dataops@192.168.64.3 "docker exec postgres_db psql -U dataops -d dataops_db -c '<câu query>'"

# Ví dụ:
# Xem dữ liệu nhân viên
ssh dataops@192.168.64.3 "docker exec postgres_db psql -U dataops -d dataops_db -c 'SELECT * FROM employees;'"

# Xem dữ liệu thời tiết gần nhất
ssh dataops@192.168.64.3 "docker exec postgres_db psql -U dataops -d dataops_db -c 'SELECT * FROM weather_hanoi ORDER BY time DESC LIMIT 5;'"

# Đếm số rows theo ngày
ssh dataops@192.168.64.3 "docker exec postgres_db psql -U dataops -d dataops_db -c 'SELECT DATE(time), count(*) FROM weather_hanoi GROUP BY DATE(time);'"
```

---

### 8.6 Xem file trong MinIO (Data Lake)

1. Mở http://192.168.64.3:9001
2. Đăng nhập với `minioadmin` / password trong `.env`
3. Vào bucket `dataops-lake`
4. Cấu trúc thư mục:
   ```
   dataops-lake/
   ├── raw/employees/
   │   └── YYYY-MM-DD.csv      ← từ ingest_csv DAG
   └── raw/weather/
       └── YYYY-MM-DD.csv      ← từ ingest_weather_api DAG
   ```

---

### 8.7 Hệ thống cảnh báo (Alert)

**Cách nhận alert:**
1. Mở https://ntfy.sh/dataops-mini-alerts trên browser
2. Hoặc cài app **ntfy** trên điện thoại → subscribe topic `dataops-mini-alerts`

**Các alert đang được theo dõi:**

| Alert | Điều kiện | Mức độ |
|---|---|---|
| `InstanceDown` | Service không phản hồi > 1 phút | critical |
| `HighCpuUsage` | CPU > 80% liên tục 5 phút | warning |
| `LowMemory` | RAM còn < 10% | warning |
| `DiskSpaceLow` | Disk còn < 15% | warning |
| `ContainerRestartingTooMuch` | Container restart > 3 lần / 10 phút | critical |

**Test alert thủ công:**
```bash
curl -s -X POST http://192.168.64.2:9093/api/v2/alerts \
  -H 'Content-Type: application/json' \
  -d '[{"labels": {"alertname": "TestAlert", "severity": "critical"}, "annotations": {"summary": "Test"}}]'
```

---

### 8.8 Backup & Restore

**Xem backup hiện có:**
```bash
ssh dataops@192.168.64.4 "ls -lh /opt/backup/postgres/"
```

**Chạy backup thủ công:**
```bash
ssh dataops@192.168.64.4 "bash /home/dataops/backup.sh"
```

**Restore từ backup:**
```bash
# Copy file backup từ VM3 về VM2
scp dataops@192.168.64.4:/opt/backup/postgres/employees_YYYY-MM-DD_HHMMSS.sql.gz .

# Giải nén và restore
gunzip employees_YYYY-MM-DD_HHMMSS.sql.gz
ssh dataops@192.168.64.3 "docker exec -i postgres_db psql -U dataops -d dataops_db" < employees_YYYY-MM-DD_HHMMSS.sql
```

**Backup tự động:** Chạy lúc **2:00 AM hàng ngày** qua cron trên VM3. Giữ tối đa 7 ngày gần nhất, tự xóa file cũ hơn.

---

### 8.9 Chạy Unit Tests

```bash
cd /Users/luongmaiquynh/Documents/dataops/pipeline
source .venv/bin/activate      # hoặc: python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Lint
flake8 etl/ dags/ tests/ --statistics

# Chạy tất cả tests
pytest tests/ -v

# Chạy test theo từng module
pytest tests/test_extract.py -v      # ETL extract
pytest tests/test_transform.py -v    # ETL transform
pytest tests/test_quality.py -v      # ETL quality check
pytest tests/test_load.py -v         # ETL load
pytest tests/test_dag_ingest_api.py -v   # DAG ingest API
pytest tests/test_dag_ingest_csv.py -v   # DAG ingest CSV
```

**Kết quả mong đợi:** `61 passed, 0 warnings`

| File test | Module | Tests |
|---|---|---|
| test_extract.py | etl/extract.py | 10 |
| test_transform.py | etl/transform.py | 15 |
| test_quality.py | etl/quality_check.py | 12 |
| test_load.py | etl/load.py | 8 |
| test_dag_ingest_api.py | dags/ingest_api_dag.py | 7 |
| test_dag_ingest_csv.py | dags/ingest_csv_dag.py | 9 |

---

### 8.10 Thêm nguồn dữ liệu mới

Để thêm pipeline mới từ một API khác:

1. **Tạo DAG mới** trong `pipeline/dags/`:
```python
# pipeline/dags/ingest_myapi_dag.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

API_URL = 'https://api.example.com/data'

def task_extract(**context):
    import requests, pandas as pd
    resp = requests.get(API_URL, timeout=30)
    df = pd.DataFrame(resp.json())
    context['ti'].xcom_push(key='raw_data', value=df.to_json())

# ... thêm task transform, quality, load tương tự ingest_weather_api
```

2. **Trên VM1**, DAG sẽ tự động được load (volume mount):
```bash
# DAG files được mount từ ~/dataops/pipeline/dags/ vào container
# Sau khi git pull, Airflow scheduler tự phát hiện DAG mới trong 30s
ssh dataops@192.168.64.2
cd ~/dataops && git pull origin main
```

3. **Kiểm tra DAG mới:**
```bash
docker exec airflow_scheduler airflow dags list | grep myapi
docker exec airflow_scheduler airflow dags trigger ingest_myapi
```

---

### 8.11 Xử lý sự cố thường gặp

| Triệu chứng | Nguyên nhân có thể | Cách xử lý |
|---|---|---|
| DAG bị `queued` mãi không chạy | DAG đang paused | `airflow dags unpause <dag_id>` |
| DAG bị `queued` sau khi unpause | Worker không kết nối Redis | `docker logs airflow_worker --tail=20` |
| Task `failed` | Lỗi code hoặc kết nối DB | Xem log: `airflow tasks logs <dag> <task> <run_id>` |
| PostgreSQL không kết nối được | VM2 chưa bật hoặc container chưa Up | `ssh dataops@192.168.64.3 "docker ps"` |
| Grafana không có data | Prometheus chưa scrape được target | Vào http://192.168.64.2:9090/targets kiểm tra |
| Loki không nhận log | Promtail chưa kết nối được | `docker logs promtail --tail=20` |
| Backup fail | Thiếu postgresql-client-15 trên VM3 | `sudo apt install postgresql-client-15` |
| `git pull` yêu cầu password | GitHub không nhận password thường | Dùng Personal Access Token thay password |
| `scp` config rồi reload Prometheus không áp dụng | `scp` tạo inode mới làm mất bind mount | Restart container: `docker restart prometheus` |

---

### 8.12 Bugs đã phát hiện và sửa

Các lỗi được tìm ra trong quá trình review và test toàn bộ source code:

| # | File | Mô tả bug | Mức độ | Cách sửa |
|---|---|---|---|---|
| 1 | `docker/dataops-vm1/docker-compose-monitoring.yml` | Promtail không có config file → không collect log được | HIGH | Tạo `monitoring/promtail/promtail-config.yml` + thêm volume mount |
| 2 | `monitoring/prometheus/alerts.yml` | `rate(container_start_time_seconds)` sai — gauge không dùng với `rate()` | MEDIUM | Đổi sang `changes(container_start_time_seconds{name!=""}[15m]) >= 3` |
| 3 | `pipeline/dags/data_quality_dag.py` | Dòng `[check_emp, check_weather]` là no-op, không làm gì cả | LOW | Xóa dòng vô nghĩa |
| 4 | `pipeline/dags/ingest_api_dag.py` | `datetime.utcnow()` deprecated từ Python 3.12 | LOW | Đổi sang `datetime.now(timezone.utc)` |
| 5 | `pipeline/etl/load.py` | `df.to_sql()` không có try-except → lỗi DB không được log | MEDIUM | Bọc trong try-except với `logger.error` |
| 6 | `pipeline/dags/ingest_api_dag.py` + `ingest_csv_dag.py` | `pd.read_json(string)` bị lỗi trong pandas mới, cần `StringIO` wrapper | MEDIUM | Đổi thành `pd.read_json(io.StringIO(json_str))` ở tất cả chỗ |
| 7 | `pipeline/dags/ingest_csv_dag.py` | `df.to_json()` dùng epoch date format cũ | LOW | Thêm `date_format='iso'` |

---

### 8.13 Cấu trúc thư mục thực tế (sau khi hoàn thiện)

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
│   │   ├── docker-compose.yml               # Airflow
│   │   └── docker-compose-monitoring.yml    # Prometheus, Grafana, Loki, Promtail, Alertmanager, cAdvisor, node-exporter, postgres-exporter
│   ├── dataops-vm2/
│   │   └── docker-compose.yml               # PostgreSQL + Redis + MinIO
│   └── dataops-vm3/
│       └── docker-compose.yml               # Node Exporter
├── pipeline/
│   ├── dags/
│   │   ├── ingest_api_dag.py                # DAG hourly – Open-Meteo API → weather_hanoi
│   │   ├── ingest_csv_dag.py                # DAG daily – sample.csv → employees
│   │   └── data_quality_dag.py              # DAG daily – kiểm tra chất lượng dữ liệu
│   ├── etl/
│   │   ├── extract.py
│   │   ├── transform.py
│   │   ├── load.py
│   │   └── quality_check.py
│   ├── tests/
│   │   ├── test_extract.py        # 10 tests
│   │   ├── test_transform.py      # 15 tests
│   │   ├── test_quality.py        # 12 tests
│   │   ├── test_load.py           # 8 tests
│   │   ├── test_dag_ingest_api.py # 7 tests
│   │   └── test_dag_ingest_csv.py # 9 tests
│   └── requirements.txt
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   └── alerts.yml
│   ├── grafana/dashboards/
│   ├── loki/loki-config.yml
│   ├── promtail/promtail-config.yml         # (mới thêm)
│   └── alertmanager/alertmanager.yml
├── backup/backup.sh
├── sample_data/sample.csv
├── .env.example
├── .gitignore
└── PLAN.md
```

