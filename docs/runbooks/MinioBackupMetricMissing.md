# Runbook: MinioBackupMetricMissing

**Mức độ:** warning · **Điều kiện kích hoạt:** Prometheus không thấy metric `dataops_minio_backup_last_success_timestamp_seconds` trong 30 phút

## Ảnh hưởng

Chưa chắc sao lưu đã hỏng, nhưng hệ thống giám sát đang **mù** về nó. Đây là loại
sự cố nguy hiểm vì im lặng: không có metric thì `MinioBackupStale` cũng không bao
giờ bật được.

## Kiểm tra

```bash
ssh dataops@192.168.64.4 'ls -l /var/lib/node_exporter/textfile/'
ssh dataops@192.168.64.4 'cat /var/lib/node_exporter/textfile/dataops_minio_backup.prom'
ssh dataops@192.168.64.4 'docker ps | grep node-exporter'
curl -sk "https://prometheus.dataops.test/api/v1/query?query=dataops_minio_backup_success"
```

## Xử lý

1. **Chưa từng chạy lần nào**: chạy tay
   `ssh dataops@192.168.64.4 'bash /home/dataops/backup-minio.sh'` rồi xem file
   `.prom` đã xuất hiện chưa.
2. **Thiếu thư mục textfile**: `ansible-playbook site.yml --limit vm3` sẽ tạo lại
   `/var/lib/node_exporter/textfile` với đúng quyền.
3. **node-exporter VM3 chết**: xem runbook `InstanceDown`; không có exporter thì
   mọi metric của cron job đều biến mất.
4. **Cron không chạy**: `ssh dataops@192.168.64.4 'systemctl status cron'`.

## Phòng ngừa

Script ghi file tạm rồi `mv`, nên node-exporter không bao giờ đọc phải file viết
dở. Metric `dataops_minio_backup_success` vẫn được ghi cả khi sao lưu thất bại —
biến mất hoàn toàn nghĩa là script không chạy, chứ không phải chạy hỏng.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
