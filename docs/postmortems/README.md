# Postmortem

Bốn sự cố thật đã xảy ra trên hệ thống này, viết lại theo cùng một cấu trúc:
chuyện gì xảy ra, phát hiện bằng cách nào, nguyên nhân gốc, đã sửa ra sao, và
làm gì để không lặp lại.

Không quy trách nhiệm cho ai — mục đích là tìm ra chỗ **hệ thống** cho phép lỗi
xảy ra mà không ai biết.

| # | Sự cố | Mức độ | Thời gian ẩn |
|---|---|---|---|
| 1 | [Backup không restore được](01-backup-khong-restore-duoc.md) | Nghiêm trọng | 4 tháng |
| 2 | [Prometheus đọc file cấu hình cũ](02-prometheus-doc-file-cu.md) | Trung bình | Vài giờ |
| 3 | [CD hỏng âm thầm](03-cd-hong-am-tham.md) | Trung bình | 3 lần push |
| 4 | [VM chết vì cấp phát RAM vượt mức](04-vm-chet-vi-thieu-ram.md) | Nghiêm trọng | Vài giờ |
| 5 | [Celery worker ngừng nhận việc](05-celery-worker-ngung-nhan-viec.md) (lặp lại 18/09, đã tìm ra lỗi thư viện) | Nghiêm trọng | 25,5 giờ; lần 2: 5 giờ |
| 6 | [CD xoá cấu hình Alertmanager](06-cd-xoa-cau-hinh-alertmanager.md) | Trung bình | 1,5 phút (phát hiện ngay) |

## Điểm chung

Cả năm đều thuộc một loại: **hệ thống báo xanh trong khi đã hỏng**. Không cái nào
tự báo lỗi. Bốn trong năm chỉ lộ ra khi có người chủ động đi kiểm tra thứ mà mọi
người đều mặc định là đang chạy tốt.

Sự cố số 5 đẩy bài học đi xa hơn một bước: ở đó không chỉ cảnh báo im lặng, mà cả
ba lệnh kiểm tra quen tay — `docker ps`, `celery inspect ping`, `celery inspect
active_queues` — đều trả lời "bình thường" trong khi công việc đã ngừng chạy 25 giờ.
