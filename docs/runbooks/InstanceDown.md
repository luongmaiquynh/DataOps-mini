# Runbook: InstanceDown

**Mức độ:** critical · **Điều kiện kích hoạt:** Một target Prometheus không phản hồi quá 1 phút

## Ảnh hưởng

Mất khả năng giám sát máy hoặc dịch vụ đó. Nếu là node-exporter của VM2 hoặc VM3,
hệ thống vẫn chạy nhưng bạn không còn nhìn thấy CPU, RAM, disk của nó.

## Kiểm tra

```bash
# Target nào đang down
curl -sk https://prometheus.dataops.test/api/v1/targets | grep -B5 '"health":"down"'

# Máy đó còn sống không
ping -c 2 192.168.64.4
ssh dataops@192.168.64.4 uptime

# Container còn chạy không
ssh dataops@192.168.64.4 'docker ps'
```

## Xử lý

1. **Máy tắt hoặc treo** — bật lại trong UTM. Dịch vụ tự lên nhờ systemd unit.
2. **Máy sống nhưng container chết**: `sudo systemctl start dataops-<stack>`
3. **Container chạy nhưng vẫn down**: kiểm tra tường lửa —
   `sudo ufw status` trên máy đích, cổng scrape phải nằm trong danh sách allow.
4. **Không rõ nguyên nhân**: `docker logs <container> --tail 50`

## Phòng ngừa

Đã có systemd unit để dịch vụ tự lên sau khi máy khởi động lại. Nếu VM hay chết
đột ngột, kiểm tra RAM cấp cho VM so với RAM thật của máy chủ.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
