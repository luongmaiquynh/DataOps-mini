# Postmortem 1: Backup chạy 4 tháng nhưng không restore được

**Ngày phát hiện:** 15/09/2026 · **Thời gian ẩn:** khoảng 4 tháng · **Mức độ:** nghiêm trọng

## Chuyện gì đã xảy ra

Script backup chạy tự động lúc 2:00 sáng mỗi ngày từ tháng 5/2026. Mỗi lần chạy
đều ghi log "Backup thành công", tạo file `.sql.gz` khoảng 150 KB, và tự xoá bản
cũ hơn 7 ngày đúng như thiết kế.

Ngày 15/09, lần đầu tiên có người thử restore một bản backup vào cụm PostgreSQL
mới. Nó thất bại ngay dòng đầu tiên:

```
ERROR: role "dataops" does not exist
```

Không một bản backup nào trong 4 tháng dùng được cho đúng tình huống mà backup
sinh ra để phục vụ: mất máy và phải dựng lại từ đầu.

## Phát hiện bằng cách nào

Không phải do cảnh báo. Không có cảnh báo nào cho việc này. Nó lộ ra khi viết
script kiểm chứng restore tự động — nghĩa là **nhờ chủ động đi kiểm tra**, chứ
không phải nhờ hệ thống báo.

## Nguyên nhân gốc

`pg_dump` của một database **không chứa định nghĩa user**. Bản dump có các lệnh
gán quyền sở hữu cho role `dataops`, nhưng bản thân role đó được lưu ở tầng cụm,
không nằm trong dump.

Restore vào chính máy cũ thì không sao vì role đã tồn tại sẵn. Nhưng kịch bản
thật của backup luôn là restore vào máy **mới**, nơi role chưa tồn tại.

Lỗi này không thể phát hiện bằng cách nhìn log, nhìn dung lượng file, hay kiểm
tra file gzip có hợp lệ không — cả ba đều bình thường.

## Đã sửa thế nào

1. `backup.sh` dump thêm định nghĩa role bằng `pg_dumpall --roles-only`, lưu
   thành file `roles_<timestamp>.sql.gz` đi kèm mỗi bản backup.
2. Viết `restore-test.sh`: dựng PostgreSQL tạm trong container, restore role rồi
   restore database, đếm số bảng và số dòng, sau đó xoá container.
3. Đặt lịch chạy 3:00 sáng Chủ nhật hàng tuần.
4. Xuất kết quả thành metric và thêm alert `BackupRestoreTestFailed`.

## Kiểm chứng

- Bản backup mới restore ra 49 bảng, `employees` 5 dòng, `weather_hanoi` 144 dòng.
- Cố tình tạo một file backup hỏng: script phát hiện và thoát với mã 1.
- Diễn tập khôi phục thật sang database mới trên VM2: mất 2 giây.

## Phòng ngừa

| Biện pháp | Trạng thái |
|---|---|
| Kiểm chứng restore tự động hàng tuần | Đã làm |
| Cảnh báo khi kiểm chứng thất bại | Đã làm |
| Cảnh báo khi quá 8 ngày không kiểm chứng | Đã làm |
| Diễn tập khôi phục thủ công mỗi quý | Ghi trong [dr-plan.md](../dr-plan.md) |

## Bài học

Một bản backup chưa từng được restore thì chưa phải là backup, mà chỉ là một file.
Điều đáng sợ không phải là không có backup — mà là **tin rằng mình có backup**
trong khi không có.
