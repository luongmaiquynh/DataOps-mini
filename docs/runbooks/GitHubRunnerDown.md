# Runbook: GitHubRunnerDown

**Mức độ:** warning · **Điều kiện kích hoạt:** Runner trên VM1 không chạy, tự khởi động lại quá 3 lần trong 30 phút, hoặc mất hẳn metric — kéo dài 15 phút

## Ảnh hưởng

CD không chạy. CI vẫn xanh, commit vẫn lên GitHub, nhưng không gì được deploy xuống
VM1 — và trước khi có alert này, không ai biết. Runner đã chết như vậy hai lần (15/09
và 18/09); lần nào cũng phải có người tình cờ để ý mới thấy.

## Kiểm tra

```bash
ssh dataops@192.168.64.2 'systemctl status actions.runner.*.service --no-pager'
ssh dataops@192.168.64.2 'journalctl -u "actions.runner.*" -n 30 --no-pager'
```

Trên GitHub: **Settings → Actions → Runners** — runner `dataops-vm1` có còn trong danh sách không.

## Xử lý

1. **Log có "registration has been deleted" nhưng runner VẪN còn trên GitHub**: không
   phải bị xoá thật. Đã gặp: VM1 vừa thức dậy sau khi máy Mac ngủ, đồng hồ còn sai nên
   GitHub từ chối token. Kiểm tra đồng hồ (runbook `ClockSkew`) rồi chờ — runner tự khởi
   động lại sau 60 giây nhờ drop-in `Restart=always`. Cần ngay thì:
   `ssh -t dataops@192.168.64.2 'cd ~/actions-runner && sudo ./svc.sh start'`.
2. **Runner không còn trên GitHub**: phải đăng ký lại — lấy token ở **New self-hosted
   runner** (Linux, ARM64), rồi trên VM1:
   ```bash
   cd ~/actions-runner
   ./config.sh --url https://github.com/luongmaiquynh/DataOps-mini --token <TOKEN> \
     --name dataops-vm1 --unattended --replace
   sudo ./svc.sh start
   ```
3. **Đăng ký lại xong mà deploy vẫn không chạy**: các lần CD đang chờ có thể đã bị huỷ.
   Push một commit mới, hoặc chạy lại lần CD gần nhất trên trang Actions.

## Phòng ngừa

Đừng bấm "Remove" / "Force remove" một runner đang Offline trên GitHub khi chưa biết lý
do: nếu nó đã được đăng ký lại bằng `--replace`, dòng đó chính là runner đang dùng.

---
*Xem toàn bộ alert: [monitoring/prometheus/alerts.yml](../../monitoring/prometheus/alerts.yml)*
