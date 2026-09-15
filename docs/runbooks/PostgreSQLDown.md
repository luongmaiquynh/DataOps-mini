# Runbook: PostgreSQLDown

**Mức độ:** critical · **Điều kiện kích hoạt:** postgres-exporter không kết nối được database

## Ảnh hưởng

Nghiêm trọng nhất trong các alert. Airflow mất metadata database nên toàn bộ
pipeline dừng; các task đang chạy sẽ fail.

## Kiểm tra

```bash
ssh dataops@192.168.64.3 'docker ps | grep postgres_db'
ssh dataops@192.168.64.3 'docker logs postgres_db --tail 30'
ssh dataops@192.168.64.3 'docker exec postgres_db pg_isready -U dataops'
```

## Xử lý

1. **Container không chạy**: `sudo systemctl start dataops-database` trên VM2.
2. **Container chạy nhưng không kết nối được**: xem log, thường là hết đĩa hoặc
   dữ liệu hỏng. Kiểm tra `df -h` trước.
3. **Sai mật khẩu** (sau khi đổi mật khẩu mà quên chạy playbook): chạy
   `ansible-playbook rotate-db-password.yml` rồi `site.yml` cho vm2, vm1, vm3.
4. **Dữ liệu hỏng, phải khôi phục**: xem `docs/runbooks/restore-database.md`.

## Phòng ngừa

Backup chạy hàng đêm và được kiểm chứng restore hàng tuần.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
