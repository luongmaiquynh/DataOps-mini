# Runbook: DiskSpaceLow

**Mức độ:** warning · **Điều kiện kích hoạt:** Dung lượng trống dưới 15%

## Ảnh hưởng

PostgreSQL sẽ dừng ghi khi hết đĩa. Log và backup không ghi được. Đây là loại sự
cố làm hỏng dữ liệu nếu để tới mức đầy hoàn toàn.

## Kiểm tra

```bash
ssh dataops@<ip> 'df -h /'
ssh dataops@<ip> 'sudo du -sh /var/lib/docker/* | sort -rh | head -5'
ssh dataops@<ip> 'du -sh /opt/backup/postgres'
```

## Xử lý

1. **Log container phình to**: đã giới hạn 3×10MB mỗi container, nhưng container
   tạo trước khi đặt giới hạn thì chưa áp dụng — dựng lại chúng.
2. **Image cũ không dùng**: `docker image prune -a`
3. **Backup chiếm nhiều**: kiểm tra retention 7 ngày có chạy không —
   `ls -lt /opt/backup/postgres | tail`
4. **Volume Loki/Prometheus lớn**: Loki giữ 7 ngày, Prometheus 15 ngày. Muốn giảm
   thì sửa `retention_period` và `--storage.tsdb.retention.time`.

## Phòng ngừa

Giữ ngưỡng cảnh báo ở 15% để còn thời gian xử lý trước khi đầy.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
