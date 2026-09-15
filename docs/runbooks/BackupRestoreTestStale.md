# Runbook: BackupRestoreTestStale

**Mức độ:** warning · **Điều kiện kích hoạt:** Quá 8 ngày chưa kiểm chứng backup

## Ảnh hưởng

Backup vẫn chạy nhưng không còn được kiểm chứng, nên không biết có restore được
hay không.

## Kiểm tra

```bash
ssh dataops@192.168.64.4 'crontab -l | grep restore'
ssh dataops@192.168.64.4 'tail -10 /var/log/dataops-restore-test.log'
```

## Xử lý

1. Chạy tay ngay: `ssh dataops@192.168.64.4 'bash /home/dataops/restore-test.sh'`
2. Cron bị mất: `ansible-playbook site.yml --limit vm3 --ask-become-pass`
3. Job chạy nhưng không ghi metric: xem runbook `BackupMetricMissing`.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
