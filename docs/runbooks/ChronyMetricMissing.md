# Runbook: ChronyMetricMissing

**Mức độ:** warning · **Điều kiện kích hoạt:** `dataops_chrony_synchronised` biến mất khỏi Prometheus suốt 30 phút

## Ảnh hưởng

Không có số đo thì không biết đồng hồ có đúng hay không, và `ClockNotSynchronised` cũng
không thể bật. Đây là alert canh cho chính phép đo — im lặng không có nghĩa là ổn.

## Kiểm tra

```bash
# Timer còn chạy không, lần chạy gần nhất khi nào
ssh dataops@192.168.64.2 'systemctl list-timers dataops-chrony-guard.timer --all;
  systemctl status dataops-chrony-guard.service --no-pager | head -12'

# File metric có được ghi không
ssh dataops@192.168.64.2 'ls -l /var/lib/node_exporter/textfile/;
  grep -v "#" /var/lib/node_exporter/textfile/dataops_chrony.prom'

# Chạy tay xem lỗi gì
ssh dataops@192.168.64.2 'sudo /usr/local/bin/dataops-chrony-guard; echo "exit=$?"'
```

## Xử lý

1. **Timer không còn:** chạy lại playbook — `ansible-playbook site.yml --limit vm1 --ask-become-pass`.
2. **Thiếu thư mục textfile:** playbook cũng tạo lại `/var/lib/node_exporter/textfile` với đúng quyền.
3. **node-exporter không đọc được thư mục:** kiểm tra container có mount `/textfile` và có cờ
   `--collector.textfile.directory` không. VM2 chỉ được bật textfile collector từ 21/09/2026.
4. **Metric có trên máy nhưng Prometheus không thấy:** xem target tương ứng trong
   https://prometheus.dataops.test/targets.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
