# Kế hoạch khôi phục thảm hoạ

*Cập nhật 15/09/2026. Mọi con số dưới đây đều đo từ diễn tập thật, không phải ước lượng.*

## Mục tiêu

| Chỉ số | Cam kết | Cơ sở |
|---|---|---|
| **RPO** (mất tối đa bao nhiêu dữ liệu) | **24 giờ** | Backup chạy 2:00 sáng hàng ngày |
| **RTO** — mất database | **≈ 5 phút** | Đo được 2 giây cho phần restore; phần còn lại là thao tác người |
| **RTO** — mất một VM (còn hệ điều hành) | **≈ 1 phút** | Đo được 28 giây khi dựng lại VM3 từ trạng thái xoá sạch |
| **RTO** — mất một VM (phải cài lại OS) | **≈ 30 phút** | Cài Ubuntu trong UTM là thao tác tay, chưa tự động hoá |

RPO 24 giờ là hệ quả trực tiếp của việc backup mỗi ngày một lần. Muốn giảm xuống
1 giờ thì phải bật WAL archiving cho PostgreSQL — chưa làm.

## Tài sản cần bảo vệ

| Tài sản | Ở đâu | Được bảo vệ thế nào |
|---|---|---|
| Dữ liệu PostgreSQL | volume `postgres_data` trên VM2 | Backup hàng ngày sang VM3, kiểm chứng restore hàng tuần |
| Định nghĩa user database | cùng nơi | File `roles_*.sql.gz` đi kèm mỗi bản backup |
| Cấu hình toàn hệ thống | repo Git trên GitHub | Có bản sao ở GitHub và trên cả 3 VM |
| Secret | `group_vars/all/vault.yml` đã mã hoá | Trong repo; khoá giải mã nằm ở `~/.ssh`-level trên máy Mac |
| **Dữ liệu MinIO** | volume `minio_data` trên VM2 | **KHÔNG được backup — xem phần điểm yếu** |

## Kịch bản 1: Mất dữ liệu PostgreSQL

Dấu hiệu: alert `PostgreSQLDown`, hoặc dữ liệu sai/mất bảng.

```bash
# 1. Lấy bản backup mới nhất từ VM3
ssh dataops@192.168.64.4 'ls -t /opt/backup/postgres/backup_*.sql.gz | head -1'
scp dataops@192.168.64.4:/opt/backup/postgres/backup_<ts>.sql.gz /tmp/
scp dataops@192.168.64.4:/opt/backup/postgres/roles_<ts>.sql.gz /tmp/

# 2. Chuyển sang VM2
scp /tmp/backup_<ts>.sql.gz /tmp/roles_<ts>.sql.gz dataops@192.168.64.3:/tmp/

# 3. Dừng Airflow để không ai ghi vào lúc khôi phục
ssh dataops@192.168.64.2 'sudo systemctl stop dataops-airflow'

# 4. Khôi phục
ssh dataops@192.168.64.3
docker exec postgres_db sh -c 'psql -U $POSTGRES_USER -d postgres -c "DROP DATABASE dataops_db"'
docker exec postgres_db sh -c 'psql -U $POSTGRES_USER -d postgres -c "CREATE DATABASE dataops_db"'
zcat /tmp/roles_<ts>.sql.gz | docker exec -i postgres_db sh -c 'psql -U $POSTGRES_USER -d postgres -q'
zcat /tmp/backup_<ts>.sql.gz | docker exec -i postgres_db sh -c 'psql -U $POSTGRES_USER -d dataops_db -q -v ON_ERROR_STOP=1'

# 5. Bật lại Airflow
ssh dataops@192.168.64.2 'sudo systemctl start dataops-airflow'
```

**Thứ tự quan trọng:** restore role trước, database sau. Bản dump database chứa
lệnh gán quyền sở hữu, thiếu role là dừng ngay ở dòng đầu tiên.

**Đã diễn tập 15/09/2026:** khôi phục vào database `dr_drill` trên VM2 mất **2 giây**,
ra đúng 49 bảng, `employees` 5 dòng, `weather_hanoi` 144 dòng.

## Kịch bản 2: Mất một VM, hệ điều hành còn nguyên

```bash
cd infra/ansible
ansible-playbook site.yml --limit vm2 --ask-become-pass
```

Playbook cài lại Docker, đồng bộ code, sinh `.env` từ vault, dựng container và đặt
systemd unit. **Đã diễn tập trên VM3:** xoá sạch container, image và code, dựng lại
hết trong **28 giây**.

Dữ liệu trong named volume không bị ảnh hưởng nếu chỉ container bị xoá. Nếu volume
cũng mất thì làm tiếp Kịch bản 1.

## Kịch bản 3: Mất hoàn toàn một VM, phải cài lại OS

1. Tạo VM mới trong UTM: Ubuntu Server 22.04 ARM64, user `dataops`, bật OpenSSH.
2. Đặt IP tĩnh đúng như cũ (192.168.64.2/3/4).
3. Chép khoá SSH: `ssh-copy-id -i ~/.ssh/id_rsa dataops@<ip>`
4. Chạy `ansible-playbook site.yml --limit <vm> --ask-become-pass`
5. Nếu là VM2, làm tiếp Kịch bản 1 để khôi phục dữ liệu.

Bước 1 và 2 là thao tác tay trong giao diện UTM, chiếm phần lớn thời gian của RTO
30 phút.

## Kịch bản 4: Mất máy Mac

Đây là kịch bản tệ nhất và **hiện chưa khôi phục được hoàn toàn**. Xem phần dưới.

## Điểm yếu đã biết

| Điểm yếu | Hậu quả | Hướng xử lý |
|---|---|---|
| **MinIO không được backup** | Mất toàn bộ data lake nếu hỏng volume `minio_data` | Thêm `mc mirror` vào script backup |
| **Backup nằm cùng máy vật lý với dữ liệu gốc** | Mất máy Mac là mất cả dữ liệu lẫn backup | Đồng bộ thư mục backup ra ổ ngoài hoặc dịch vụ lưu trữ khác |
| **Khoá vault chỉ có trên máy Mac** | Mất máy là không giải mã được secret | Cất bản sao khoá trong trình quản lý mật khẩu |
| **Cài OS chưa tự động hoá** | Chiếm phần lớn RTO kịch bản 3 | Tạo sẵn một VM mẫu trong UTM để nhân bản |
| **Metadata Airflow dùng chung database với dữ liệu nghiệp vụ** | Khôi phục một phần thì kéo theo phần kia | Tách thành hai database riêng |

Danh sách này cố ý viết thẳng thay vì che giấu: một kế hoạch khôi phục chỉ đáng tin
khi nó nói rõ mình chưa bảo vệ được cái gì.

## Lịch diễn tập

| Hạng mục | Tần suất | Cách làm |
|---|---|---|
| Kiểm chứng restore tự động | Hàng tuần, 3:00 sáng Chủ nhật | `backup/restore-test.sh`, có alert nếu thất bại |
| Diễn tập khôi phục có bấm giờ | Mỗi quý | Theo Kịch bản 1, ghi lại thời gian vào tài liệu này |
| Diễn tập dựng lại VM | Mỗi quý | Theo Kịch bản 2 trên VM3 |

---
*Liên quan: [runbook](runbooks/), [README](../README.md)*
