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

## Điểm chung

Cả bốn đều thuộc một loại: **hệ thống báo xanh trong khi đã hỏng**. Không cái nào
tự báo lỗi. Ba trong bốn chỉ lộ ra khi có người chủ động đi kiểm tra thứ mà mọi
người đều mặc định là đang chạy tốt.
