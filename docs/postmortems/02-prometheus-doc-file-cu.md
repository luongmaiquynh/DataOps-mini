# Postmortem 2: Prometheus đọc file cấu hình cũ suốt nhiều giờ

**Ngày:** 15/09/2026 · **Mức độ:** trung bình

## Chuyện gì đã xảy ra

Thêm 4 alert rule mới cho backup vào `alerts.yml`, đồng bộ xuống VM1, nạp lại
cấu hình Prometheus. Lệnh nạp báo thành công.

Nhưng Prometheus vẫn chỉ có 6 rule cũ. File trên máy chủ có 10 rule, file trong
container chỉ có 6. Không một thông báo lỗi nào.

## Phát hiện bằng cách nào

Tình cờ. Chạy `promtool check rules` để kiểm tra cú pháp và thấy nó báo
"6 rules found" trong khi đáng lẽ phải là 10.

Nếu không gõ lệnh đó, 4 cảnh báo về backup sẽ **không bao giờ bật lên** — kể cả
khi backup thật sự hỏng.

## Nguyên nhân gốc

Docker mount **file đơn lẻ** theo inode, không theo đường dẫn. rsync mặc định ghi
file mới rồi đổi tên, tạo ra inode khác. Container vẫn giữ inode cũ, nên nó tiếp
tục đọc nội dung cũ mãi mãi.

Điều nguy hiểm là mọi thứ đều "thành công": rsync thành công, lệnh nạp lại thành
công, container vẫn chạy. Chỉ có nội dung là sai.

Cùng cơ chế này từng được ghi nhận hồi tháng 5 với `scp`, nhưng chỉ ghi là "phải
restart container sau khi copy" chứ chưa hiểu nguyên nhân gốc là inode.

## Đã sửa thế nào

1. Ansible đồng bộ bằng `rsync --inplace` để giữ nguyên inode. Phải tắt kèm
   `delay_updates` vì hai tuỳ chọn này xung khắc.
2. Thêm bước nạp lại cấu hình Prometheus vào role sau mỗi lần triển khai.
3. Container đã dính lỗi phải dựng lại một lần để bám vào inode mới.

## Kiểm chứng

Sau khi dựng lại: container thấy đủ 10 rule, `promtool check rules` báo đúng số.

## Phòng ngừa

| Biện pháp | Trạng thái |
|---|---|
| `rsync --inplace` trong role `app_code` | Đã làm |
| Nạp lại cấu hình Prometheus sau mỗi lần triển khai | Đã làm |
| Ghi rõ cái bẫy inode vào tài liệu vận hành | Đã làm |
| Mount thư mục thay vì file đơn lẻ | Chưa — cần đổi nhiều compose |

## Bài học

"Đã đồng bộ file" không có nghĩa là "dịch vụ đã đọc file đó". Với cấu hình, phải
kiểm tra từ phía **bên trong container**, không phải từ phía máy chủ.
