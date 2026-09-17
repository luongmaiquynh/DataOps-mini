# Runbook: CeleryMetricMissing

**Mức độ:** warning · **Điều kiện kích hoạt:** Prometheus không thấy `dataops_celery_probe_success` trong 30 phút

## Ảnh hưởng

Hệ thống đang **mù** về tình trạng hàng đợi. Không có metric thì hai alert
`AirflowTaskStuckQueued` và `CeleryQueueBacklog` cũng không bao giờ bật được —
đúng tình huống đã để sự cố 16/09 ẩn suốt 25 giờ.

## Kiểm tra

```bash
ssh dataops@192.168.64.2 'ls -l /var/lib/node_exporter/textfile/'
ssh dataops@192.168.64.2 'cat /var/lib/node_exporter/textfile/dataops_celery.prom'
ssh dataops@192.168.64.2 'tail -20 /var/log/dataops-celery-metrics.log'
ssh dataops@192.168.64.2 'crontab -l | grep celery'
curl -sk "https://prometheus.dataops.test/api/v1/query?query=dataops_celery_probe_success"
```

## Xử lý

1. **Chạy tay để xem lỗi**: `ssh dataops@192.168.64.2 'bash /home/dataops/celery-queue-metrics.sh'`
2. **Container `airflow_scheduler` không chạy**: script hỏi hàng đợi thông qua nó.
   Xem `docker ps | grep scheduler`, cần thì `sudo systemctl restart dataops-airflow`.
3. **Thiếu thư mục textfile**: `ansible-playbook site.yml --limit vm1` sẽ tạo lại
   `/var/lib/node_exporter/textfile` và cài lại cron.
4. **node-exporter không đọc textfile**: kiểm tra container có tham số
   `--collector.textfile.directory=/textfile` và mount tương ứng chưa —
   `docker inspect node_exporter --format '{{.Config.Cmd}}'`.

## Phòng ngừa

Script ghi file tạm rồi `mv`, nên node-exporter không bao giờ đọc phải file viết dở.
Metric `dataops_celery_probe_success` vẫn được ghi cả khi phép đo thất bại — biến mất
hoàn toàn nghĩa là cron không chạy.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
