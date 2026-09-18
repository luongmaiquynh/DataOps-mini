# Postmortem 6: CD xoá cấu hình Alertmanager ngay lần đầu chạy lại

**Ngày xảy ra:** 18/09/2026 · **Thời gian mất cảnh báo:** khoảng 1 phút 30 giây · **Mức độ:** trung bình

## Chuyện gì đã xảy ra

Runner tự host trên VM1 bị GitHub xoá đăng ký từ 11:16 ngày 15/09, nên suốt ba ngày
không có lần deploy tự động nào. Ngày 18/09 đăng ký lại runner, CD chạy ngay hai lần
liên tiếp cho hai commit đang chờ. Cả hai lần `deploy-vm1` đều thành công, cả hai lần
`deploy-monitoring` đều **thất bại**, và Alertmanager ngừng chạy:

```
$ ls -ld monitoring/alertmanager/alertmanager.yml
drwxr-xr-x 2 root root 4096 Sep 18 05:56 monitoring/alertmanager/alertmanager.yml
```

File cấu hình đã biến thành một **thư mục** thuộc root.

## Phát hiện bằng cách nào

Kiểm tra sức khỏe ngay sau khi CD chạy xong: job `deploy-monitoring` báo `Failed`,
container `alertmanager` kẹt ở trạng thái `Created`, và alert `EndpointDown` bật cho
`https://alerts.dataops.test`. Blackbox-exporter làm đúng việc của nó.

## Nguyên nhân gốc

Ba điều kiện phải xảy ra cùng lúc:

1. **Git trên VM1 đứng ở một commit rất cũ.** Lần reset cuối của CD là trước 11:16
   ngày 15/09. Lúc đó repo còn theo dõi `monitoring/alertmanager/alertmanager.yml`.
2. **File đó bị gỡ khỏi git sau thời điểm ấy** (commit `bb6c2bc`, 21:05 ngày 15/09),
   khi cấu hình Alertmanager chuyển sang do Ansible render từ vault, để URL dead man's
   switch không nằm trong repo.
3. **CD chạy `git reset --hard` rồi dựng lại cả Alertmanager.** Reset từ commit cũ sang
   commit mới, git thấy file được theo dõi ở bên cũ nhưng không có ở bên mới, nên xoá
   nó — kể cả khi nội dung trên đĩa là bản Ansible vừa render. Ngay sau đó
   `docker compose up --force-recreate alertmanager` mount một đường dẫn không còn tồn
   tại, và **Docker tự tạo thư mục trùng tên** thay vì báo lỗi.

Nghi vấn ban đầu (kiểm tra `git ls-files` trên máy Mac) cho kết quả "an toàn", vì đã
kiểm tra repo *hiện tại* chứ không kiểm tra commit *mà VM1 đang đứng*.

## Đã sửa thế nào

Khôi phục: xoá thư mục bằng chính Docker (vì thuộc root), render lại bằng đúng
template của role `monitoring` qua `ansible vm1 -m template`, rồi dựng lại container.
`amtool check-config` báo `SUCCESS`, đủ 2 receiver, URL dead man's switch còn nguyên.

Phòng ngừa, ba lớp:

| Lớp | Thay đổi |
|---|---|
| CD không đụng thứ nó không sở hữu | `deploy-monitoring` chỉ dựng lại Prometheus. Cấu hình Alertmanager thuộc về Ansible |
| Không để Docker tạo thư mục thay file | CD kiểm tra mọi file cấu hình được mount **trước** khi dựng container, thiếu thì dừng |
| Không commit nhầm được | `alertmanager.yml` nằm trong `.gitignore` |

## Bài học

- **Một lần deploy đầu tiên sau thời gian dài gián đoạn là một lần deploy đặc biệt.**
  Nó phải đi qua mọi thay đổi tích luỹ cùng lúc, kể cả những thay đổi về *cách* file
  được quản lý, chứ không chỉ nội dung file.
- **Bind mount một file không tồn tại là lỗi im lặng.** Docker không báo lỗi mà tạo
  thư mục, và lỗi chỉ lộ ra ở tầng ứng dụng.
- **Hai cơ chế cùng ghi vào một thư mục phải chia rõ ranh giới.** Ansible và CD đều
  ghi vào `/home/dataops/dataops` — đây là lần thứ hai điều đó gây sự cố (lần đầu là
  [postmortem 3](03-cd-hong-am-tham.md)).

---
*Các postmortem khác: [README.md](README.md)*
