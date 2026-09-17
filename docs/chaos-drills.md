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

## Những gì diễn tập đã phát hiện

Không phải kịch bản nào cũng chạy trơn. Ba lần thử đã lộ ra lỗi thật:

| Diễn tập | Lỗi phát hiện |
|---|---|
| Kiểm chứng restore lần đầu | Backup chạy suốt 4 tháng **không restore được** vào cụm mới vì thiếu định nghĩa role |
| Xoá volume Grafana | Mount trỏ sai thư mục nên provisioning chưa bao giờ hoạt động |
| Cảnh báo chứng chỉ TLS | Ngưỡng 7 ngày trong khi chứng chỉ chỉ có hạn 12 giờ — alert firing vĩnh viễn |
| Sao lưu MinIO lần đầu | Container chạy bằng root nên toàn bộ file mirror thuộc root, user thường không xoá hay ghi đè được nữa |

Đó chính là lý do phải diễn tập: cấu hình sai thường im lặng, và hệ thống vẫn
báo xanh cho tới lúc thật sự cần tới nó.

## Lịch diễn tập đề xuất

| Hạng mục | Tần suất |
|---|---|
| Kiểm chứng restore (tự động) | Hàng tuần |
| Kịch bản 7 (dead man's switch) | Mỗi quý |
| Kịch bản 9, 10 (dựng lại và khôi phục) | Mỗi quý |
| Kịch bản 13 (khôi phục MinIO) | Mỗi quý |
| Toàn bộ danh sách | Sau mỗi thay đổi lớn về hạ tầng |
