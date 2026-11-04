# Thiết kế database Weather Stream

## Phạm vi

Schema có bốn bảng: `users`, `observations`, `provinces`, `wards`. User và hợp đồng JWT kế thừa từ main; danh mục địa lý và địa điểm mặc định là phần bổ sung. Các API thời tiết hiện vẫn dùng `city` theo luồng đang chạy trên main.

Mỗi model nằm trong một file trực tiếp tại `source/server/app/db/`:

```text
app/db/
├── __init__.py       # Export Base và các model, nạp đủ metadata
├── base.py           # created_at và updated_at dùng chung
├── session.py        # Kết nối/transaction database
├── user.py           # User
├── observation.py    # Observation
├── province.py       # Province
└── ward.py           # Ward
```

Base và session không tạo bảng riêng. Consumer import từ `app.db`; không dùng `app.db.models`.

## Trường dùng chung

Tất cả model kế thừa Base và có `created_at`, `updated_at` kiểu timestamp có timezone. Thời gian mặc định do database cung cấp; cập nhật qua SQLAlchemy tự thay `updated_at`. Đây không phải trigger cho mọi câu SQL viết tay.

Timestamp lưu UTC, hiển thị Asia/Ho_Chi_Minh. `observed_at` của observation là lúc số liệu khí tượng có hiệu lực, khác thời điểm server tạo row.

## User — bảng users

| Trường | Kiểu | Ràng buộc/vai trò |
|---|---|---|
| id | VARCHAR(36) | PK, chuỗi UUID do ứng dụng cấp, giữ contract main |
| name | VARCHAR(100) | Bắt buộc, tên hiển thị |
| email | VARCHAR(254) | Bắt buộc, unique; API auth chuẩn hóa email |
| password_hash | VARCHAR(255) | Bắt buộc, hash mật khẩu; không trả qua API |
| token_version | INTEGER | Bắt buộc, mặc định 0; JWT dùng để thu hồi phiên khi logout |
| address_text | VARCHAR(500) | Nullable, ghi chú địa chỉ riêng |
| default_ward_id | VARCHAR(20) | Nullable, FK tới wards.id; có index |
| created_at / updated_at | TIMESTAMPTZ | Kế thừa Base |

User có thể đăng ký khi chưa chọn xã. Nhiều user có thể dùng cùng một xã mặc định. `default_ward_id` dùng RESTRICT khi xóa ward để không làm mất địa điểm đang lưu; danh mục hết hiệu lực chuyển inactive.

API auth trả id/name/email trong data. API `/users/me/address` đọc/lưu/xóa ward mặc định và địa chỉ riêng của chính user bằng JWT. Xem thời tiết và danh mục địa lý vẫn công khai; các API và response được mô tả tại `docs/06_API.md`.

## Province — bảng provinces

| Trường | Kiểu | Ràng buộc/vai trò |
|---|---|---|
| id | VARCHAR(20) | PK, mã tỉnh dạng chuỗi để giữ số 0 đầu |
| name | VARCHAR(150) | Bắt buộc, có index |
| dataset_version | VARCHAR(64) | Bắt buộc, phiên bản snapshot |
| is_active | BOOLEAN | Bắt buộc, mặc định true khi tạo qua ORM |
| created_at / updated_at | TIMESTAMPTZ | Kế thừa Base |

Mã là định danh, tên có thể thay đổi. Không dùng tên làm khóa ngoại.

## Ward — bảng wards

| Trường | Kiểu | Ràng buộc/vai trò |
|---|---|---|
| id | VARCHAR(20) | PK, mã phường/xã/đơn vị cấp xã |
| province_id | VARCHAR(20) | Bắt buộc, FK tới provinces.id, RESTRICT |
| name | VARCHAR(150) | Bắt buộc; không unique toàn quốc |
| administrative_type | VARCHAR(32) | Nullable, chỉ điền khi nguồn xác định rõ loại đơn vị |
| latitude | NUMERIC(8,5) | Nullable, tọa độ đại diện trong [-90,90] |
| longitude | NUMERIC(8,5) | Nullable, tọa độ đại diện trong [-180,180] |
| dataset_version | VARCHAR(64) | Bắt buộc, phiên bản snapshot |
| is_active | BOOLEAN | Bắt buộc, mặc định true khi tạo qua ORM |
| created_at / updated_at | TIMESTAMPTZ | Kế thừa Base |

