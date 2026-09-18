#!/bin/bash
# =============================================================================
# unit-status-metrics.sh — Đưa trạng thái các systemd unit quan trọng vào
# Prometheus qua textfile collector.
#
# Vì sao cần: runner GitHub đã chết hai lần mà không alert nào bật; lần nào cũng
# phải có người tình cờ để ý CD không chạy. Hai con số cho mỗi unit:
#   - đang chạy hay không
#   - đã tự khởi động lại bao nhiêu lần (runner nay tự khởi động lại, nên chết
#     thật sẽ hiện ra dưới dạng khởi động lại liên tục chứ không phải "không chạy")
#
# Chạy trên VM1. Cron: mỗi phút.
# =============================================================================
set -uo pipefail

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
METRIC_FILE="$TEXTFILE_DIR/dataops_systemd.prom"
[ -d "$TEXTFILE_DIR" ] || exit 0

mapfile -t UNITS < <(systemctl list-units --all --plain --no-legend --type=service \
    'actions.runner.*' 'dataops-*' 2>/dev/null | awk '{print $1}')

tmp="$METRIC_FILE.$$"
{
    echo "# HELP dataops_systemd_unit_active Unit có đang chạy không (1/0)"
    echo "# TYPE dataops_systemd_unit_active gauge"
    for u in "${UNITS[@]}"; do
        state=$(systemctl is-active "$u" 2>/dev/null)
        [ "$state" = "active" ] && v=1 || v=0
        echo "dataops_systemd_unit_active{unit=\"$u\"} $v"
    done
    echo "# HELP dataops_systemd_unit_restarts_total Số lần systemd tự khởi động lại unit"
    echo "# TYPE dataops_systemd_unit_restarts_total counter"
    for u in "${UNITS[@]}"; do
        n=$(systemctl show -p NRestarts --value "$u" 2>/dev/null)
        echo "dataops_systemd_unit_restarts_total{unit=\"$u\"} ${n:-0}"
    done
} > "$tmp" && mv "$tmp" "$METRIC_FILE"
