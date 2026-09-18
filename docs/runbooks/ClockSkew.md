# Runbook: ClockSkew

**Mức độ:** warning · **Điều kiện kích hoạt:** Đồng hồ một máy lệch hơn 30 giây so với Prometheus (VM1) suốt 5 phút

## Ảnh hưởng

Lệch giờ âm thầm làm hỏng những thứ trông không liên quan. Ngày 18/09/2026 đã gặp cả ba:

- Runner GitHub bị từ chối token, hiểu nhầm thành "registration has been deleted" rồi tự tắt.
- Script đo hàng đợi tính ra tuổi task **âm 647 giây** vì trừ hai mốc giờ của hai máy khác nhau.
- `apt` từ chối danh sách gói ("Release file is not valid yet") khi đồng hồ chậm.

## Kiểm tra

```bash
# Lệch bao nhiêu (dương = máy đó nhanh hơn VM1)
curl -sk "https://prometheus.dataops.test/api/v1/query?query=node_time_seconds-timestamp(node_time_seconds)"

# chrony có đang đồng bộ không, lệch bao nhiêu, hỏi máy chủ nào
ssh dataops@192.168.64.3 'chronyc tracking; chronyc sources -v'
```

## Xử lý

1. **Vừa sau khi máy Mac ngủ dậy**: chrony hỏi lại máy chủ giờ khoảng mỗi 64 giây và
   nhảy thẳng tới giờ đúng khi lệch quá 1 giây (`makestep 1 -1`), nên thường tự hết
   trong vài phút. Alert có `for: 5m` để không báo động cho trường hợp này.
2. **Kéo dài**: ép đồng bộ ngay — `ssh -t dataops@<ip> sudo chronyc makestep`.
3. **chrony không liên lạc được máy chủ giờ** (`chronyc sources` toàn dấu `?`): kiểm tra
   mạng ra ngoài của máy đó, UDP 123.
4. **Chỉ VM1 bình thường, hai máy kia cùng lệch một lượng như nhau**: có thể chính VM1
   (Prometheus) mới là máy sai. So với máy Mac: `date -u` trên Mac và trên VM1.

## Phòng ngừa

Đo bằng cách so với đồng hồ Prometheus chứ không dùng `node_timex_sync_status`: ngày
18/09 VM2 chậm 44 phút mà metric đó vẫn báo "đã đồng bộ" suốt 12 giờ, vì
systemd-timesyncd không biết máy ảo vừa bị tạm dừng. Từ 18/09 cả ba máy dùng chrony.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
