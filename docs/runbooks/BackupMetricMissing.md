# Runbook: BackupMetricMissing

**Mức độ:** warning · **Điều kiện kích hoạt:** Không thấy metric backup nào

## Ảnh hưởng

Không biết backup có chạy hay không — nguy hiểm vì cảnh báo `BackupStale` cũng
không thể hoạt động khi không có dữ liệu.

## Kiểm tra

```bash
ssh dataops@192.168.64.4 'ls -l /var/lib/node_exporter/textfile/'
ssh dataops@192.168.64.4 'docker inspect node_exporter --format "{{.Args}}" | tr " " "\n" | grep textfile'
curl -sk "https://prometheus.dataops.test/api/v1/query?query=dataops_backup_success"
```

## Xử lý

1. **Thư mục textfile trống**: chạy thử `bash /home/dataops/backup.sh` và xem file
   `.prom` có được tạo không.
2. **node-exporter thiếu cờ textfile**: chạy `ansible-playbook site.yml --limit vm3`.
3. **Thư mục không tồn tại**: playbook sẽ tạo lại với quyền của user `dataops`.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
