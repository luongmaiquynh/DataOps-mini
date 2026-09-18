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
# --- Phần kiểm chứng bản sao MinIO ---
MINIO_BACKUP_DIR="${MINIO_BACKUP_DIR:-/opt/backup/minio}"
MINIO_IMAGE="${MINIO_IMAGE:-quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z}"
MC_IMAGE="${MC_IMAGE:-quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z}"
MINIO_CONTAINER="minio_restore_test_$$"
MINIO_DRILL_PORT="${MINIO_DRILL_PORT:-19001}"
MINIO_DRILL_USER="drilluser"
MINIO_DRILL_PASS="$(openssl rand -hex 16)"
MINIO_WORKDIR="/tmp/minio_restore_test_$$"
MINIO_BUCKET="${MINIO_BUCKET:-dataops-lake}"
MINIO_METRIC_FILE="$TEXTFILE_DIR/dataops_restore_test_minio.prom"

write_minio_metrics() {
    local success="$1" objects="${2:-0}"
    [ -d "$TEXTFILE_DIR" ] || return 0
    local tmp="$MINIO_METRIC_FILE.$$"
    {
        echo "# HELP dataops_restore_test_minio_success Lần kiểm chứng khôi phục MinIO gần nhất có đạt không (1/0)"
        echo "# TYPE dataops_restore_test_minio_success gauge"
        echo "dataops_restore_test_minio_success $success"
        echo "# HELP dataops_restore_test_minio_timestamp_seconds Thời điểm kiểm chứng MinIO gần nhất"
        echo "# TYPE dataops_restore_test_minio_timestamp_seconds gauge"
        echo "dataops_restore_test_minio_timestamp_seconds $(date +%s)"
        echo "# HELP dataops_restore_test_minio_objects Số object khôi phục được vào MinIO trắng"
        echo "# TYPE dataops_restore_test_minio_objects gauge"
        echo "dataops_restore_test_minio_objects $objects"
    } > "$tmp" && mv "$tmp" "$MINIO_METRIC_FILE"
}

# shellcheck disable=SC2317,SC2329  # SC2317 là mã của shellcheck bản cũ; được gọi gián tiếp qua trap EXIT bên dưới
cleanup() {
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    docker rm -f "$MINIO_CONTAINER" >/dev/null 2>&1 || true
    # Thư mục dữ liệu do MinIO trong container tạo ra, xoá bằng chính container
    # để không phụ thuộc quyền của user đang chạy script.
    [ -d "$MINIO_WORKDIR" ] && docker run --rm -v /tmp:/host alpine:3.20 \
        sh -c "rm -rf /host/$(basename "$MINIO_WORKDIR")" >/dev/null 2>&1
    rm -rf "$MINIO_WORKDIR" 2>/dev/null || true
}
trap cleanup EXIT

log "===== BẮT ĐẦU KIỂM CHỨNG BACKUP ====="

# Chỉ lấy bản dump database; roles_*.sql.gz là file riêng, xử lý ở bước sau.
# shellcheck disable=SC2012  # tên file do chính script backup sinh ra, không có ký tự lạ
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
# shellcheck disable=SC2012  # cùng lý do trên
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

# --- Bước 6: bản sao MinIO có đổ ngược được vào một MinIO trắng không ---
# pg_dump không chạm tới data lake, nên phần này kiểm chứng riêng: dựng một MinIO
# hoàn toàn trống, đổ bản sao mới nhất vào, rồi đếm lại số object.
log "--- Kiểm chứng bản sao MinIO ---"
MINIO_FAILED=0

# shellcheck disable=SC2012  # tên file do chính script backup sinh ra
MINIO_ARCHIVE=$(ls -t "$MINIO_BACKUP_DIR"/minio_*.tar.gz 2>/dev/null | head -1)
if [ -z "$MINIO_ARCHIVE" ]; then
    log "[ERROR] Không tìm thấy bản sao MinIO nào trong $MINIO_BACKUP_DIR"
    write_minio_metrics 0
    MINIO_FAILED=1