Tọa độ phải có cả cặp hoặc cùng NULL. Nhiều ward có thể trùng tên hoặc tọa độ đại diện; chỉ mã là unique. Index `(province_id, name)` phục vụ tìm xã theo tỉnh. Tọa độ đại diện có thể dùng để lấy thời tiết khu vực khi tích hợp provider theo ward.

## Observation — bảng observations

Giữ cấu trúc và tên class từ main để TCP/REST/WebSocket tiếp tục hoạt động:

| Trường | Kiểu | Vai trò |
|---|---|---|
| id | VARCHAR(36) | PK, UUID bản tin để chống ghi trùng khi retry |
| city | VARCHAR(64) | Thành phố của luồng thời tiết hiện tại |
| temperature | FLOAT | °C |
| humidity | FLOAT | % |
| wind_speed | FLOAT | km/h |
| rainfall | FLOAT | mm/h |
| source | VARCHAR(32) | Phân biệt provider/simulator |
| observed_at | TIMESTAMPTZ | Thời điểm số liệu có hiệu lực |
| created_at / updated_at | TIMESTAMPTZ | Kế thừa Base |

Index `(city, observed_at)` giữ nguyên. Chưa gán lịch sử cấp thành phố sang một phường/xã vì không có căn cứ địa lý tương ứng; kết nối dữ liệu thời tiết theo ward cần hợp đồng API/producer riêng.

## Quan hệ

| Quan hệ | Bội số | Khi xóa |
|---|---|---|
| Province → Ward | Một tỉnh có nhiều ward; một ward thuộc một tỉnh | RESTRICT |
| Ward → User.default_ward | Một ward có nhiều user; mỗi user có 0 hoặc 1 ward mặc định | RESTRICT |

Observation giữ luồng city độc lập. JWT dùng `users.token_version` của main; không cần thêm bảng phiên token trong phạm vi này.

## Dữ liệu toàn Việt Nam và import

Snapshot trong `source/data/administrative/` có 34 tỉnh/thành và 3.321 đơn vị cấp xã, mã tỉnh cha và tọa độ đại diện. Nguồn, commit, SHA-256 và giấy phép được lưu cùng dữ liệu; đây là một snapshot cố định, không tự cập nhật khi địa giới thay đổi.

Importer kiểm tra hash/version/counts, mã trùng, tỉnh cha, tọa độ và cặp tọa độ trước khi ghi. Nhập lại không nhân bản row. Snapshot là danh mục đầy đủ: mã không còn xuất hiện chuyển inactive, không bị xóa.

Từ source/server, dùng môi trường Python backend và database đã cấu hình:

```bash
# Chỉ đọc dữ liệu, không kết nối database:
python ../scripts/import_administrative_units.py

# Tạo schema và ghi danh mục vào database đã cấu hình:
alembic upgrade head
python ../scripts/import_administrative_units.py --apply
```

## Migration và kiểm chứng

Main giữ nguyên 0001_observations và 0002_users. PR chỉ thêm **một file** `0003_geographic_catalog.py`, gồm tạo Province/Ward, thêm địa điểm mặc định và timestamp chung. Migration không tải dữ liệu mạng, không đổi ID/tên/password_hash/token_version hay bản tin hiện có.

Tài khoản đã có giữ created_at; updated_at khởi tạo bằng created_at khi bổ sung trường. Timestamp của observations cũ được backfill theo lúc migration, không thể suy lại thời gian server từng nhận bản tin.

Downgrade bị chặn khi còn danh mục hoặc địa chỉ đã lưu cần giữ. Các kiểm thử migration/import chỉ chạy trên SQLite tạm; không tự áp dụng vào Neon. Kế hoạch kiểm thử nằm ở `.plans/plan_process/2026-11-03-db-models-import-test-plan.md`.
