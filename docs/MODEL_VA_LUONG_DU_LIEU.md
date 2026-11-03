# Model và luồng dữ liệu

## Timestamp dùng chung

Tất cả tám model kế thừa Base, nên mỗi bảng có:

- `created_at`: thời điểm tạo bản ghi. Dữ liệu cũ chưa có trường này được backfill theo thời điểm chạy migration, không thể khôi phục thời gian tạo thực tế.
- `updated_at`: thời điểm bản ghi được sửa qua SQLAlchemy. Đây là cơ chế `onupdate` của SQLAlchemy, không phải trigger cập nhật mọi câu SQL viết tay.

Hai trường mặc định lấy thời gian database. PostgreSQL lưu dưới kiểu timestamp có timezone; UI hiển thị theo giờ Việt Nam.

`WeatherObservation.observed_at` là thời điểm số liệu thời tiết có hiệu lực. Ví dụ số liệu lúc 14:00 gửi tới hệ thống lúc 14:05 thì `observed_at` là 14:00, còn `created_at` là 14:05. Sửa bản ghi lúc 14:10 sẽ đổi `updated_at`, giữ `created_at` và `observed_at`.

User/UserSession dùng timestamp kế thừa, không khai báo lại. Migration `0002` tạo schema hiện tại từ `0001`; các bảng mới có sẵn hai timestamp.

## Session trong một thao tác cụ thể

`app/db/session.py` tạo `engine`, bộ tạo `Session` và dependency `get_session`.

Ví dụ thực tế đang chạy là TCP nhận một bản tin thời tiết trong `services/ingestion.py`:

1. `async with Session() as session` mở một phiên thao tác database cho bản tin.
2. Tạo `WeatherObservation`, gọi `session.add(record)` để chuẩn bị ghi.
3. `await session.commit()` thực hiện ghi và xác nhận transaction. Dữ liệu lúc này mới được lưu thành công.
4. Nếu vi phạm khóa/ràng buộc, `await session.rollback()` hủy transaction đang lỗi. Bản tin trùng UUID có thể được nhận diện và không ghi/broadcast lần nữa.
5. Thoát context thì đóng session, trả kết nối về pool; các kết nối có thể được tái sử dụng cho bản tin/request tiếp theo.

Session quản lý truy vấn và thay đổi của một lượt làm việc, transaction và trạng thái các object ORM. Nó không phải một bảng, cũng không biểu thị người dùng đang đăng nhập.

`UserSession` là bảng riêng cho phiên đăng nhập trong bước auth về sau. Ví dụ user đăng nhập trên laptop: server sẽ tạo một token, lưu hash trong UserSession, gửi cookie về trình duyệt. Request sau gửi cookie để server tìm user và kiểm tra hạn/thu hồi. Auth/cookie này hiện chưa được triển khai chỉ vì đã có model UserSession.

## AlertRule lưu và cấu hình gì

Một hàng là một phiên bản quy tắc. Migration 0002 seed ba quy tắc demo: nóng từ 35°C, mưa từ 20 mm/h và gió từ 50 km/h.

Ví dụ cấu hình một quy tắc cảnh báo nóng:

| Trường | Giá trị ví dụ | Nghĩa |
|---|---|---|
| rule_key | heat | Tên quy tắc ổn định |
| version | 1 | Phiên bản cấu hình |
| metric | temperature | Chỉ số cần kiểm tra |
| operator | gte | Lớn hơn hoặc bằng |
| threshold | 35 | Ngưỡng nhiệt độ 35°C |
| severity | warning | Mức cảnh báo |
| cooldown_seconds | 600 | Khoảng cách tối thiểu giữa các lần gửi thông báo khi tích hợp service |
| enabled | true | Được phép áp dụng khi service đọc quy tắc |

Để thay ngưỡng từ 35 lên 37°C mà giữ lịch sử: trong cùng transaction, tắt phiên bản 1 (`enabled=false`) và tạo phiên bản 2 cùng rule_key, threshold=37, enabled=true. Không ghi đè quy tắc cũ đang được cảnh báo lịch sử tham chiếu.

**Trạng thái code hiện tại:** chưa có UI/API cấu hình quy tắc. `services/alerts.py` vẫn kiểm tra trực tiếp các hằng số 35/20/50, chưa đọc bảng AlertRule. Sửa threshold trong DB hiện chưa đổi cảnh báo API. Cooldown và enabled mới là dữ liệu cấu hình, chưa tự có tác dụng cho tới khi nối service đánh giá.

## WeatherAlert ghi nhận điều gì

Một hàng là một đợt cảnh báo tại một ward, một loại nguồn và một quy tắc. Luồng dự kiến khi nối service:

| Thời điểm | Observation | Cách xử lý đợt cảnh báo |
|---|---|---|
| 14:00 | 36°C | Tạo WeatherAlert active; ghi started_at và observation khởi phát |
| 14:05 | 37°C | Cập nhật last_observation_id/last_evaluated_at của cùng đợt; không tạo thêm đợt active |
| 14:10 | 34°C | Đổi đợt sang resolved và ghi resolved_at |

`rule_id` liên kết tới AlertRule đã dùng; `rule_snapshot` lưu cấu hình tại thời điểm tạo. `last_notified_at` dùng quyết định gửi lại thông báo theo cooldown khi có service thông báo. `created_at`/`updated_at` theo dõi lúc lưu/sửa row; `started_at`/`resolved_at` biểu thị thời gian diễn biến thời tiết.

Constraint unique chỉ cho một đợt active cho cùng ward/source/rule. Constraint không tự đánh giá thời tiết hay chuyển active thành resolved. Hiện chưa có service tạo/cập nhật WeatherAlert; cảnh báo trên API đang được tính và trả trực tiếp từ bản tin.

## Hoãn AI

Forecast chỉ chấp nhận `method=persistence_baseline` và `is_ai=false`. Schema hiện tại tập trung vào dữ liệu thời tiết, người dùng và cảnh báo; phần quản lý phiên bản AI sẽ thiết kế khi triển khai AI.
