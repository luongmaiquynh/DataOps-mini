# Runbook: LowMemory

**Mức độ:** critical · **Điều kiện kích hoạt:** RAM khả dụng còn dưới 10%

## Ảnh hưởng

Kernel sẽ bắt đầu giết tiến trình (OOM killer). Container bị giết đột ngột,
thường là container ngốn RAM nhất — trên VM1 thường là Airflow hoặc Grafana.

## Kiểm tra

```bash
ssh dataops@<ip> 'free -h; docker stats --no-stream'
ssh dataops@<ip> 'dmesg | grep -i "out of memory" | tail -5'
```

## Xử lý

1. **Đã có tiến trình bị OOM kill**: khởi động lại stack tương ứng bằng
   `sudo systemctl restart dataops-<stack>`.
2. **Chưa bị giết**: dừng bớt dịch vụ không thiết yếu (Flower, cAdvisor).
3. **Lặp lại thường xuyên**: tăng RAM cho VM trong UTM, nhưng nhớ tổng RAM cấp
   cho các VM không được vượt RAM thật của máy Mac.

## Phòng ngừa

Đã từng xảy ra: cấp 3 × 8 GB cho 3 VM trên máy Mac 16 GB khiến VM chết dần.
Kiểm tra bằng `free -h` trong VM và Activity Monitor trên máy Mac.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
