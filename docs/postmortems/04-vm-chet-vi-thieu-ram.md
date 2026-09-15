# Postmortem 4: Ba VM chết dần vì cấp phát RAM vượt mức

**Ngày:** 15/09/2026 · **Mức độ:** nghiêm trọng

## Chuyện gì đã xảy ra

Trong lúc đang kiểm tra hệ thống, VM3 ngừng phản hồi: không SSH được, không ping
được, Prometheus báo `InstanceDown`. Khoảng một giờ sau, cả VM1 và VM2 cũng mất
kết nối.

Toàn bộ hệ thống dừng hoạt động.

## Phát hiện bằng cách nào

Alert `InstanceDown` bật lên đúng cho VM3 — hệ thống giám sát làm đúng việc của
nó. Nhưng khi VM1 chết theo thì chính hệ thống giám sát cũng chết, nên hai VM sau
không có cảnh báo nào.

Đây chính là tình huống dẫn tới việc xây dead man's switch sau đó.

## Nguyên nhân gốc

Máy Mac có **16 GB RAM**. Ba VM được cấp mỗi máy **8 GB**, tổng **24 GB** — vượt
50% so với RAM thật, chưa tính khoảng 4–5 GB cho macOS.

Linux càng chạy lâu càng lấp đầy page cache và không trả RAM lại cho máy chủ. Mức
chiếm dụng tăng dần cho tới khi macOS phải nén và swap liên tục, và các VM bị treo
theo thứ tự.

Cần nói rõ: **nguyên nhân này chưa được chứng minh dứt điểm**, vì các máy đã tắt
trước khi kịp đo. Nhưng việc cấp 24 GB trên máy 16 GB là sai rõ ràng bất kể có
phải nguyên nhân trực tiếp hay không.

## Đã sửa thế nào

Chưa đổi mức RAM — chủ nhà muốn giữ nguyên và đo mức dùng thật trước khi quyết
định, đó là cách làm đúng: đo rồi mới chỉnh, không chỉnh theo cảm tính.

Việc đã làm:
1. Thêm node-exporter cho VM2 để không còn máy nào là điểm mù về tài nguyên.
2. Thêm dead man's switch để lần sau hệ thống giám sát chết thì vẫn có người biết.
3. Thêm systemd unit để sau khi bật máy lại, dịch vụ tự lên.

## Phòng ngừa

| Biện pháp | Trạng thái |
|---|---|
| Giám sát RAM cả 3 máy | Đã làm |
| Cảnh báo `LowMemory` dưới 10% | Đã có từ trước |
| Dead man's switch | Đã làm |
| Dịch vụ tự khởi động sau khi máy lên | Đã làm |
| Đo mức dùng RAM thật rồi chỉnh cấp phát | **Chưa làm** |

## Bài học

Hệ thống giám sát chạy trên chính hạ tầng mà nó giám sát thì sẽ chết cùng hạ tầng
đó. Luôn cần một thứ nằm **bên ngoài** để báo tin — đó là toàn bộ lý do tồn tại
của dead man's switch.
