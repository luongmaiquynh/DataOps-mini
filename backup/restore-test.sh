#!/bin/bash
# =============================================================================
# restore-test.sh — Kiểm chứng bản backup mới nhất có restore được không.
#
# Một bản backup chưa từng restore thì chưa phải là backup. Script này dựng
# một PostgreSQL tạm trong container, restore bản dump mới nhất vào đó, kiểm
# tra số bảng và số dòng, rồi xoá container.
#
# Chạy trên VM3 (nơi lưu backup). Cron: 3:00 sáng Chủ nhật hàng tuần.
# Thoát khác 0 nếu bản backup không dùng được.
# =============================================================================
set -uo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/backup/postgres}"
PG_IMAGE="${PG_IMAGE:-postgres:15.17}"
CONTAINER="restore_test_$$"
TMP_PASS="$(openssl rand -hex 16)"
CHECK_DB="restore_check"

# Ngưỡng tối thiểu để coi bản dump là hợp lệ
MIN_TABLES="${MIN_TABLES:-30}"
MIN_EMPLOYEE_ROWS="${MIN_EMPLOYEE_ROWS:-1}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
METRIC_FILE="$TEXTFILE_DIR/dataops_restore_test.prom"

write_metrics() {
    local success="$1" tables="${2:-0}" rows="${3:-0}"
    [ -d "$TEXTFILE_DIR" ] || return 0
    local tmp="$METRIC_FILE.$$"
    {
        echo "# HELP dataops_restore_test_success Lần kiểm chứng restore gần nhất có đạt không (1/0)"
        echo "# TYPE dataops_restore_test_success gauge"
        echo "dataops_restore_test_success $success"
        echo "# HELP dataops_restore_test_timestamp_seconds Thời điểm chạy kiểm chứng gần nhất"
        echo "# TYPE dataops_restore_test_timestamp_seconds gauge"
        echo "dataops_restore_test_timestamp_seconds $(date +%s)"
        echo "# HELP dataops_restore_test_tables Số bảng khôi phục được"
        echo "# TYPE dataops_restore_test_tables gauge"
        echo "dataops_restore_test_tables $tables"
        echo "# HELP dataops_restore_test_rows Số dòng dữ liệu nghiệp vụ khôi phục được"
        echo "# TYPE dataops_restore_test_rows gauge"
        echo "dataops_restore_test_rows $rows"
    } > "$tmp" && mv "$tmp" "$METRIC_FILE"
}
cleanup() { docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT

log "===== BẮT ĐẦU KIỂM CHỨNG BACKUP ====="

# Chỉ lấy bản dump database; roles_*.sql.gz là file riêng, xử lý ở bước sau.
BACKUP_FILE=$(ls -t "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null | head -1)
if [ -z "$BACKUP_FILE" ]; then
    log "[ERROR] Không tìm thấy file backup nào trong $BACKUP_DIR"
    write_metrics 0
    exit 1
fi
log "File kiểm tra : $(basename "$BACKUP_FILE") ($(du -h "$BACKUP_FILE" | cut -f1))"
log "Tuổi của file : $(( ( $(date +%s) - $(stat -c %Y "$BACKUP_FILE") ) / 3600 )) giờ"

# --- Bước 1: file nén còn nguyên vẹn không ---
if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
    log "[ERROR] File gzip hỏng, không giải nén được"
    write_metrics 0
    exit 1
fi
log "[OK] File gzip hợp lệ"

# --- Bước 2: dựng PostgreSQL tạm ---
if ! docker run -d --name "$CONTAINER" -e POSTGRES_PASSWORD="$TMP_PASS" "$PG_IMAGE" >/dev/null 2>&1; then
    log "[ERROR] Không dựng được container PostgreSQL tạm từ image $PG_IMAGE"
    write_metrics 0
    exit 1
fi

for i in $(seq 1 30); do
    if docker exec "$CONTAINER" pg_isready -U postgres -q 2>/dev/null; then break; fi
    sleep 2
    if [ "$i" -eq 30 ]; then log "[ERROR] PostgreSQL tạm không sẵn sàng sau 60 giây"; exit 1; fi
done
log "[OK] Đã dựng PostgreSQL tạm ($PG_IMAGE)"

# --- Bước 3: restore định nghĩa role trước ---
# Bản dump database chứa lệnh gán quyền sở hữu cho các role; nếu role chưa tồn
# tại thì toàn bộ restore sẽ dừng với 'role ... does not exist'.
ROLES_FILE=$(ls -t "$BACKUP_DIR"/roles_*.sql.gz 2>/dev/null | head -1)
if [ -n "$ROLES_FILE" ]; then
    zcat "$ROLES_FILE" | docker exec -i "$CONTAINER" psql -U postgres -q >/dev/null 2>&1
    log "[OK] Đã restore định nghĩa role từ $(basename "$ROLES_FILE")"
else
    log "[WARN] Không có file roles_*.sql.gz — tạo tạm role để restore tiếp"
    docker exec "$CONTAINER" psql -U postgres -q -c "CREATE ROLE dataops LOGIN SUPERUSER" >/dev/null 2>&1
fi

# --- Bước 4: restore database ---
docker exec "$CONTAINER" psql -U postgres -q -c "CREATE DATABASE $CHECK_DB" >/dev/null 2>&1
if ! zcat "$BACKUP_FILE" | docker exec -i "$CONTAINER" psql -U postgres -d "$CHECK_DB" -q -v ON_ERROR_STOP=1 >/dev/null 2>&1; then
    log "[ERROR] Restore thất bại — bản backup KHÔNG dùng được"
    write_metrics 0
    exit 1
fi
log "[OK] Restore thành công"

# --- Bước 5: dữ liệu có thật sự ở đó không ---
q() { docker exec "$CONTAINER" psql -U postgres -d "$CHECK_DB" -At -c "$1" 2>/dev/null; }

TABLES=$(q "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
EMPLOYEES=$(q "SELECT count(*) FROM employees")
WEATHER=$(q "SELECT count(*) FROM weather_hanoi")

log "Số bảng       : ${TABLES:-0} (tối thiểu $MIN_TABLES)"
log "employees     : ${EMPLOYEES:-0} dòng"
log "weather_hanoi : ${WEATHER:-0} dòng"

FAILED=0
[ "${TABLES:-0}" -lt "$MIN_TABLES" ] && { log "[ERROR] Số bảng thấp bất thường"; FAILED=1; }
[ "${EMPLOYEES:-0}" -lt "$MIN_EMPLOYEE_ROWS" ] && { log "[ERROR] Bảng employees rỗng"; FAILED=1; }

if [ "$FAILED" -ne 0 ]; then
    write_metrics 0 "${TABLES:-0}" "$(( ${EMPLOYEES:-0} + ${WEATHER:-0} ))"
    log "===== KIỂM CHỨNG THẤT BẠI ====="
    exit 1
fi

write_metrics 1 "$TABLES" "$(( EMPLOYEES + WEATHER ))"
log "[OK] Dữ liệu đầy đủ sau khi restore"
log "===== KIỂM CHỨNG THÀNH CÔNG ====="
exit 0
