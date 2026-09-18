# Runbook: CeleryNoConsumer

**Mức độ:** critical · **Điều kiện kích hoạt:** Redis không có kết nối nào chờ ở `BRPOP` suốt 10 phút

## Ảnh hưởng

Không còn ai lấy việc khỏi hàng đợi. Mọi task Airflow mới sẽ nằm `queued` rồi bị
scheduler đánh dấu hỏng sau 10 phút. Đây đúng là trạng thái của sự cố 16–17/09/2026
([postmortem 5](../postmortems/05-celery-worker-ngung-nhan-viec.md)): worker vẫn
trả lời `ping`, `docker ps` vẫn báo `Up`, nhưng pipeline đã chết 25 giờ.

## Kiểm tra

```bash
# 1. Xác nhận trực tiếp ở Redis — đây là nguồn sự thật, không phải worker
ssh dataops@192.168.64.3 'docker exec redis_cache sh -c "redis-cli -a \$REDIS_PASSWORD --no-auth-warning CLIENT LIST" | grep -c "cmd=brpop"'

# 2. Worker có còn chạy không (câu trả lời "có" KHÔNG loại trừ được sự cố này)
ssh dataops@192.168.64.2 'docker ps --filter name=airflow_worker'

# 3. Worker có đang bận hết mọi slot không (trường hợp duy nhất consumer=0 là bình thường)
ssh dataops@192.168.64.2 'docker exec airflow_worker celery -A airflow.providers.celery.executors.celery_executor.app inspect active | grep -c "'"'"'id'"'"'"'
```

## Xử lý

1. **Worker không chạy**: `ssh dataops@192.168.64.2 'sudo systemctl restart dataops-airflow'`.
2. **Worker chạy, không bận, mà không có `brpop`**: consumer đã chết im lặng.
   `ssh dataops@192.168.64.2 'docker restart airflow_worker'`, rồi đếm lại `brpop` —
   phải về 1 trong vài giây.
3. **Worker bận hết 16 slot**: khi mọi slot đều bận, Celery ngừng lấy thêm việc nên
   `brpop` về 0 là đúng thiết kế. Với các DAG vài giây của lab này, trường hợp đó
   không thể kéo dài 10 phút; nếu có, xem task nào đang chạy lâu bất thường.

## Phòng ngừa

Phép đo hỏi Redis chứ không hỏi worker, vì chính worker là thứ có thể trả lời sai.
Khác với `AirflowTaskStuckQueued`, alert này bật được cả khi hệ thống đang rảnh —
không cần đợi có task mới vào hàng đợi mới phát hiện ra worker đã chết.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
