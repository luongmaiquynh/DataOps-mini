# Postmortem 5: Celery worker ngừng nhận việc nhưng mọi thứ vẫn báo xanh

**Ngày phát hiện:** 17/09/2026 · **Thời gian ẩn:** khoảng 25 giờ 30 phút · **Mức độ:** nghiêm trọng

## Chuyện gì đã xảy ra

Từ 06:41 ngày 16/09, Celery worker trên VM1 ngừng lấy việc khỏi hàng đợi. Mọi task
Airflow được đẩy vào Redis rồi nằm đó vĩnh viễn: 92 message tồn đọng, DAG
`ingest_csv` của ngày 16/09 thất bại, `ingest_weather_api` treo ở trạng thái
`running` suốt hai tiếng, và bảng `weather_hanoi` dừng lại ở mốc 16/09 23:00.

Trong suốt 25 giờ đó, không có một cảnh báo nào.

Cả ba DAG của hệ thống đều dính: `ingest_csv` thất bại, `ingest_weather_api` treo,
`data_quality_check` thất bại ở cả hai task. Điểm chung của chúng là các task đều
**không có `start_date`** — tức chưa từng được chạy, chỉ nằm chờ rồi bị đánh dấu
hỏng. Sau khi khắc phục, chạy lại `data_quality_check` thì cả hai task đều thành
công trong chưa tới một giây, xác nhận không DAG nào có lỗi logic.

## Vì sao không ai biết

Mọi chỉ dấu quen thuộc đều bình thường:

| Kiểm tra | Kết quả | Thực tế |
|---|---|---|
| `docker ps` | `Up 40 hours`, không restart lần nào | Tiến trình chính còn sống thật |
| `celery inspect ping` | `1 node online` | Trả lời qua pub/sub, không chứng minh gì về việc đọc hàng đợi |
| `celery inspect active_queues` | đang nghe queue `default` | Khai báo đúng, nhưng không còn đọc |
| `celery inspect active` | rỗng | Trông như worker đang rảnh, thực ra là đang chết |
| Prometheus | 12/12 target UP, 0 alert | Không có metric nào về hàng đợi Celery |

Nói cách khác: hệ thống giám sát theo dõi **container còn sống hay không**, chứ
chưa bao giờ theo dõi **công việc có chạy hay không**.

## Phát hiện bằng cách nào

Không phải nhờ cảnh báo. Nó lộ ra khi kiểm tra sức khỏe tổng thể sau một lần
triển khai: `airflow dags list-runs` cho thấy một DAG `failed` và một DAG `running`
suốt hai tiếng.

## Nguyên nhân gốc

Bằng chứng quyết định nằm ở phía Redis chứ không phải phía Airflow:

```
CLIENT LIST | grep brpop   →  0 client
LLEN default               →  92 (đứng yên qua nhiều lần đo)
HLEN unacked               →  0
CONFIG GET timeout         →  0
```

Celery worker khi rảnh phải luôn có một kết nối chặn ở `BRPOP` để chờ việc. Không
có kết nối nào như vậy, trong khi `unacked = 0` chứng tỏ worker chưa hề lấy message
ra rồi bỏ dở. Kết luận: **tiến trình consumer đã chết, còn tiến trình chính vẫn
sống và tiếp tục trả lời các lệnh inspect qua kênh pidbox (pub/sub)**.

Redis được loại khỏi diện nghi vấn vì `timeout = 0`, tức nó không tự ngắt kết nối
rảnh. Container cũng chưa restart lần nào (`RestartCount: 0`), nên không phải
worker vừa khởi động lại rồi kẹt.

