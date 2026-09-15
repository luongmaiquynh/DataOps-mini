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
│   └── tests/              # Unit tests (66 tests, 6 files)
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
ansible-playbook site.yml --ask-become-pass

# Hoặc deploy riêng từng VM
ansible-playbook site.yml --limit vm2 --ask-become-pass

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
docker compose --profile init run --rm airflow-init   # chỉ lần đầu, hoặc sau khi nâng cấp Airflow
docker compose up -d

# VM1 - Monitoring
docker compose -f docker-compose-monitoring.yml up -d

# VM3 - Node Exporter + Backup
ssh dataops@192.168.64.4
cd ~/dataops/docker/dataops-vm3
docker compose up -d
```

## Khả năng dựng lại

VM3 đã được kiểm chứng bằng cách xoá sạch container, image và thư mục code, rồi
dựng lại hoàn toàn bằng một lệnh:

```bash
time ansible-playbook site.yml --limit vm3 --ask-become-pass
```

| Chỉ số | Kết quả (15/09/2026) |
|---|---|
| Thời gian dựng lại toàn bộ dịch vụ | **28 giây** |
| Số task | 21, `changed=4`, `failed=0` |
| Chạy lần hai | `changed=0` trên cả 3 VM |

Phép đo bắt đầu từ máy **đã có OS và Docker**; chưa tính thời gian cài Ubuntu và
cài Docker Engine. Sau khi dựng lại, node-exporter chạy đúng version đã ghim,
`.env` được sinh từ template, script backup và cron 2:00 được đặt lại, và
Prometheus nhận lại target `node-exporter-vm3`.

## Khởi động và tắt hệ thống

Mỗi stack là một systemd unit nên **không cần gõ lệnh docker khi bật máy**:

| Máy | Unit |
|---|---|
| VM1 | `dataops-airflow.service`, `dataops-monitoring.service` |
| VM2 | `dataops-database.service` |
| VM3 | `dataops-node-exporter.service` |

```bash
sudo systemctl stop dataops-airflow      # dừng (giữ container)
sudo systemctl start dataops-airflow     # chạy lại
systemctl status dataops-airflow
```

Unit dùng `docker compose stop` chứ không phải `down`: `down` xoá container nên
`restart: always` mất tác dụng, và sau khi máy khởi động lại sẽ không có gì chạy.

**Đã kiểm chứng 15/09/2026:** xoá sạch container trên VM3 bằng `compose down`,
khởi động lại máy, systemd tự dựng lại container và Prometheus nhận lại target —
không có thao tác thủ công nào.

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

# Kết quả: 66 passed, 0 warnings
```

| File | Tests | Phạm vi |
|---|---|---|
| `test_extract.py` | 10 | extract_from_csv, extract_from_api |
| `test_transform.py` | 15 | clean_data, normalize_columns, fill_missing, cast_types |
| `test_quality.py` | 12 | run_quality_check, assert_quality, QualityReport |
| `test_load.py` | 13 | load_to_postgres, load_to_minio, upsert_dataframe |
| `test_dag_ingest_csv.py` | 9 | task_extract/transform/quality/load (CSV DAG) |
| `test_dag_ingest_api.py` | 7 | task_extract/transform/quality/load (API DAG) |

## Bảo mật

| Lớp | Cấu hình |
|---|---|
| SSH | Chỉ nhận khoá (`PasswordAuthentication no`), cấm đăng nhập root, fail2ban chặn 1 giờ sau 5 lần sai |
| Tường lửa | UFW khai báo trong `infra/ansible/host_vars/`, mặc định chặn mọi kết nối vào |
| Secret | Ansible Vault (mật khẩu vault đọc từ `~/.ansible/vault_pass_dataops`, ngoài repo); `.env` sinh từ template, mỗi máy chỉ nhận phần nó cần |
| Redis | Bắt buộc xác thực bằng `requirepass`; kết nối không mật khẩu bị từ chối với `NOAUTH` |
| Network | VM2 tách network riêng `data-net` |
| TLS | Caddy reverse proxy, chứng chỉ do CA nội bộ cấp và tự gia hạn; HTTP tự chuyển sang HTTPS |
| Lịch sử git | Đã dọn bằng `git filter-repo` (15/09/2026); toàn bộ mật khẩu từng xuất hiện đều đã được thay thế trước đó |
| Cổng mở | VM1: 22, 80, 443 · VM2: 22, 5432, 6379, 9000, 9001 · VM3: 22, 9100 |

**Lưu ý đã kiểm chứng:** UFW không chặn được cổng do Docker publish vì Docker
chèn luật iptables riêng. Vì vậy các service chỉ cần truy cập nội bộ
(node-exporter, postgres-exporter, Loki) đã được bỏ `ports:` thay vì dựa vào
tường lửa.

## Monitoring

