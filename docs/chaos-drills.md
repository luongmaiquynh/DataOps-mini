# Diễn tập sự cố

Danh sách các kịch bản đã **thực sự chạy** trên hệ thống, kèm kết quả đo được.
Mỗi kịch bản có thể lặp lại theo đúng lệnh ghi bên dưới.

Nguyên tắc: một cảnh báo chưa từng bật lên thì chưa biết nó có hoạt động không;
một quy trình khôi phục chưa từng chạy thì chưa phải quy trình.

## Bảng tổng hợp

| # | Kịch bản | Kết quả | Thời gian phát hiện | Ngày |
|---|---|---|---|---|
| 1 | Tắt PostgreSQL | `PostgreSQLDown` FIRING | ~1 phút | 05/2026 |
| 2 | Làm đầy đĩa | `DiskSpaceLow` FIRING | ~5 phút | 05/2026 |
| 3 | Tắt node-exporter VM3 | `InstanceDown` FIRING | ~1 phút | 05/2026 |
| 4 | Container crash-loop | `ContainerRestartingTooMuch` FIRING | ~3 phút | 05/2026 |
| 5 | Giả lập backup quá hạn 48 giờ | `BackupStale` FIRING kèm link runbook | 10 phút | 15/09/2026 |
| 6 | Làm hỏng file backup | `restore-test.sh` thoát mã 1 | ngay lập tức | 15/09/2026 |
| 7 | **Tắt Alertmanager 17 phút** | Email `DOWN` từ healthchecks.io | **14,5 phút** | 15/09/2026 |
| 8 | Xoá container rồi khởi động lại VM3 | systemd tự dựng lại, không thao tác tay | ~40 giây | 15/09/2026 |
| 9 | Xoá sạch container, image và code trên VM3 | Dựng lại bằng một lệnh | **28 giây** | 15/09/2026 |
| 10 | Khôi phục database từ backup sang DB mới | 49 bảng, dữ liệu đầy đủ | **2 giây** | 15/09/2026 |
| 11 | Xoá volume Grafana | Datasource và dashboard tự trở về từ file | ~30 giây | 15/09/2026 |
| 12 | Tắt Grafana | `EndpointDown` bật đúng endpoint | 2 phút | 16/09/2026 |
| 13 | **Khôi phục data lake vào một MinIO trắng** | 17/17 object, md5 khớp từng byte | **dưới 1 giây** | 17/09/2026 |
| 14 | Bơm `InstanceDown` + `PostgreSQLDown` cùng nhãn `vm` vào Alertmanager | `PostgreSQLDown` chuyển sang `suppressed`; cùng alert đó ở `vm` khác vẫn `active` | ngay lập tức | 17/09/2026 |
| 15 | **Worker ngừng lấy việc nhưng vẫn trả lời ping** (`celery control cancel_consumer`) | `CeleryNoConsumer` firing, gửi qua ntfy — lần thử đầu KHÔNG bật, lộ lỗi trong metric | **11,5 phút** | 18/09/2026 |
| 16 | **Khởi động lại Redis một lần** (`docker restart redis_cache`) | Worker kết nối lại nhưng không bao giờ lấy việc nữa — tái hiện nguyên nhân gốc của postmortem 5; sửa bằng Celery 5.4.0 | `CeleryNoConsumer` (như #15) | 19/09/2026 |

## Cách lặp lại từng kịch bản

### 1. PostgreSQL chết
```bash
ssh dataops@192.168.64.3 'docker stop postgres_db'
# chờ ~1 phút, xem https://prometheus.dataops.test/alerts
ssh dataops@192.168.64.3 'docker start postgres_db'
```

### 5. Backup quá hạn
```bash
ssh dataops@192.168.64.4
cp /var/lib/node_exporter/textfile/dataops_backup.prom /tmp/b.bak
OLD=$(( $(date +%s) - 48*3600 ))
sed -i "s/^dataops_backup_last_success_timestamp_seconds .*/dataops_backup_last_success_timestamp_seconds $OLD/" \
  /var/lib/node_exporter/textfile/dataops_backup.prom
# chờ 10 phút (rule có for: 10m), rồi khôi phục:
cp /tmp/b.bak /var/lib/node_exporter/textfile/dataops_backup.prom
```

### 6. Backup hỏng
```bash
ssh dataops@192.168.64.4
head -c 50000 /dev/urandom | gzip > /opt/backup/postgres/backup_dataops_db_99999999_999999.sql.gz
bash /home/dataops/restore-test.sh; echo "exit=$?"     # phải khác 0
rm /opt/backup/postgres/backup_dataops_db_99999999_999999.sql.gz
```

### 7. Dead man's switch
```bash
ssh dataops@192.168.64.2 'docker stop alertmanager'
# chờ ~15 phút, kiểm tra email
ssh dataops@192.168.64.2 'docker start alertmanager'
```
Đây là kịch bản quan trọng nhất: nó kiểm chứng thứ duy nhất có thể báo tin khi
chính hệ thống giám sát đã chết.

### 8. Máy khởi động lại sau khi container bị xoá
```bash
ssh dataops@192.168.64.4
cd ~/dataops/docker/dataops-vm3 && docker compose down
sudo reboot
# chờ ~1 phút rồi kiểm tra: docker ps phải có node_exporter
```

### 9. Dựng lại máy từ trạng thái trống
```bash
ssh dataops@192.168.64.4 'cd ~/dataops/docker/dataops-vm3 && docker compose down; \
  docker system prune -af; rm -rf ~/dataops'
cd infra/ansible && time ansible-playbook site.yml --limit vm3 --ask-become-pass
```

### 10. Khôi phục database
Xem [dr-plan.md](dr-plan.md), Kịch bản 1. Diễn tập dùng database `dr_drill` nên
không đụng dữ liệu thật.

### 11. Mất volume Grafana
```bash
ssh dataops@192.168.64.2
cd ~/dataops/docker/dataops-vm1
docker compose -f docker-compose-monitoring.yml rm -sf grafana
docker volume rm dataops-vm1_grafana_data
docker compose -f docker-compose-monitoring.yml up -d grafana
# dashboard và datasource phải tự trở về
```

### 12. Endpoint không phản hồi
```bash
ssh dataops@192.168.64.2 'docker stop grafana'
# chờ 2 phút, EndpointDown phải bật lên đúng endpoint
ssh dataops@192.168.64.2 'docker start grafana'
```

### 13. Khôi phục MinIO từ bản sao

Chạy hoàn toàn trong `/tmp` với một MinIO dựng riêng, nên không đụng dữ liệu thật.

```bash
ssh dataops@192.168.64.4
DRILL=/tmp/drill; mkdir -p $DRILL/{data,restore}
MC=quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z

# 1. Bản sao mới nhất
bash /home/dataops/backup-minio.sh
ARCHIVE=$(ls -t /opt/backup/minio/minio_*.tar.gz | head -1)

# 2. Một MinIO hoàn toàn trống
docker run -d --name minio_drill -e MINIO_ROOT_USER=drilluser \
  -e MINIO_ROOT_PASSWORD=drillpass123 -v $DRILL/data:/data -p 19000:9000 \
  quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z server /data

# 3. Đổ ngược vào
tar xzf "$ARCHIVE" -C $DRILL/restore
docker run --rm --network host --user "$(id -u):$(id -g)" -e MC_CONFIG_DIR=/tmp/.mc \
  -v $DRILL/restore:/restore --entrypoint sh $MC -c \
  "mc alias set drill http://127.0.0.1:19000 drilluser drillpass123 && \
   mc mb --ignore-existing drill/dataops-lake && \
   mc mirror --overwrite /restore/dataops-lake drill/dataops-lake"

# 4. Đối chiếu: số object phải bằng nhau, md5 phải khớp
docker rm -f minio_drill
```

Kết quả 17/09/2026: 17 object trong bản sao, 17 object sau khi khôi phục, md5 của
file mẫu khớp từng byte, thời gian mirror dưới 1 giây.

### 14. Luật inhibit có thật sự nín alert không

Tắt database thật chỉ chứng minh được một nửa và làm gián đoạn Airflow. Bơm alert
thẳng vào Alertmanager kiểm đúng thứ cần kiểm: logic nín.

```bash
ssh dataops@192.168.64.2
AM="--alertmanager.url=http://localhost:9093"

# 1. Alert phụ thuộc, chưa có gì nín nó
docker exec alertmanager amtool alert add \
  alertname=PostgreSQLDown severity=critical vm=vm2 instance=postgres-exporter:9187 $AM

# 2. Báo luôn là cả máy chết
docker exec alertmanager amtool alert add \
  alertname=InstanceDown severity=critical vm=vm2 instance=192.168.64.3:9100 $AM

# 3. PostgreSQLDown phải chuyển sang suppressed, kèm inhibitedBy
docker exec alertmanager wget -qO- 'http://localhost:9093/api/v2/alerts' | \
  python3 -m json.tool | grep -A3 '"state"'

# 4. Phép thử ngược: cùng alert nhưng khác máy thì KHÔNG được nín
docker exec alertmanager amtool alert add \
  alertname=PostgreSQLDown severity=critical vm=vm3 instance=fake-exporter:9187 $AM
```

Kết quả 17/09/2026: `PostgreSQLDown` vm=vm2 `suppressed` với `inhibitedBy` trỏ đúng
`InstanceDown`; `PostgreSQLDown` vm=vm3 vẫn `active`. Alert bơm tay tự hết sau 5 phút.

### 15. Worker ngừng lấy việc nhưng vẫn trả lời ping

Tái hiện đúng sự cố 16/09 ([postmortem 5](postmortems/05-celery-worker-ngung-nhan-viec.md)):
tiến trình worker vẫn sống và trả lời `inspect ping`, chỉ ngừng lấy việc khỏi hàng đợi.

```bash
CEL='docker exec airflow_worker celery -A airflow.providers.celery.executors.celery_executor.app'
ssh dataops@192.168.64.2 "$CEL control cancel_consumer default"   # tái hiện
ssh dataops@192.168.64.2 "$CEL inspect ping"                      # vẫn "1 node online"
# chờ khoảng 12 phút, CeleryNoConsumer phải chuyển sang firing
ssh dataops@192.168.64.2 "$CEL control add_consumer default"      # khôi phục
```

Kết quả 18/09/2026:

| Lần | Kết quả |
|---|---|
| 1 | **Không bật trong 20 phút.** Metric vẫn đếm được 1 consumer, vì kết nối cũ vẫn mang `cmd=brpop` — cột `cmd` chỉ là lệnh cuối cùng, không phải việc đang làm. Kết nối đó có `idle=1099` giây, trong khi worker khỏe đo 10 lần luôn 0–1 giây |
| 2 | Sau khi script chỉ đếm kết nối `brpop` có `idle` dưới 30 giây: consumer về 0 sau 2 phút, alert `pending`, rồi **firing lúc +11,5 phút** và Alertmanager gửi qua `ntfy`. Khôi phục xong alert tự tắt |

So với sự cố thật: 25,5 giờ không ai biết, nay hệ thống tự báo sau 11,5 phút.

### 16. Khởi động lại Redis: worker có lấy việc lại không

Tìm nguyên nhân gốc của sự cố worker lặp lại ngày 18/09 ([postmortem 5](postmortems/05-celery-worker-ngung-nhan-viec.md)).
Log trong Loki cho thấy worker mất kết nối Redis lúc VM2 tắt, kết nối lại được, rồi
không lấy thêm việc nào suốt 5 giờ.

```bash
# Trên hệ thống thật (làm lúc không có DAG chạy, worker sẽ phải khởi động lại sau đó)
ssh dataops@192.168.64.3 'docker restart redis_cache'
# 60 giây sau: phải còn đúng 1 kết nối brpop có idle 0-1 giây
ssh dataops@192.168.64.3 'docker exec redis_cache sh -c "redis-cli -a \$REDIS_PASSWORD --no-auth-warning CLIENT LIST" | grep cmd=brpop'
```

Kết quả 19/09/2026:

| Bước | Kết quả |
|---|---|
| Khởi động lại Redis thật, lần 1 | Worker ghi `Connection to broker lost`, kết nối lại (`Connected to redis`, `mingle: all alone`) rồi **ngừng lấy việc**. Bốn lần khởi động lại / đóng băng Redis sau đó không sinh thêm một dòng log nào |
| Gửi `SIGUSR1` để worker in stack | Vòng lặp chính không treo — đang chờ ở `epoll.poll` — nhưng không còn gửi `BRPOP`: sau khi kết nối lại, nó quên đăng ký đọc hàng đợi |
| App Celery tối giản + Redis tạm, cùng image | Tái hiện 5/5 lần: lỗi nằm ở thư viện, không ở cấu hình Airflow hay mạng lab |
| Thử các bản vá | kombu 5.3.7: hỏng. Celery 5.3.6 + kombu 5.3.7: sống qua 1 lần rồi hỏng. **Celery 5.4.0 + kombu 5.4.2: 5/5 lần sống**, với cả redis-py 4.6.0 và 5.0.8 |
| Chạy task thật sau mỗi lần khởi động lại Redis | Bản cũ **0/5**, bản mới **5/5** |
| **Sau khi triển khai Celery 5.4.0 lên VM1** | Khởi động lại Redis thật 3 lần, mỗi lần chờ 60 giây: luôn còn 1 consumer sống, hàng đợi 0. Chạy `data_quality_check` ngay sau đó: `success` trong 12 giây |

Khởi động lại Redis một lần lúc 15:47 ngày 18/09 không làm hỏng worker, nên lỗi không
xảy ra 100% trên hệ thống thật — nhưng đủ thường để một lần bảo trì VM2 là dính.

## Những gì diễn tập đã phát hiện

Không phải kịch bản nào cũng chạy trơn. Ba lần thử đã lộ ra lỗi thật:

| Diễn tập | Lỗi phát hiện |
|---|---|
| Kiểm chứng restore lần đầu | Backup chạy suốt 4 tháng **không restore được** vào cụm mới vì thiếu định nghĩa role |
| Xoá volume Grafana | Mount trỏ sai thư mục nên provisioning chưa bao giờ hoạt động |
| Cảnh báo chứng chỉ TLS | Ngưỡng 7 ngày trong khi chứng chỉ chỉ có hạn 12 giờ — alert firing vĩnh viễn |
| Sao lưu MinIO lần đầu | Container chạy bằng root nên toàn bộ file mirror thuộc root, user thường không xoá hay ghi đè được nữa |
| Đọc nhãn thật của từng target | Luật inhibit dùng `equal: ['instance']` chưa bao giờ khớp được: `instance` là địa chỉ của target, nên ba exporter trên cùng VM1 mang ba giá trị khác nhau |
| Tái hiện worker chết im lặng | Metric đếm consumer theo cột `cmd` của Redis nên vẫn báo 1 consumer khi worker đã ngừng lấy việc — alert viết ra để bắt đúng sự cố này lại không bắt được nó |
| Khởi động lại Redis | Celery 5.3.4 đi kèm Airflow 2.7.3 kết nối lại sau khi mất broker nhưng không lấy việc nữa — nguyên nhân gốc của sự cố worker hai lần |

Đó chính là lý do phải diễn tập: cấu hình sai thường im lặng, và hệ thống vẫn
báo xanh cho tới lúc thật sự cần tới nó.

## Lịch diễn tập đề xuất

| Hạng mục | Tần suất |
|---|---|
| Kiểm chứng restore PostgreSQL và MinIO (tự động) | Hàng tuần |
| Kịch bản 7 (dead man's switch) | Mỗi quý |
| Kịch bản 9, 10 (dựng lại và khôi phục) | Mỗi quý |
| Kịch bản 13 (khôi phục MinIO) | Mỗi quý |
| Kịch bản 14 (luật inhibit) | Sau mỗi lần sửa luật cảnh báo |
| Kịch bản 15, 16 (worker chết im lặng, khởi động lại Redis) | Sau mỗi lần nâng cấp Airflow, Celery hoặc Redis |
| Toàn bộ danh sách | Sau mỗi thay đổi lớn về hạ tầng |