Nguyên nhân sâu hơn — vì sao consumer chết mà không ghi một dòng log nào — chưa xác
định được, vì bằng chứng trong tiến trình đã mất khi restart. Điều ghi nhận được là
log duy nhất của container trong ngày hôm đó thuộc về tiến trình phụ `serve_logs`
(gunicorn), liên tục `WORKER TIMEOUT` và một lần `SIGKILL! Perhaps out of memory?`.
VM1 khi kiểm tra còn 4,4 GB RAM trống, nhưng máy Mac chủ đang dùng 15,3/16,4 GB
swap — nên sức ép bộ nhớ ở tầng máy chủ vẫn là giả thuyết đáng theo dõi.

## Đã sửa thế nào

Khắc phục tức thời: `docker restart airflow_worker`. Worker đăng ký lại consumer sau
2 giây và bắt đầu tiêu thụ hàng đợi ngay.

Nhưng khắc phục không phải bài học. Bài học là **hệ thống không có cách nào tự biết
điều này**. Đã thêm một script chạy mỗi phút trên VM1, đẩy ba số đo vào Prometheus
qua textfile collector:

| Metric | Trả lời câu hỏi | Alert |
|---|---|---|
| `dataops_celery_consumers` | Còn ai chờ lấy việc không (đếm client ở `BRPOP`) | `CeleryNoConsumer` sau 10 phút |
| `dataops_airflow_queued_task_age_seconds` | Task chờ lâu nhất đã chờ bao lâu | `AirflowTaskStuckQueued` trên 300 giây |
| `dataops_celery_queue_length` | Hàng đợi có đang dồn không | `CeleryQueueBacklog` trên 20 việc |

`CeleryNoConsumer` đo thẳng bằng chứng quyết định của sự cố này, và bật được cả khi
hệ thống đang rảnh — không cần đợi có task mới vào hàng đợi.

### Một lỗi trong chính bản sửa

Bản đầu của `AirflowTaskStuckQueued` đặt ngưỡng 900 giây. Nó qua được
`promtool check rules`, nhưng **không bao giờ bật được**: Airflow tự đánh dấu hỏng
task nằm chờ quá 600 giây (`task_queued_timeout`), nên tuổi task quay về 0 trước khi
chạm ngưỡng. Lỗi lộ ra khi đối chiếu ngưỡng với cấu hình thật của scheduler.

Để không lặp lại, nhóm alert này có unit test (`promtool test rules`) chạy trong CI:
mô phỏng chuỗi số liệu theo thời gian và khẳng định alert phải bật đúng lúc. Đã thử
nghịch — trả ngưỡng về 900 thì test đỏ.

### Diễn tập xác nhận — và lộ thêm một lỗi

Ngày 18/09 tái hiện sự cố bằng `celery control cancel_consumer default`. Lần thử
đầu, `CeleryNoConsumer` **không bật suốt 20 phút**: metric đếm kết nối có
`cmd=brpop`, nhưng `cmd` chỉ là lệnh *cuối cùng* kết nối đã chạy. Kết nối của worker
đã ngừng vẫn mang `cmd=brpop`, chỉ có `idle` tăng lên 1099 giây. Sau khi lọc thêm
`idle < 30` giây, lần thử thứ hai alert bật sau 11,5 phút và gửi thông báo thật.

Nếu không diễn tập, alert này sẽ nằm im đúng trong tình huống nó sinh ra để bắt.

## Bài học

- **Tiến trình còn sống không có nghĩa là nó còn làm việc.** Health check dựa trên
  "container Up" và "ping OK" bỏ lọt đúng loại hỏng nguy hiểm nhất: hỏng im lặng.
- **Đo ở phía hàng đợi, đừng chỉ đo ở phía dịch vụ.** Một hàng đợi không vơi là
  bằng chứng khách quan, không phụ thuộc vào việc tiến trình tự khai báo tình trạng.
- **Lệnh inspect của Celery đi qua kênh khác với đường lấy việc.** Vì thế nó có thể
  trả lời "OK" trong khi đường lấy việc đã đứt. Muốn biết sự thật thì hỏi Redis:
  có client nào đang `brpop` không.

---
*Các postmortem khác: [README.md](README.md)*
