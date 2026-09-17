#!/bin/bash
# =============================================================================
# celery-queue-metrics.sh — Đo xem CÔNG VIỆC có chạy không, chứ không chỉ đo
# container có sống không.
#
# Vì sao cần: ngày 16/09/2026 Celery worker ngừng lấy việc khỏi hàng đợi suốt
# 25 giờ mà không có cảnh báo nào. `docker ps` báo Up, `celery inspect ping` báo
# OK, Prometheus báo 12/12 target UP — vì toàn bộ phép đo lúc đó đều hỏi "tiến
# trình còn sống không", không cái nào hỏi "hàng đợi có vơi không".
#
# Hai con số ở đây trả lời đúng câu hỏi đó:
#   - độ dài hàng đợi Celery trong Redis
#   - task đang chờ lâu nhất đã chờ bao nhiêu giây (lấy từ metadata Airflow)
#
# Chạy trên VM1. Cron: mỗi phút.
# =============================================================================
set -uo pipefail

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
METRIC_FILE="$TEXTFILE_DIR/dataops_celery.prom"
QUEUE="${CELERY_QUEUE:-default}"
# Hỏi qua container scheduler: nó đã có sẵn thư viện redis, sqlalchemy và đúng
# chuỗi kết nối trong biến môi trường. Không cần cài gì lên host, và cũng không
# phải đưa mật khẩu Redis ra dòng lệnh.
CONTAINER="${CELERY_PROBE_CONTAINER:-airflow_scheduler}"

write_metrics() {
    local success="$1" qlen="${2:-0}" age="${3:-0}"
    [ -d "$TEXTFILE_DIR" ] || return 0
    local tmp="$METRIC_FILE.$$"
    {
        echo "# HELP dataops_celery_probe_success Phép đo hàng đợi Celery có thực hiện được không (1/0)"
        echo "# TYPE dataops_celery_probe_success gauge"
        echo "dataops_celery_probe_success $success"
        if [ "$success" -eq 1 ]; then
            echo "# HELP dataops_celery_queue_length Số việc đang nằm chờ trong hàng đợi Celery"
            echo "# TYPE dataops_celery_queue_length gauge"
            echo "dataops_celery_queue_length $qlen"
            echo "# HELP dataops_airflow_queued_task_age_seconds Task Airflow đang chờ lâu nhất đã chờ bao lâu"
            echo "# TYPE dataops_airflow_queued_task_age_seconds gauge"
            echo "dataops_airflow_queued_task_age_seconds $age"
        fi
    } > "$tmp" && mv "$tmp" "$METRIC_FILE"
}

# -i là bắt buộc: không có nó thì heredoc bên dưới không đi vào được stdin của
# container và lệnh trả về rỗng. Đã mắc đúng lỗi này lúc chạy thử lần đầu.
OUT=$(docker exec -i -e PROBE_QUEUE="$QUEUE" "$CONTAINER" python - <<'PY' 2>/dev/null
import os
import redis
from sqlalchemy import create_engine, text

queue = os.environ.get("PROBE_QUEUE", "default")
qlen = redis.from_url(os.environ["AIRFLOW__CELERY__BROKER_URL"]).llen(queue)

engine = create_engine(os.environ["AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"])
with engine.connect() as conn:
    age = conn.execute(text(
        "SELECT COALESCE(EXTRACT(EPOCH FROM (now() - min(queued_dttm))), 0) "
        "FROM task_instance WHERE state = 'queued'"
    )).scalar()

print(int(qlen), int(age or 0))
PY
)

if [ -z "$OUT" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] Không hỏi được hàng đợi qua container $CONTAINER"
    write_metrics 0
    exit 1
fi

QLEN=$(echo "$OUT" | awk '{print $1}')
AGE=$(echo "$OUT" | awk '{print $2}')
case "$QLEN$AGE" in
    *[!0-9]*)
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] Kết quả không phải số: $OUT"
        write_metrics 0
        exit 1
        ;;
esac

write_metrics 1 "$QLEN" "$AGE"
exit 0
