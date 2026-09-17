# Runbook: CeleryQueueBacklog

**Mức độ:** warning · **Điều kiện kích hoạt:** Hàng đợi Celery còn trên 20 việc suốt 15 phút

## Ảnh hưởng

Chưa chắc đã hỏng, nhưng công việc đang dồn nhanh hơn tốc độ xử lý. Nếu kéo dài,
DAG sẽ trễ lịch và `AirflowTaskStuckQueued` sẽ bật theo.

## Kiểm tra

```bash
ssh dataops@192.168.64.3 'docker exec redis_cache sh -c "redis-cli -a \$REDIS_PASSWORD --no-auth-warning LLEN default"'
ssh dataops@192.168.64.2 'docker exec airflow_worker celery -A airflow.providers.celery.executors.celery_executor.app inspect active | tail -20'
ssh dataops@192.168.64.2 'free -m; docker stats --no-stream --format "{{.Name}}: {{.MemUsage}}"'
```

## Xử lý

1. **Worker bận thật** (inspect active có nhiều task): chờ, hoặc tăng
   `AIRFLOW__CELERY__WORKER_CONCURRENCY` nếu VM1 còn RAM.
2. **Worker rảnh mà hàng đợi không vơi**: đây là dấu hiệu consumer chết — xử lý theo
   runbook `AirflowTaskStuckQueued`.
3. **Việc dồn do tồn đọng cũ**: sau một sự cố dài, hàng đợi có thể chứa message của
   các task đã bị đánh dấu thất bại. Chúng sẽ được worker bỏ qua nhanh, hàng đợi vơi
   trong vài phút. Nếu không vơi, quay lại bước 2.
4. **VM1 thiếu RAM**: xem runbook `LowMemory`; worker prefork rất tốn bộ nhớ.

## Phòng ngừa

Ngưỡng 20 việc trong 15 phút cố ý đặt cao hơn mức dao động bình thường của lab (ba
DAG nhẹ, hàng đợi thường về 0 trong vài giây).

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
