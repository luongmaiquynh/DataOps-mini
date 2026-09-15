# Runbook

Mỗi alert trong `monitoring/prometheus/alerts.yml` có một runbook tương ứng, được
liên kết trực tiếp từ annotation `runbook_url` nên người trực bấm thẳng từ
Alertmanager là tới.

| Alert | Mức độ | Nội dung |
|---|---|---|
| [InstanceDown](InstanceDown.md) | critical | Target không phản hồi |
| [PostgreSQLDown](PostgreSQLDown.md) | critical | Database không kết nối được |
| [LowMemory](LowMemory.md) | critical | RAM còn dưới 10% |
| [BackupStale](BackupStale.md) | critical | Quá 26 giờ không có backup |
| [BackupRestoreTestFailed](BackupRestoreTestFailed.md) | critical | Backup không restore được |
| [HighCpuUsage](HighCpuUsage.md) | warning | CPU trên 80% |
| [DiskSpaceLow](DiskSpaceLow.md) | warning | Đĩa còn dưới 15% |
| [ContainerRestartingTooMuch](ContainerRestartingTooMuch.md) | warning | Container crash-loop |
| [BackupMetricMissing](BackupMetricMissing.md) | warning | Không thấy metric backup |
| [BackupRestoreTestStale](BackupRestoreTestStale.md) | warning | Lâu chưa kiểm chứng backup |

Mỗi runbook trả lời bốn câu hỏi: chuyện gì đang xảy ra, ảnh hưởng ra sao, kiểm tra
bằng lệnh nào, và xử lý thế nào.
