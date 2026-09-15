# Runbook: TLSCertExpiringSoon

**Mức độ:** warning · **Điều kiện kích hoạt:** chứng chỉ TLS của một endpoint còn hạn dưới 7 ngày

## Ảnh hưởng

Chưa mất dịch vụ. Nhưng nếu để hết hạn, trình duyệt sẽ chặn và các phép thử
blackbox sẽ fail hàng loạt.

## Kiểm tra

```bash
# Hạn còn lại của từng endpoint
curl -sk "https://prometheus.dataops.test/api/v1/query?query=(probe_ssl_earliest_cert_expiry-time())/86400"

# Xem chứng chỉ thật
echo | openssl s_client -connect grafana.dataops.test:443 \
  -servername grafana.dataops.test 2>/dev/null | openssl x509 -noout -dates -issuer
```

## Xử lý

Caddy tự cấp và tự gia hạn chứng chỉ từ CA nội bộ, nên alert này báo rằng
**việc tự gia hạn đang hỏng**, chứ không phải bạn cần gia hạn bằng tay.

1. Xem log Caddy: `docker logs caddy --tail 50 | grep -i cert`
2. Kiểm tra volume lưu CA còn nguyên không: `docker volume ls | grep caddy_data`.
   Mất volume này là CA bị sinh lại, trình duyệt sẽ cảnh báo lại từ đầu.
3. Khởi động lại Caddy: `docker compose -f docker-compose-monitoring.yml restart caddy`
4. Nếu vẫn không gia hạn: xoá chứng chỉ cũ trong volume rồi khởi động lại để Caddy cấp mới.
