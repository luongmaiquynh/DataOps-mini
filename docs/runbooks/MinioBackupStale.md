# Runbook: MinioBackupStale

**Mức độ:** critical · **Điều kiện kích hoạt:** Không có lần sao lưu MinIO thành công nào trong 26 giờ

## Ảnh hưởng

Data lake không còn bản sao mới. MinIO nằm trong volume `minio_data` trên VM2 và
`pg_dump` **không** chạm tới nó: mất volume đó là mất toàn bộ file raw mà hai DAG
đã đẩy lên (`raw/employees/*`, `raw/weather/*`). Database vẫn được backup bình
thường, nên đừng nhầm là "đã có backup rồi".

## Kiểm tra

```bash
ssh dataops@192.168.64.4 'ls -lt /opt/backup/minio | head -5'
ssh dataops@192.168.64.4 'tail -30 /var/log/dataops-minio-backup.log'
ssh dataops@192.168.64.4 'crontab -l | grep -i minio'
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.64.3:9000/minio/health/live
```

## Xử lý

1. **Chạy thử ngay để xem lỗi gì**: `ssh dataops@192.168.64.4 'bash /home/dataops/backup-minio.sh'`
2. **MinIO không phản hồi**: xem container trên VM2 —
   `ssh dataops@192.168.64.3 'docker ps | grep minio'`, cần thì
   `sudo systemctl restart dataops-database`.
3. **Sai thông tin đăng nhập**: script đọc `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD`
   từ `/home/dataops/dataops/.env`. Sinh lại bằng
   `ansible-playbook site.yml --limit vm3`.
4. **Không kéo được image `mc`**: image lấy từ quay.io (MinIO đã rút khỏi Docker
   Hub). Kiểm tra mạng ra ngoài của VM3 rồi
   `docker pull quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z`.
5. **Hết đĩa**: xem runbook `DiskSpaceLow`.

## Phòng ngừa

Sao lưu MinIO chạy 2:30 sáng, sau backup database 30 phút để hai việc không giành
nhau băng thông. Bản mirror ở `/opt/backup/minio/current` giữ nguyên giữa các lần
chạy nên chỉ phần thay đổi mới phải tải lại.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