| Giao diện | Địa chỉ | Mô tả |
|---|---|---|
| Airflow | https://airflow.dataops.test | Quản lý DAGs |
| Grafana | https://grafana.dataops.test | Dashboard metrics và log |
| Prometheus | https://prometheus.dataops.test | Metrics, alert rules |
| Alertmanager | https://alerts.dataops.test | Alert đang firing |
| Flower | https://flower.dataops.test | Monitor Celery worker |
| cAdvisor | https://cadvisor.dataops.test | Metrics container |
| MinIO Console | http://192.168.64.3:9001 | Object storage UI (chưa đặt sau proxy) |

Mọi giao diện trên VM1 đi qua Caddy bằng HTTPS trên cổng 443; các cổng HTTP cũ
(3000, 8080, 9090, 9093, 8081, 5555) đã được gỡ khỏi compose. Chứng chỉ do CA
nội bộ của Caddy cấp nên trình duyệt sẽ cảnh báo ở lần đầu.

Máy muốn truy cập cần trỏ tên miền về VM1:

```bash
sudo sh -c 'cat >> /etc/hosts' <<'EOF'

# Mini DataOps Platform (VM1)
192.168.64.2  grafana.dataops.test airflow.dataops.test prometheus.dataops.test
192.168.64.2  alerts.dataops.test flower.dataops.test cadvisor.dataops.test
EOF
```

## Cảnh báo và runbook

11 alert rule trong [monitoring/prometheus/alerts.yml](monitoring/prometheus/alerts.yml),
mỗi rule có annotation `runbook_url` trỏ tới hướng dẫn xử lý tương ứng trong
[docs/runbooks/](docs/runbooks/) — người trực bấm thẳng từ Alertmanager là tới.

| Nhóm | Alert |
|---|---|
| Hạ tầng | `InstanceDown`, `HighCpuUsage`, `LowMemory`, `DiskSpaceLow` |
| Database | `PostgreSQLDown` |
| Container | `ContainerRestartingTooMuch` |
| Backup | `BackupStale`, `BackupMetricMissing`, `BackupRestoreTestFailed`, `BackupRestoreTestStale` |
| Nhịp tim | `Watchdog` |

### Dead man's switch

`Watchdog` là alert **luôn firing**. Alertmanager gửi nó tới healthchecks.io mỗi 5
phút như một nhịp tim. Khi nhịp ngừng — Prometheus chết, Alertmanager chết, hoặc
VM1 mất mạng — healthchecks.io gửi email báo động sau 10 phút chờ.

Đây là câu trả lời cho câu hỏi *"làm sao biết hệ thống giám sát vẫn còn sống?"*.
Ngày 15/09/2026 Alertmanager từng không gửi được cảnh báo suốt 15 phút vì mạng ra
ngoài chập chờn, và không có cách nào biết điều đó.

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

Mỗi lần backup tạo **hai file**: `backup_<db>_<timestamp>.sql.gz` chứa dữ liệu và
`roles_<timestamp>.sql.gz` chứa định nghĩa user. Thiếu file thứ hai thì restore
vào một cụm PostgreSQL mới sẽ dừng với `role "dataops" does not exist`.

### Kiểm chứng backup

`backup/restore-test.sh` chạy 3:00 sáng Chủ nhật hàng tuần trên VM3: dựng một
PostgreSQL tạm trong container, restore role rồi restore database, đếm số bảng và
số dòng, sau đó xoá container. Thoát khác 0 nếu bản backup không dùng được.

```bash
ssh dataops@192.168.64.4 "bash /home/dataops/restore-test.sh"
tail -f /var/log/dataops-restore-test.log
```

Kết quả được đưa vào Prometheus qua textfile collector của node-exporter:

| Metric | Ý nghĩa |
|---|---|
| `dataops_backup_last_success_timestamp_seconds` | Thời điểm backup thành công gần nhất |
| `dataops_backup_size_bytes` | Dung lượng bản backup |
| `dataops_restore_test_success` | Lần kiểm chứng restore gần nhất đạt hay không |
| `dataops_restore_test_tables` | Số bảng khôi phục được |

Alert đi kèm: `BackupStale` (quá 26 giờ không có backup mới), `BackupMetricMissing`,
`BackupRestoreTestFailed`, `BackupRestoreTestStale` (quá 8 ngày chưa kiểm chứng).

Kết quả lần chạy 15/09/2026: 49 bảng, `employees` 5 dòng, `weather_hanoi` 144
dòng. Đã thử với một file backup cố tình làm hỏng để xác nhận script báo lỗi.

## CI/CD

### CI (GitHub Actions)
Tự động chạy khi push lên nhánh `main`:
- `flake8` lint check
- `pytest` unit tests (66 tests)

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
| GĐ7 | Unit Tests (66/66 passed, 6 files, flake8 clean) | ✅ Hoàn thành |
| GĐ8 | Documentation | ✅ Hoàn thành |
