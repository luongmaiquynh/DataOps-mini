# Runbook: ClockNotSynchronised

**Mức độ:** warning · **Điều kiện kích hoạt:** `dataops_chrony_synchronised == 0` suốt 10 phút — chrony không chọn được nguồn giờ nào, hoặc lệch quá 60 giây

## Khác gì ClockSkew

`ClockSkew` so đồng hồ từng máy với đồng hồ Prometheus, nên **mù khi cả lab cùng lệch**:
Prometheus chạy trên VM1 với đúng cái đồng hồ sai đó. Ngày 20/09/2026 ba VM chậm 8 tiếng
mà không alert nào bật. Alert này dùng số đo của chính chrony, tức so với nguồn giờ ngoài
lab, nên bắt được cả trường hợp đó.

## Ảnh hưởng

Lệch giờ làm hỏng những thứ trông không liên quan: runner GitHub bị từ chối phiên và báo
nhầm "registration has been deleted"; DAG theo giờ không chạy đúng lịch; `apt` từ chối
danh sách gói; đồ thị Grafana hiện dữ liệu lùi về quá khứ.

## Kiểm tra

```bash
# Ba VM có cùng giờ với máy Mac không
date -u; for ip in 2 3 4; do echo "vm$((ip-1)) $(ssh dataops@192.168.64.$ip 'date -u +%T')"; done

# chrony đang thấy gì: cột trạng thái '*' là nguồn đang được chọn, '?' là bị loại
ssh dataops@192.168.64.2 'chronyc tracking; chronyc sources -v; chronyc sourcestats'

# Script tự chữa có chạy không, đã phải chữa mấy lần
ssh dataops@192.168.64.2 'systemctl list-timers dataops-chrony-guard.timer --all;
  journalctl -t chrony-guard -n 20 --no-pager;
  grep -v "#" /var/lib/node_exporter/textfile/dataops_chrony.prom'
```

## Xử lý

1. **Bình thường không cần làm gì.** Timer `dataops-chrony-guard` chạy mỗi phút; sau 3 lần đo
   hỏng liên tiếp nó tự khởi động lại chrony. Alert có `for: 10m` nên chỉ bật khi cách đó
   đã thất bại.
2. **Chữa tay:** `ssh -t dataops@<ip> 'sudo systemctl restart chrony'`. Chờ khoảng 8 giây rồi
   kiểm lại bằng `date -u`.
3. **Đừng dùng `chronyc makestep`.** Ngày 20/09 nó trả `200 OK` mà vô tác dụng: makestep chỉ
   đặt cờ cho lần cập nhật tới, mà khi chrony đã loại hết nguồn thì không có lần cập nhật nào.
   Chỉ khởi động lại dịch vụ mới xoá được lịch sử mẫu đo đã bị phá.
4. **Nếu `chronyc sources` toàn dấu `?`** và khởi động lại không ăn: kiểm tra mạng ra ngoài
   của máy đó (UDP 123). Máy Mac mất mạng thì cả ba VM cùng mất nguồn giờ.
5. **Sau khi chữa xong**, kiểm tra runner GitHub: `ssh dataops@192.168.64.2 'systemctl is-active "actions.runner.*"'`.
   Nó tự kết nối lại trong 60 giây; đừng bấm Remove runner trên GitHub.

## Nguyên nhân gốc

Máy Mac ngủ làm ba VM bị tạm dừng, đồng hồ đứng yên. Khi máy thức, cú nhảy lớn phá thống kê
nội bộ của chrony — đã đo được ước lượng sai số tần số gần 5 triệu ppm và độ lệch chuẩn 230
giây — khiến khoảng tin cậy của mọi nguồn rộng đến mức bị loại hết. Lệch vừa phải (101 phút,
19/09) thì chrony tự chỉnh trong vòng một phút; lệch 8 tiếng thì kẹt vô thời hạn.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
