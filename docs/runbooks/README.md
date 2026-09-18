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
| [EndpointDown](EndpointDown.md) | critical | Endpoint không phản hồi khi gọi thử |
| [MinioBackupStale](MinioBackupStale.md) | critical | Quá 26 giờ không sao lưu MinIO |
| [MinioRestoreTestFailed](MinioRestoreTestFailed.md) | critical | Bản sao MinIO không khôi phục được |
| [CeleryNoConsumer](CeleryNoConsumer.md) | critical | Không còn worker nào lấy việc |
| [AirflowTaskStuckQueued](AirflowTaskStuckQueued.md) | critical | Task nằm chờ quá 5 phút |
| [HighCpuUsage](HighCpuUsage.md) | warning | CPU trên 80% |
| [DiskSpaceLow](DiskSpaceLow.md) | warning | Đĩa còn dưới 15% |
| [ContainerRestartingTooMuch](ContainerRestartingTooMuch.md) | warning | Container crash-loop |
| [BackupMetricMissing](BackupMetricMissing.md) | warning | Không thấy metric backup |
| [MinioBackupMetricMissing](MinioBackupMetricMissing.md) | warning | Không thấy metric sao lưu MinIO |
| [CeleryQueueBacklog](CeleryQueueBacklog.md) | warning | Hàng đợi Celery dồn việc |
| [CeleryMetricMissing](CeleryMetricMissing.md) | warning | Không thấy phép đo hàng đợi |
| [ClockSkew](ClockSkew.md) | warning | Đồng hồ một máy lệch hơn 30 giây |
| [GitHubRunnerDown](GitHubRunnerDown.md) | warning | Runner không nhận job, CD sẽ không chạy |
| [BackupRestoreTestStale](BackupRestoreTestStale.md) | warning | Lâu chưa kiểm chứng backup |
| [TLSCertExpiringSoon](TLSCertExpiringSoon.md) | warning | Chứng chỉ TLS sắp hết hạn |
| [Watchdog](Watchdog.md) | none | Nhịp tim — luôn firing; runbook dành cho khi nó NGỪNG |

Mỗi runbook trả lời bốn câu hỏi: chuyện gì đang xảy ra, ảnh hưởng ra sao, kiểm tra
bằng lệnh nào, và xử lý thế nào.
