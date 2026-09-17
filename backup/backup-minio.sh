#!/bin/bash
# =============================================================================
# backup-minio.sh — Sao lưu toàn bộ object trong MinIO (VM2) về VM3.
#
# Vì sao cần: pg_dump chỉ cứu được PostgreSQL. Data lake nằm trong volume
# minio_data trên VM2 và trước đây KHÔNG được sao lưu ở đâu cả — mất volume là
# mất toàn bộ file raw mà hai DAG đã đẩy lên từ tháng 5.
#
# Cách làm: dùng mc (MinIO client) chạy trong container để mirror bucket về đĩa
# VM3, rồi đóng gói thành một file .tar.gz có mốc thời gian. Mirror giữ bản
# "hiện tại" để lần sau chỉ tải phần thay đổi; file .tar.gz là bản chụp giữ lại
# theo lịch giữ.
#
# Chạy trên VM3. Cron: 30 2 * * *
# Thoát khác 0 nếu không sao lưu được.
# =============================================================================
set -uo pipefail

# --- Nạp cấu hình từ .env do Ansible sinh (chứa mật khẩu MinIO) ---
ENV_FILE="${ENV_FILE:-/home/dataops/dataops/.env}"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

MINIO_HOST="${MINIO_HOST:-192.168.64.3}"
MINIO_PORT="${MINIO_PORT:-9000}"
MINIO_BUCKET="${MINIO_BUCKET:-dataops-lake}"
BACKUP_DIR="${MINIO_BACKUP_DIR:-/opt/backup/minio}"
MIRROR_DIR="$BACKUP_DIR/current"
RETENTION_DAYS="${MINIO_RETENTION_DAYS:-7}"
# Ghim version: image mc lấy từ quay.io vì MinIO đã rút toàn bộ image khỏi Docker Hub.
MC_IMAGE="${MC_IMAGE:-quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE="$BACKUP_DIR/minio_${MINIO_BUCKET}_${TIMESTAMP}.tar.gz"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"
START_TS=$(date +%s)

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
METRIC_FILE="$TEXTFILE_DIR/dataops_minio_backup.prom"

# Ghi file tạm rồi mv, để node-exporter không đọc phải file viết dở.
write_metrics() {
    local success="$1" objects="${2:-0}" size_bytes="${3:-0}"
    [ -d "$TEXTFILE_DIR" ] || return 0
    local tmp="$METRIC_FILE.$$"
    {
        echo "# HELP dataops_minio_backup_success Lần sao lưu MinIO gần nhất có thành công không (1/0)"
        echo "# TYPE dataops_minio_backup_success gauge"
        echo "dataops_minio_backup_success $success"
        echo "# HELP dataops_minio_backup_duration_seconds Thời gian chạy sao lưu MinIO"
        echo "# TYPE dataops_minio_backup_duration_seconds gauge"
        echo "dataops_minio_backup_duration_seconds $(( $(date +%s) - START_TS ))"
        echo "# HELP dataops_minio_backup_objects Số object sao lưu được"
        echo "# TYPE dataops_minio_backup_objects gauge"
        echo "dataops_minio_backup_objects $objects"
        if [ "$success" -eq 1 ]; then
            echo "# HELP dataops_minio_backup_last_success_timestamp_seconds Thời điểm sao lưu MinIO thành công gần nhất"
            echo "# TYPE dataops_minio_backup_last_success_timestamp_seconds gauge"
            echo "dataops_minio_backup_last_success_timestamp_seconds $(date +%s)"
            echo "# HELP dataops_minio_backup_size_bytes Dung lượng bản sao lưu gần nhất"
            echo "# TYPE dataops_minio_backup_size_bytes gauge"
            echo "dataops_minio_backup_size_bytes $size_bytes"
        fi
    } > "$tmp" && mv "$tmp" "$METRIC_FILE"
}

echo "$LOG_PREFIX ===== BẮT ĐẦU SAO LƯU MINIO ====="
echo "$LOG_PREFIX Nguồn : http://$MINIO_HOST:$MINIO_PORT/$MINIO_BUCKET"
echo "$LOG_PREFIX Đích  : $ARCHIVE"