else
    log "File kiểm tra : $(basename "$MINIO_ARCHIVE") ($(du -h "$MINIO_ARCHIVE" | cut -f1))"
    mkdir -p "$MINIO_WORKDIR/data" "$MINIO_WORKDIR/restore"

    if ! tar xzf "$MINIO_ARCHIVE" -C "$MINIO_WORKDIR/restore" 2>/dev/null; then
        log "[ERROR] Không giải nén được bản sao MinIO"
        write_minio_metrics 0
        MINIO_FAILED=1
    else
        SRC_OBJECTS=$(find "$MINIO_WORKDIR/restore" -type f | wc -l | tr -d ' ')

        docker run -d --name "$MINIO_CONTAINER" \
            -e MINIO_ROOT_USER="$MINIO_DRILL_USER" \
            -e MINIO_ROOT_PASSWORD="$MINIO_DRILL_PASS" \
            -v "$MINIO_WORKDIR/data:/data" \
            -p "$MINIO_DRILL_PORT:9000" \
            "$MINIO_IMAGE" server /data >/dev/null 2>&1

        MINIO_READY=0
        for _ in $(seq 1 30); do
            if curl -sf --max-time 3 "http://127.0.0.1:$MINIO_DRILL_PORT/minio/health/live" >/dev/null 2>&1; then
                MINIO_READY=1
                break
            fi
            sleep 2
        done

        if [ "$MINIO_READY" -ne 1 ]; then
            log "[ERROR] MinIO tạm không sẵn sàng sau 60 giây"
            write_minio_metrics 0 "$SRC_OBJECTS"
            MINIO_FAILED=1
        else
            docker run --rm --network host --user "$(id -u):$(id -g)" \
                -e MC_CONFIG_DIR=/tmp/.mc \
                -e DRILL_USER="$MINIO_DRILL_USER" \
                -e DRILL_PASS="$MINIO_DRILL_PASS" \
                -v "$MINIO_WORKDIR/restore:/restore" \
                --entrypoint sh "$MC_IMAGE" -c \
                "mc alias set drill http://127.0.0.1:$MINIO_DRILL_PORT \"\$DRILL_USER\" \"\$DRILL_PASS\" >/dev/null && \
                 mc mb --ignore-existing drill/$MINIO_BUCKET >/dev/null && \
                 mc mirror --overwrite /restore/$MINIO_BUCKET drill/$MINIO_BUCKET" >/dev/null 2>&1

            # Đếm bằng chính mc, không đếm thư mục trên đĩa: MinIO lưu mỗi object
            # thành một thư mục mang tên object, nên đếm theo đuôi file sẽ sai ngay
            # khi lake chứa loại dữ liệu khác.
            DST_OBJECTS=$(docker run --rm --network host --user "$(id -u):$(id -g)" \
                -e MC_CONFIG_DIR=/tmp/.mc \
                -e DRILL_USER="$MINIO_DRILL_USER" \
                -e DRILL_PASS="$MINIO_DRILL_PASS" \
                --entrypoint sh "$MC_IMAGE" -c \
                "mc alias set drill http://127.0.0.1:$MINIO_DRILL_PORT \"\$DRILL_USER\" \"\$DRILL_PASS\" >/dev/null && \
                 mc ls --recursive drill/$MINIO_BUCKET | wc -l" 2>/dev/null | tr -d ' ')
            DST_OBJECTS="${DST_OBJECTS:-0}"
            log "object trong bản sao      : $SRC_OBJECTS"
            log "object sau khi khôi phục  : $DST_OBJECTS"

            if [ "$DST_OBJECTS" -ne "$SRC_OBJECTS" ] || [ "$SRC_OBJECTS" -eq 0 ]; then
                log "[ERROR] Số object không khớp — bản sao MinIO KHÔNG dùng được"
                write_minio_metrics 0 "$DST_OBJECTS"
                MINIO_FAILED=1
            else
                log "[OK] Khôi phục MinIO đạt: $DST_OBJECTS/$SRC_OBJECTS object"
                write_minio_metrics 1 "$DST_OBJECTS"
            fi
        fi
    fi
fi

if [ "$MINIO_FAILED" -ne 0 ]; then
    log "===== KIỂM CHỨNG THẤT BẠI (phần MinIO) ====="
    exit 1
fi

log "===== KIỂM CHỨNG THÀNH CÔNG ====="
exit 0
