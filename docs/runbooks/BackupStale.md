# Runbook: BackupStale

**Mức độ:** critical · **Điều kiện kích hoạt:** Không có bản backup thành công nào trong 26 giờ

## Ảnh hưởng

Mất khả năng khôi phục dữ liệu mới. Nếu database hỏng ngay bây giờ, bạn chỉ khôi
phục được tới bản backup cuối cùng.

## Kiểm tra

```bash
ssh dataops@192.168.64.4 'ls -lt /opt/backup/postgres | head -5'
ssh dataops@192.168.64.4 'tail -30 /var/log/dataops-backup.log'
ssh dataops@192.168.64.4 'crontab -l'
```

## Xử lý

1. **Chạy thử ngay để xem lỗi gì**: `ssh dataops@192.168.64.4 'bash /home/dataops/backup.sh'`
2. **Không kết nối được PostgreSQL**: xem runbook `PostgreSQLDown`.
3. **Thiếu mật khẩu**: script đọc `/home/dataops/dataops/.env`. Chạy
   `ansible-playbook site.yml --limit vm3` để sinh lại file này.
4. **Cron không chạy**: kiểm tra `systemctl status cron` trên VM3.
5. **Hết đĩa**: xem runbook `DiskSpaceLow`.

## Phòng ngừa

Ngưỡng 26 giờ cho phép lần chạy 2:00 sáng trễ tối đa 2 tiếng mà chưa báo động.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
