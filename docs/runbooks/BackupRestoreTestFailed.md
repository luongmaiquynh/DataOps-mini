# Runbook: BackupRestoreTestFailed

**Mức độ:** critical · **Điều kiện kích hoạt:** Bản backup gần nhất không restore được

## Ảnh hưởng

Nguy hiểm hơn cả việc không có backup, vì bạn đang tin vào một bản backup vô dụng.

## Kiểm tra

```bash
ssh dataops@192.168.64.4 'tail -30 /var/log/dataops-restore-test.log'
ssh dataops@192.168.64.4 'bash /home/dataops/restore-test.sh'
```

## Xử lý

1. **Thiếu file `roles_*.sql.gz`**: bản dump database không chứa định nghĩa user,
   restore vào cụm mới sẽ lỗi `role "dataops" does not exist`. Chạy lại
   `bash /home/dataops/backup.sh` để tạo cả hai file.
2. **File gzip hỏng**: kiểm tra đĩa VM3 còn chỗ không, rồi chạy lại backup.
3. **Restore lỗi ở một bảng cụ thể**: xem log chi tiết, có thể dữ liệu nguồn đã
   hỏng — so sánh với bản backup cũ hơn.
4. **Không dựng được PostgreSQL tạm**: VM3 thiếu image, cần mạng để tải
   `postgres:15.17`.

## Phòng ngừa

Đây chính là lý do phải kiểm chứng backup định kỳ: bản backup chạy suốt 4 tháng
đầu tiên của dự án hoàn toàn không restore được, mà không ai biết.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
