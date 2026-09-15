# Runbook: Watchdog (dead man's switch)

**Mức độ:** none · **Trạng thái bình thường: LUÔN firing**

## Alert này khác mọi alert khác

`Watchdog` firing là chuyện bình thường, không phải sự cố. Nó là nhịp tim mà
Alertmanager gửi tới healthchecks.io mỗi 5 phút.

**Thứ đáng lo là khi nhịp tim NGỪNG.** Lúc đó healthchecks.io gửi email
`DOWN | dataops-alertmanager` cho bạn — và runbook này dành cho tình huống ấy.

## Nhận được email DOWN nghĩa là gì

Một trong các mắt xích sau đã đứt:

| Mắt xích | Kiểm tra |
|---|---|
| Prometheus không còn đánh giá rule | `curl -sk https://prometheus.dataops.test/-/ready` |
| Alertmanager chết hoặc không gửi được | `ssh dataops@192.168.64.2 'docker ps \| grep alertmanager'` |
| VM1 mất mạng ra ngoài | `ssh dataops@192.168.64.2 'curl -sS -m 10 https://hc-ping.com'` |
| VM1 tắt hẳn | `ping -c 2 192.168.64.2` |

Lưu ý: **nếu cả hệ thống giám sát chết thì bạn sẽ không nhận được alert nào khác**,
kể cả `InstanceDown` hay `PostgreSQLDown`. Email này có thể là tín hiệu duy nhất.

## Xử lý

```bash
# 1. VM1 còn sống không
ping -c 2 192.168.64.2 && ssh dataops@192.168.64.2 uptime

# 2. Stack monitoring còn chạy không
ssh dataops@192.168.64.2 'docker ps --format "{{.Names}} {{.Status}}"'
ssh dataops@192.168.64.2 'sudo systemctl status dataops-monitoring'

# 3. Alertmanager có gửi được không (log không ghi lần gửi thành công,
#    phải xem metric)
ssh dataops@192.168.64.2 'docker exec alertmanager wget -qO- \
  http://localhost:9093/metrics | grep notifications_total.*webhook'

# 4. Mạng ra ngoài
ssh dataops@192.168.64.2 'curl -sS -m 15 -o /dev/null -w "%{http_code}\n" https://hc-ping.com'
```

1. **Stack chết**: `sudo systemctl start dataops-monitoring`
2. **Mất mạng ra ngoài**: đây là sự cố đã gặp ngày 15/09/2026 — HTTPS từ VM treo
   trong khi HTTP vẫn chạy. Thường tự khỏi; nếu kéo dài, kiểm tra VPN hoặc phần mềm
   mạng trên máy Mac (Cloudflare WARP từng bị nghi ngờ).
3. **VM1 tắt**: bật lại trong UTM, dịch vụ tự lên nhờ systemd unit.

Sau khi khôi phục, healthchecks.io tự chuyển về xanh khi nhận được nhịp tim kế tiếp.

## Đã diễn tập

15/09/2026: tắt Alertmanager 17 phút → nhận email DOWN sau 14,5 phút → bật lại →
check tự xanh. Xem [chaos-drills.md](../chaos-drills.md).
