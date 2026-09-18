#!/bin/bash
# =============================================================================
# apply-monitoring-config.sh — Áp dụng cấu hình Loki và Promtail khi nó đổi.
#
# Vì sao cần: hai dịch vụ này đọc cấu hình đúng một lần lúc khởi động và không
# nạp lại nóng được (Loki không hỗ trợ; Promtail thì có nhưng image không có
# công cụ HTTP để gọi). Trước đây không ai khởi động lại chúng khi cấu hình đổi:
# sửa loki-config.yml, đẩy xuống VM1, file đổi nhưng Loki vẫn chạy cấu hình cũ
# mà không báo gì.
#
# Với mỗi dịch vụ:
#   1. kiểm tra cấu hình mới bằng một container tạm cùng image — sai thì dừng,
#      dịch vụ đang chạy giữ nguyên cấu hình cũ
#   2. so mã băm với lần áp dụng thành công gần nhất
#   3. chỉ khởi động lại dịch vụ nào thật sự đổi
#
# Ansible (role monitoring) và CD (deploy-monitoring) cùng gọi script này, nên
# cấu hình đổi theo đường nào cũng được áp dụng.
# In "APPLIED <dịch vụ>" cho mỗi dịch vụ được khởi động lại.
# =============================================================================
set -uo pipefail

REPO_DIR="${REPO_DIR:-/home/dataops/dataops}"
STATE_DIR="${STATE_DIR:-$HOME/.local/state/dataops-config}"
mkdir -p "$STATE_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# dịch vụ | thư mục cấu hình | file cấu hình | nơi mount trong container | cờ kiểm tra
SERVICES=(
    "loki|monitoring/loki|loki-config.yml|/etc/loki|-verify-config"
    "promtail|monitoring/promtail|promtail-config.yml|/etc/promtail|-check-syntax"
)

FAILED=0
for entry in "${SERVICES[@]}"; do
    IFS='|' read -r svc dir file mnt check <<< "$entry"
    cfg="$REPO_DIR/$dir/$file"

    if [ ! -f "$cfg" ]; then
        log "[ERROR] $svc: không thấy $cfg"
        FAILED=1
        continue
    fi

    new_hash=$(sha256sum "$cfg" | cut -d' ' -f1)
    old_hash=$(cat "$STATE_DIR/$svc.sha256" 2>/dev/null || true)
    if [ "$new_hash" = "$old_hash" ]; then
        log "[OK] $svc: cấu hình không đổi"
        continue
    fi

    image=$(docker inspect "$svc" --format '{{.Config.Image}}' 2>/dev/null)
    if [ -z "$image" ]; then
        log "[ERROR] $svc: container không tồn tại"
        FAILED=1
        continue
    fi

    if ! docker run --rm -v "$REPO_DIR/$dir:$mnt:ro" "$image" \
            "-config.file=$mnt/$file" "$check" >/dev/null 2>&1; then
        log "[ERROR] $svc: cấu hình mới KHÔNG hợp lệ — giữ nguyên cấu hình đang chạy"
        FAILED=1
        continue
    fi

    docker restart "$svc" >/dev/null
    running=false
    for _ in $(seq 1 30); do
        if [ "$(docker inspect "$svc" --format '{{.State.Running}} {{.State.Restarting}}')" = "true false" ]; then
            running=true
            break
        fi
        sleep 2
    done
    if [ "$running" != true ]; then
        log "[ERROR] $svc: không chạy lại được sau khi khởi động lại"
        FAILED=1
        continue
    fi

    echo "$new_hash" > "$STATE_DIR/$svc.sha256"
    log "[OK] $svc: đã áp dụng cấu hình mới"
    echo "APPLIED $svc"
done

exit "$FAILED"