# --- Thiếu thông tin đăng nhập thì dừng, không đoán giá trị mặc định ---
if [ -z "${MINIO_ROOT_USER:-}" ] || [ -z "${MINIO_ROOT_PASSWORD:-}" ]; then
    echo "$LOG_PREFIX [ERROR] Thiếu MINIO_ROOT_USER hoặc MINIO_ROOT_PASSWORD. Kiểm tra $ENV_FILE"
    write_metrics 0
    exit 1
fi

# --- MinIO còn sống không ---
if ! curl -sf --max-time 10 "http://$MINIO_HOST:$MINIO_PORT/minio/health/live" >/dev/null; then
    echo "$LOG_PREFIX [ERROR] MinIO không phản hồi tại $MINIO_HOST:$MINIO_PORT"
    write_metrics 0
    exit 1
fi

mkdir -p "$MIRROR_DIR"

# --- Mirror bucket về đĩa ---
# Mật khẩu truyền qua biến môi trường rồi mới đưa vào `mc alias set`, không nhét
# vào URL: URL sẽ hỏng nếu mật khẩu có ký tự đặc biệt, và còn lộ trong ps.
# --user: nếu để container chạy bằng root thì mọi file mirror thuộc về root và
# user dataops không xoá hay ghi đè được nữa — đã mắc đúng lỗi này lúc chạy thử.
# MC_CONFIG_DIR phải trỏ vào chỗ ghi được, vì mc mặc định ghi cấu hình vào $HOME
# của root mà user thường không vào được.
if ! docker run --rm \
        --user "$(id -u):$(id -g)" \
        -e MC_CONFIG_DIR=/tmp/.mc \
        -e MC_USER="$MINIO_ROOT_USER" \
        -e MC_PASS="$MINIO_ROOT_PASSWORD" \
        -v "$MIRROR_DIR:/backup" \
        --entrypoint sh \
        "$MC_IMAGE" -c \
        "mc alias set lake http://$MINIO_HOST:$MINIO_PORT \"\$MC_USER\" \"\$MC_PASS\" >/dev/null && \
         mc mirror --overwrite --remove lake/$MINIO_BUCKET /backup/$MINIO_BUCKET"; then
    echo "$LOG_PREFIX [ERROR] mc mirror thất bại"
    write_metrics 0
    exit 1
fi

OBJECTS=$(find "$MIRROR_DIR" -type f ! -name '.*' | wc -l | tr -d ' ')
echo "$LOG_PREFIX [OK] Đã mirror $OBJECTS object"

if [ "$OBJECTS" -eq 0 ]; then
    echo "$LOG_PREFIX [ERROR] Không có object nào — coi như sao lưu thất bại, không tạo file rỗng"
    write_metrics 0 0
    exit 1
fi

# --- Đóng gói bản chụp ---
if ! tar czf "$ARCHIVE" -C "$MIRROR_DIR" . 2>/dev/null; then
    echo "$LOG_PREFIX [ERROR] Không đóng gói được $ARCHIVE"
    rm -f "$ARCHIVE"
    write_metrics 0 "$OBJECTS"
    exit 1
fi

# --- Kiểm tra ngay file vừa tạo có đọc lại được không ---
if ! tar tzf "$ARCHIVE" >/dev/null 2>&1; then
    echo "$LOG_PREFIX [ERROR] File vừa tạo không đọc lại được — xoá đi để khỏi tạo cảm giác an toàn giả"
    rm -f "$ARCHIVE"
    write_metrics 0 "$OBJECTS"
    exit 1
fi

SIZE_BYTES=$(stat -c %s "$ARCHIVE")
echo "$LOG_PREFIX [OK] Đã đóng gói: $(basename "$ARCHIVE") ($(du -h "$ARCHIVE" | cut -f1))"

# --- Xoá bản chụp cũ ---
DELETED=$(find "$BACKUP_DIR" -maxdepth 1 -name 'minio_*.tar.gz' -mtime "+$RETENTION_DAYS" -print -delete | wc -l | tr -d ' ')
if [ "$DELETED" -gt 0 ]; then
    echo "$LOG_PREFIX [OK] Đã xoá $DELETED bản chụp cũ hơn $RETENTION_DAYS ngày"
fi

write_metrics 1 "$OBJECTS" "$SIZE_BYTES"
echo "$LOG_PREFIX ===== SAO LƯU MINIO HOÀN THÀNH ====="
exit 0
