#!/bin/bash
# =============================================================================
# chrony-guard.sh — Đo tình trạng đồng bộ giờ và tự chữa khi chrony kẹt.
#
# Vì sao cần (sự cố 20/09/2026): máy Mac ngủ 8 tiếng, ba VM bị tạm dừng nên
# đồng hồ đứng yên. Khi máy thức, chrony đo đúng độ lệch (-28899 giây ở cả 4
# nguồn) nhưng thống kê nội bộ bị phá — ước lượng sai số tần số gần 5 triệu ppm
# — nên nó loại bỏ mọi nguồn và nằm im vô thời hạn. `chronyc makestep` trả
# "200 OK" mà vô tác dụng, vì makestep chỉ đặt cờ cho lần cập nhật tới, mà
# không có nguồn nào được chọn thì không bao giờ có lần cập nhật.
# Chỉ `systemctl restart chrony` mới chữa được: nó xoá lịch sử mẫu đo.
#
# Hệ quả lúc đó: runner GitHub bị từ chối phiên và báo nhầm là "registration
# has been deleted"; alert ClockSkew không bắt được vì nó so đồng hồ với
# Prometheus, mà Prometheus chạy trên VM1 với cùng cái đồng hồ sai.
#
# Chạy trên cả 3 VM bằng systemd timer, mỗi phút, dưới quyền root.
# Đặt DRY_RUN=1 để chỉ đo và không khởi động lại gì (dùng khi chạy thử).
# =============================================================================
set -uo pipefail

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
STATE_DIR="${STATE_DIR:-/var/lib/dataops-chrony-guard}"
METRIC_FILE="$TEXTFILE_DIR/dataops_chrony.prom"
FAIL_FILE="$STATE_DIR/consecutive_failures"
RESTART_FILE="$STATE_DIR/restarts_total"

# Chịu đựng bao nhiêu lần đo hỏng liên tiếp trước khi khởi động lại chrony.
# Lúc máy vừa boot, chrony cần vài chục giây mới chọn được nguồn — đừng khởi
# động lại ngay, nếu không sẽ thành vòng lặp khởi động lại vô tận.
FAIL_LIMIT="${FAIL_LIMIT:-3}"
# Lệch quá ngưỡng này (giây) thì coi là hỏng, kể cả khi chrony vẫn chọn được nguồn.
OFFSET_LIMIT="${OFFSET_LIMIT:-60}"

mkdir -p "$STATE_DIR" 2>/dev/null
[ -f "$FAIL_FILE" ] || echo 0 > "$FAIL_FILE"
[ -f "$RESTART_FILE" ] || echo 0 > "$RESTART_FILE"

fails=$(cat "$FAIL_FILE" 2>/dev/null); fails=${fails:-0}
restarts=$(cat "$RESTART_FILE" 2>/dev/null); restarts=${restarts:-0}

# --- Đọc số đo. Dùng -c (CSV) vì chuỗi tiếng Anh của chronyc đổi giữa các bản ---
# tracking: trường 1 = Reference ID, trường 5 = độ lệch hệ thống (giây).
tracking=$(chronyc -n -c tracking 2>/dev/null)
refid=$(echo "$tracking" | cut -d, -f1)
offset=$(echo "$tracking" | cut -d, -f5)

# sources: trường 2 = trạng thái ('*' là nguồn đang được chọn),
# trường 9 = độ lệch đo được của nguồn đó.
sources=$(chronyc -n -c sources 2>/dev/null)
selected=$(echo "$sources" | awk -F, '$2 == "*"' | wc -l | tr -d ' ')
max_src_offset=$(echo "$sources" | awk -F, 'NF >= 9 {v = $9 < 0 ? -$9 : $9; if (v > m) m = v} END {printf "%.6f", m + 0}')

# Không gọi được chronyc thì coi như chưa đồng bộ, nhưng ĐỪNG khởi động lại:
# có thể chính chronyd đang khởi động dở.
if [ -z "$tracking" ]; then
    refid="00000000"; offset="0"; selected=0; max_src_offset=0
fi

abs_offset=$(awk -v v="${offset:-0}" 'BEGIN {printf "%.9f", v < 0 ? -v : v}')

# Đồng bộ được = có nguồn đang chọn, Reference ID khác 0, và độ lệch trong ngưỡng.
synced=1
[ "$selected" -ge 1 ] || synced=0
[ "$refid" != "00000000" ] || synced=0
awk -v v="$abs_offset" -v lim="$OFFSET_LIMIT" 'BEGIN {exit !(v > lim)}' && synced=0
# Nguồn báo lệch lớn mà chrony vẫn tự nhận là ổn: đúng kiểu kẹt hôm 20/09.
awk -v v="$max_src_offset" -v lim="$OFFSET_LIMIT" 'BEGIN {exit !(v > lim)}' && synced=0

healed=0
if [ "$synced" -eq 1 ]; then
    fails=0
else
    fails=$((fails + 1))
    if [ "$fails" -ge "$FAIL_LIMIT" ]; then
        if [ "${DRY_RUN:-0}" = "1" ]; then
            logger -t chrony-guard "DRY_RUN: dang le da khoi dong lai chrony (fails=$fails)"
        else
            logger -t chrony-guard "chrony khong dong bo $fails lan lien tiep, khoi dong lai"
            if systemctl restart chrony; then
                restarts=$((restarts + 1))
                healed=1
            fi
        fi
        fails=0
    fi
fi

echo "$fails" > "$FAIL_FILE"
echo "$restarts" > "$RESTART_FILE"

# --- Ghi metric: file tạm rồi mv, để node-exporter không đọc phải file viết dở ---
[ -d "$TEXTFILE_DIR" ] || exit 0
tmp="$METRIC_FILE.$$"
{
    echo "# HELP dataops_chrony_synchronised Máy có đang đồng bộ giờ không (1/0)"
    echo "# TYPE dataops_chrony_synchronised gauge"
    echo "dataops_chrony_synchronised $synced"
    echo "# HELP dataops_chrony_offset_seconds Độ lệch chrony tự báo, so với nguồn giờ"
    echo "# TYPE dataops_chrony_offset_seconds gauge"
    echo "dataops_chrony_offset_seconds $abs_offset"
    echo "# HELP dataops_chrony_source_offset_seconds Độ lệch lớn nhất các nguồn NTP đo được"
    echo "# TYPE dataops_chrony_source_offset_seconds gauge"
    echo "dataops_chrony_source_offset_seconds $max_src_offset"
    echo "# HELP dataops_chrony_sources_selected Số nguồn giờ đang được chọn"
    echo "# TYPE dataops_chrony_sources_selected gauge"
    echo "dataops_chrony_sources_selected $selected"
    echo "# HELP dataops_chrony_guard_restarts_total Số lần script phải khởi động lại chrony"
    echo "# TYPE dataops_chrony_guard_restarts_total counter"
    echo "dataops_chrony_guard_restarts_total $restarts"
} > "$tmp" && mv "$tmp" "$METRIC_FILE"

# Luôn thoát 0: timer báo hỏng chỉ khi script chết thật, còn việc "chrony đang
# lệch" được báo qua metric chứ không qua mã thoát.
[ "$healed" -eq 1 ] && logger -t chrony-guard "da khoi dong lai chrony xong"
exit 0
