# Runbook: HighCpuUsage

**Mức độ:** warning · **Điều kiện kích hoạt:** CPU vượt 80% liên tục 5 phút

## Ảnh hưởng

Task Airflow chạy chậm, truy vấn database lâu hơn. Chưa mất dịch vụ.

## Kiểm tra

```bash
ssh dataops@<ip> 'top -bn1 | head -15'
ssh dataops@<ip> 'docker stats --no-stream'
```

## Xử lý

1. **Do DAG đang chạy**: bình thường nếu chỉ kéo dài vài phút. Xem
   https://airflow.dataops.test để biết task nào đang chạy.
2. **Một container ngốn CPU liên tục**: xem log của nó, cân nhắc đặt giới hạn
   `cpus:` trong compose.
3. **CPU cao kéo dài không rõ lý do**: `docker restart <container>` rồi theo dõi
   xem có tái diễn không.

## Phòng ngừa

VM1 chạy 13 container nên nhạy cảm nhất. Nếu cảnh báo lặp lại hằng ngày, cân nhắc
tăng vCPU cho VM1 hoặc chuyển bớt stack monitoring sang máy khác.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
