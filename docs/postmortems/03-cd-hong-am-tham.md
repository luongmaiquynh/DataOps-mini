# Postmortem 3: CD hỏng âm thầm qua 3 lần push liên tiếp

**Ngày:** 15/09/2026 · **Mức độ:** trung bình

## Chuyện gì đã xảy ra

Ba lần push lên `main` liên tiếp, CD đều không triển khai được. VM1 vẫn đứng ở
commit cũ trong khi GitHub đã có code mới.

Không ai biết cho tới khi kiểm tra thủ công và thấy VM1 thiếu code mới.

## Phát hiện bằng cách nào

Không phải do cảnh báo. Phát hiện khi đang làm việc khác: kiểm tra xem VM1 đã có
hàm `upsert_dataframe` chưa thì thấy chưa có, dù đã push từ lâu.

## Nguyên nhân gốc

Hai cơ chế cùng ghi vào một thư mục trên VM1:

- **CD** dùng `git pull`.
- **Ansible** đẩy code bằng `rsync`.

rsync ghi xuống VM1 những file chưa được commit. Lần `git pull` sau đó bị Git từ
chối với lý do "untracked working tree files would be overwritten" — đúng theo
thiết kế của Git, nhưng job CD chỉ fail và không báo cho ai.

Vấn đề kép: **workflow hỏng thì không có cảnh báo nào**. GitHub gửi email cho
workflow thất bại, nhưng tài khoản khi đó không truy cập được.

## Đã sửa thế nào

1. CD đổi từ `git pull` sang `git fetch` + `git reset --hard FETCH_HEAD`. Repo là
   nguồn sự thật duy nhất cho VM1 nên ghi đè là đúng ý muốn.
2. Quy tắc vận hành: commit và push trước, rồi mới chạy Ansible lên VM1.
3. Ghi vào tài liệu vận hành để người sau biết hai cơ chế này từng cắn nhau.

## Kiểm chứng

Sau khi sửa, ba lần push tiếp theo đều thấy VM1 tự nhảy sang commit mới nhất.

## Phòng ngừa

| Biện pháp | Trạng thái |
|---|---|
| CD ghi đè thay vì merge | Đã làm |
| CD chỉ chạy sau khi CI xanh | Đã làm |
| Cảnh báo khi workflow thất bại | **Chưa** — phụ thuộc email GitHub |

## Bài học

Hai công cụ cùng quản lý một thư mục là công thức gây lỗi. Nếu buộc phải vậy thì
phải chọn rõ ai là nguồn sự thật và cho bên kia nhường.

Và quan trọng hơn: **một quy trình tự động hỏng mà không báo thì tệ hơn là không
có quy trình đó**, vì nó tạo cảm giác an toàn giả.
