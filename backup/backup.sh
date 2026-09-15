#!/bin/bash
# =============================================================================
# backup.sh – Backup PostgreSQL database định kỳ
# Chạy trên VM3 (192.168.64.4), kết nối sang VM2 (192.168.64.3)
# Cron: 0 2 * * * /opt/dataops/backup/backup.sh >> /var/log/dataops-backup.log 2>&1
# =============================================================================

# --- Nạp cấu hình từ .env do Ansible sinh (chứa mật khẩu) ---
ENV_FILE="${ENV_FILE:-/home/dataops/dataops/.env}"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

# --- Cấu hình (giá trị trong .env được ưu tiên) ---
POSTGRES_HOST="${POSTGRES_HOST:-192.168.64.3}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-dataops}"
POSTGRES_DB="${POSTGRES_DB:-dataops_db}"
BACKUP_DIR="/opt/backup/postgres"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_${POSTGRES_DB}_${TIMESTAMP}.sql.gz"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

# --- Tạo thư mục backup nếu chưa có ---
mkdir -p "$BACKUP_DIR"

echo "$LOG_PREFIX ===== BẮT ĐẦU BACKUP ====="
echo "$LOG_PREFIX Database : $POSTGRES_DB @ $POSTGRES_HOST:$POSTGRES_PORT"
echo "$LOG_PREFIX File     : $BACKUP_FILE"

# --- Dùng pg_dump v15 cho đúng version server ---
PG_DUMP="/usr/lib/postgresql/15/bin/pg_dump"
PG_ISREADY="/usr/lib/postgresql/15/bin/pg_isready"

# --- Không có mật khẩu thì dừng ngay, không đoán giá trị mặc định ---
if [ -z "${POSTGRES_PASSWORD:-}" ]; then
    echo "$LOG_PREFIX [ERROR] Thiếu POSTGRES_PASSWORD. Kiểm tra file $ENV_FILE"
    exit 1
fi

# --- Kiểm tra kết nối PostgreSQL ---
if ! "$PG_ISREADY" -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -q; then
    echo "$LOG_PREFIX [ERROR] Không kết nối được PostgreSQL tại $POSTGRES_HOST:$POSTGRES_PORT"
    exit 1
fi

# --- Thực hiện backup và nén gzip ---
PGPASSWORD="$POSTGRES_PASSWORD" "$PG_DUMP" \
    -h "$POSTGRES_HOST" \
    -p "$POSTGRES_PORT" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    | gzip > "$BACKUP_FILE"

DUMP_EXIT=${PIPESTATUS[0]}

# --- Kiểm tra kết quả ---
if [ $DUMP_EXIT -eq 0 ] && [ -s "$BACKUP_FILE" ]; then
    FILE_SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
    echo "$LOG_PREFIX [OK] Backup thành công: $(basename $BACKUP_FILE) ($FILE_SIZE)"
else
    echo "$LOG_PREFIX [ERROR] Backup thất bại! Xóa file lỗi..."
    rm -f "$BACKUP_FILE"
    exit 1
fi

# --- Xóa backup cũ hơn RETENTION_DAYS ngày ---
DELETED=$(find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -print -delete | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "$LOG_PREFIX [OK] Đã xóa $DELETED file backup cũ hơn $RETENTION_DAYS ngày"
fi

# --- Liệt kê các backup hiện có ---
echo "$LOG_PREFIX Danh sách backup hiện có:"
ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null || echo "$LOG_PREFIX   (không có file nào)"

echo "$LOG_PREFIX ===== BACKUP HOÀN THÀNH ====="
exit 0
