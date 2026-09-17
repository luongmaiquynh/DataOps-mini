# Runbook: AirflowTaskStuckQueued

**Mức độ:** critical · **Điều kiện kích hoạt:** Có task Airflow nằm ở trạng thái `queued` quá 15 phút

## Ảnh hưởng

Pipeline đã ngừng chạy dù không có gì báo hỏng. Đây chính là sự cố ngày 16–17/09/2026:
worker im lặng 25 giờ, DAG treo, dữ liệu ngừng cập nhật, mà `docker ps` vẫn báo `Up`.

## Kiểm tra

Câu hỏi cần trả lời: **có ai đang thật sự chờ lấy việc không?**

```bash
# 1. Hàng đợi còn bao nhiêu việc, có vơi không (đo hai lần cách 30 giây)
ssh dataops@192.168.64.3 'docker exec redis_cache sh -c "redis-cli -a \$REDIS_PASSWORD --no-auth-warning LLEN default"'

# 2. QUAN TRỌNG NHẤT: có client nào đang chặn ở brpop để chờ việc không
ssh dataops@192.168.64.3 'docker exec redis_cache sh -c "redis-cli -a \$REDIS_PASSWORD --no-auth-warning CLIENT LIST" | grep -c "cmd=brpop"'

# 3. Worker có nói dối không — ping và active có thể OK trong khi đã hỏng
ssh dataops@192.168.64.2 'docker exec airflow_worker celery -A airflow.providers.celery.executors.celery_executor.app inspect active'
```

## Xử lý

1. **`brpop` đếm được 0 trong khi hàng đợi > 0**: consumer đã chết dù tiến trình còn
   sống. Khắc phục: `ssh dataops@192.168.64.2 'docker restart airflow_worker'`. Worker
   đăng ký lại sau khoảng 2 giây và hàng đợi bắt đầu vơi ngay.
2. **`brpop` có client nhưng hàng đợi không vơi**: xem task đầu hàng đợi có hỏng không,
   và xem log `docker logs airflow_worker --tail 50`.
3. **Redis không kết nối được**: xem runbook `InstanceDown` cho VM2; kiểm tra
   `docker ps | grep redis` trên 192.168.64.3.
4. **Task chờ vì hết slot**: kiểm tra `airflow pools list` và `parallelism`; trường hợp
   này hàng đợi ngắn nhưng task vẫn `queued`.

## Phòng ngừa

Phép đo này cố ý hỏi hàng đợi thay vì hỏi tiến trình. Một tiến trình có thể trả lời
"tôi khỏe" trong khi đã ngừng làm việc; một hàng đợi không vơi thì không nói dối được.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
