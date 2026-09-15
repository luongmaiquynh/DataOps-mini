# Runbook: ContainerRestartingTooMuch

**Mức độ:** warning · **Điều kiện kích hoạt:** Một container khởi động lại từ 3 lần trở lên trong 15 phút

## Ảnh hưởng

Container đang crash-loop: chạy lên rồi chết, lặp lại. Dịch vụ đó gần như không
dùng được dù `docker ps` có thể vẫn hiện "Up".

## Kiểm tra

```bash
ssh dataops@<ip> 'docker ps -a --format "{{.Names}} {{.Status}}"'
ssh dataops@<ip> 'docker logs <container> --tail 50'
ssh dataops@<ip> 'docker inspect <container> --format "{{.State.ExitCode}} {{.State.Error}}"'
```

## Xử lý

1. **Thiếu biến môi trường**: compose dùng cú pháp `${BIEN:?...}` nên sẽ báo rõ
   biến nào thiếu. Kiểm tra `.env` trong thư mục compose.
2. **Sai cấu hình**: file cấu hình mount vào container có thể là bản cũ — Docker
   mount file đơn lẻ theo inode. Dựng lại container bằng
   `docker compose up -d --force-recreate <service>`.
3. **Phụ thuộc chưa sẵn sàng**: ví dụ Airflow khởi động khi PostgreSQL chưa lên.
   Khởi động theo thứ tự VM2 trước, rồi VM1.

## Lưu ý

Alert này loại trừ các container `airflow_*` vì chúng khởi động lại một cách bình
thường khi PostgreSQL hoặc Redis tạm ngừng.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
