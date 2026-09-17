# Runbook: MinioRestoreTestFailed

**Mức độ:** critical · **Điều kiện kích hoạt:** Lần kiểm chứng khôi phục MinIO hàng tuần không đạt

## Ảnh hưởng

Data lake có file backup nhưng **chưa chắc dùng được**. Đây là tình huống nguy hiểm
hơn không có backup: nó tạo cảm giác an toàn giả, đúng kiểu sự cố đã xảy ra với
backup PostgreSQL (chạy suốt 4 tháng, log báo xanh, restore thì hỏng).

## Kiểm tra

```bash
ssh dataops@192.168.64.4 'tail -40 /var/log/dataops-restore-test.log'
ssh dataops@192.168.64.4 'ls -lt /opt/backup/minio/minio_*.tar.gz | head -3'
ssh dataops@192.168.64.4 'tar tzf $(ls -t /opt/backup/minio/minio_*.tar.gz | head -1) | head'
curl -sk "https://prometheus.dataops.test/api/v1/query?query=dataops_restore_test_minio_objects"
```

## Xử lý

1. **Chạy lại tay để xem lỗi ở bước nào**:
   `ssh dataops@192.168.64.4 'bash /home/dataops/restore-test.sh'`
2. **Không có file nào trong `/opt/backup/minio`**: sao lưu chưa từng chạy — xem
   runbook `MinioBackupStale`.
3. **Giải nén hỏng**: file `.tar.gz` lỗi. Kiểm tra đĩa VM3 (`DiskSpaceLow`) rồi chạy
   `bash /home/dataops/backup-minio.sh` tạo bản mới và thử lại.
4. **MinIO tạm không lên trong 60 giây**: thường do VM3 thiếu RAM hoặc không kéo
   được image từ quay.io. Kiểm tra `free -m` và mạng ra ngoài.
5. **Số object lệch**: so bản sao với nguồn —
   `docker exec minio_storage sh -c 'ls -R /data/dataops-lake'` trên VM2. Lệch thật
   nghĩa là `mc mirror` bị ngắt giữa chừng; chạy lại sao lưu rồi kiểm chứng lại.

## Phòng ngừa

Kiểm chứng dùng MinIO trắng dựng riêng trên cổng 19001 và xoá sạch sau khi xong, nên
không bao giờ đụng vào dữ liệu thật. Mật khẩu của instance tạm sinh ngẫu nhiên mỗi
lần chạy.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
