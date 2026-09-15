# Runbook: EndpointDown

**Mức độ:** critical · **Điều kiện kích hoạt:** blackbox-exporter gọi thử một endpoint và không nhận được phản hồi hợp lệ trong 2 phút

## Ảnh hưởng

Dịch vụ đó không dùng được từ bên ngoài, dù container có thể vẫn hiện "Up".
Đây là loại hỏng mà các alert khác bỏ sót: tiến trình còn sống nhưng không phục vụ được.

## Kiểm tra

```bash
# Endpoint nào hỏng
curl -sk "https://prometheus.dataops.test/api/v1/query?query=probe_success==0"

# Gọi thử bằng tay từ máy Mac
curl -vk https://grafana.dataops.test/api/health

# Chuỗi phụ thuộc: tường lửa -> Caddy -> dịch vụ
ssh dataops@192.168.64.2 'docker ps --format "{{.Names}} {{.Status}}"'
ssh dataops@192.168.64.2 'docker logs caddy --tail 30'
```

## Xử lý

1. **Caddy chết**: `sudo systemctl restart dataops-monitoring` trên VM1.
2. **Dịch vụ phía sau chết**: xem `docker logs <container>`, khởi động lại stack tương ứng.
3. **Chỉ MinIO hỏng**: kiểm tra VM2 — `sudo systemctl status dataops-database`.
4. **Tất cả endpoint cùng hỏng**: nhiều khả năng do tường lửa hoặc mạng, không phải ứng dụng.
   Kiểm tra `sudo ufw status` và thử `nc -z 192.168.64.2 443` từ máy Mac.
5. **Chỉ blackbox báo hỏng còn gọi tay vẫn được**: xem log của chính blackbox —
   `docker logs blackbox_exporter --tail 20`.

## Lưu ý

Blackbox gọi qua IP của VM1 nhờ `extra_hosts` trong compose, nên phép thử đi đúng
đường mà người dùng đi: qua tường lửa, qua Caddy, rồi mới tới dịch vụ.
