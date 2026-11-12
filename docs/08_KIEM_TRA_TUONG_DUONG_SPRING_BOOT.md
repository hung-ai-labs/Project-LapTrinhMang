# Kiểm tra tương đương FastAPI → Spring Boot

Ngày kiểm chứng: 12/11/2026. Baseline FastAPI: commit `f63561a`. Spring Boot: mã trong working tree sau chuyển đổi và sửa hồi quy. Các server/database kiểm thử đặt riêng trên localhost; không ghi, migrate hoặc reset Neon trong đợt kiểm tra này.

## Kết quả

| Nhóm | Kết quả kiểm chứng |
|---|---|
| FastAPI gốc | 104 test qua trong bản trích xuất Git tại thư mục tạm |
| Spring Boot | 35 test qua: REST, JWT, địa chỉ, địa danh, provider, cache, TCP/WS, collector, snapshot |
| PostgreSQL thật | Chạy lại 9 test tích hợp API; kiểm tra schema Alembic cũ, schema Java mới và nhập/cập nhật địa danh |
| Đối chiếu trực tiếp | 35 kiểm tra API/JWT/Argon2/TCP hai chiều qua trên FastAPI và Java dùng chung database thử |
| React | 21 test qua và build TypeScript/Vite thành công |
| Open-Meteo thật | Current, preview giờ tiếp theo, future 168 giờ và provider forecast Hà Nội 3 ngày đều HTTP 200 |
| 100 phiên đồng thời | 100 WS nhận bản tin, 2.000 REST request, 0 lỗi; p95 tổng hợp 286 ms trong bài smoke 3,28 giây |
| Docker | Cả hai Compose validate được; chưa build/chạy container vì Docker daemon đang tắt |

PostgreSQL cục bộ: 14.21, database tách biệt, Java 17. CI được bổ sung kiểm tra API với PostgreSQL 17. Kết quả cục bộ không thay thế kết quả CI chưa chạy.

Bài 100 phiên là **smoke ngắn**, không phải bài JMeter 120 vòng, không chứng minh tải tối đa hoặc độ ổn định nhiều giờ. Mỗi phiên giữ một WS và gọi lần lượt provinces, wards, current, history trong 5 vòng. Một producer TCP gửi 12 event trong lúc tải. Không đo tải auth/forecast, nhiều producer TCP hoặc Neon. Không dùng dữ liệu giả rồi gắn nhãn dữ liệu thật.

## Những lỗi phát hiện và đã sửa

- **Snapshot tọa độ dạng chuỗi:** Java ban đầu đọc sai kiểu chuỗi thập phân, có thể nhập sai hoặc không khởi tạo được DB. Đã chuẩn hóa bằng BigDecimal, kiểm tra phạm vi/checksum/version/mã trùng/quan hệ tỉnh–xã. PostgreSQL thực tế xác nhận xã `00004` có tọa độ `21.04000, 105.83600`.
- **Profile không có web server:** encoder mật khẩu ban đầu phụ thuộc cấu hình web, làm init/import/collector có thể thiếu bean. Đã tách cấu hình encoder dùng được cho mọi profile; profile init/import đã chạy và tự thoát thành công.
- **Trộn nguồn WebSocket:** đã lọc đồng thời Ward và nguồn provider/simulator, không phát lại duplicate.
- **Client WS chậm ảnh hưởng TCP:** chuyển sang gửi bất đồng bộ, queue tối đa 32 event/client, giữ event mới nhất, send timeout 10 giây; publish sau commit.
- **Current provider chậm mốc:** cache theo bucket của lần yêu cầu để không gọi provider liên tiếp khi thời điểm dữ liệu nguồn cũ hơn mốc 15 phút; vẫn có fallback dữ liệu cũ và cooldown khi provider lỗi.
- **Preview thiếu chia sẻ request/qua giờ:** chỉ chia sẻ request đang chạy; 2 worker, tối đa 32 request khác nhau, request sau lấy mới; đổi target nếu qua mốc giờ trong lúc tải. Hủy một caller không hủy công việc dùng chung.
- **Provider treo body:** giới hạn thời gian toàn bộ response, không chỉ header; giới hạn 256 KiB, kiểm tra mảng/đơn vị/giá trị/mốc thời gian.
- **Catalog khi mất DB:** tải cache tỉnh và xã thành một snapshot; refresh lỗi giữ bản cũ và trả `X-Data-Stale`. Không có cache thì trả 503.
- **Khác hợp đồng REST:** success chỉ có `success/data`, lỗi có `success/data/error`; query sai trả 422 `validation_error`, sai HTTP method trả 405; giữ `/openapi.json`, `/redoc` và Swagger JWT authorization.
- **Địa chỉ và tài khoản:** chuẩn hóa email/khoảng trắng; đọc được địa chỉ đã lưu khi mã địa danh bị vô hiệu hóa; kiểm tra quyền sở hữu, xóa địa chỉ, không cho body thay user. Thiếu khóa JWT vẫn giữ API nội dung công khai, login báo 503.
- **Độ chính xác thời gian:** chuẩn hóa microsecond tương đương Python/PostgreSQL để retry event không biến thành xung đột do nanosecond.
- **Collector/outbox:** batch tối đa 50 xã, chọn danh sách hoặc chủ động toàn quốc; collection và sender độc lập; giới hạn outbox, backoff khi lỗi; kiểm tra ACK đúng event ID trước khi xóa, giữ payload xung đột, hỗ trợ gửi lại sau restart.
- **Công cụ import bị thiếu:** bổ sung `import-catalog`, dry-run mặc định; apply cập nhật/khôi phục mã hiện có và vô hiệu hóa mã bỏ khỏi snapshot trong transaction, không xóa dữ liệu người dùng/quan sát. Có helper xuất SQLite outbox cũ theo chế độ chỉ đọc.

## Ma trận tính năng

| Tính năng FastAPI | Spring Boot sau sửa | Bằng chứng |
|---|---|---|
| Register/login, Argon2 | Đáp ứng | Test + tài khoản tạo bởi runtime này đăng nhập được runtime kia |
| JWT, `/me`, logout | Đáp ứng | JWT hai chiều, logout ở một bên bị thu hồi ở cả hai |
| Reload giữ phiên đăng nhập | Giữ giao thức frontend | React session tests + JWT backend thực tế; không chạy kiểm tra trình duyệt thủ công |
| Địa chỉ riêng theo user | Đáp ứng | GET/PATCH/DELETE, isolation, body giả user, mã không hợp lệ, địa chỉ mã cũ |
| Tỉnh/xã, tìm kiếm, phân trang | Đáp ứng | Test + so sánh response với FastAPI trên cùng dữ liệu |
| Xã gần nhất | Đáp ứng | Cùng xã/khoảng cách; chấp nhận sai số số thực nhỏ trong kiểm tra |
| Current theo nguồn | Đáp ứng | Simulator trên PG; provider Open-Meteo thật; cache/fallback bằng test |
| History API | Đáp ứng | Thứ tự thời gian, pagination, tách nguồn, đối chiếu hai runtime |
| Cảnh báo ngưỡng | Đáp ứng | Nhiệt ≥35°C, mưa ≥20 mm/h, gió ≥50 km/h; không gọi là AI |
| Dự báo giờ tiếp theo | Đáp ứng | Live provider + test chia sẻ/cancel/bounded queue/qua giờ |
| Future 7 ngày theo xã | Đáp ứng | Live 168 giờ, test filter thời gian/cache/nhãn nguồn |
| Dự báo thành phố | Đáp ứng | Live Hà Nội 72 giờ/3 ngày; input hỗ trợ 1–16 ngày |
| TCP NDJSON | Đáp ứng | Phân mảnh/gộp frame, invalid rồi phục hồi, duplicate/conflict, UTC, giới hạn frame/thời gian |
| WebSocket | Đáp ứng | Lọc xã/nguồn, heartbeat, reconnect, origin, unknown ward, 100 phiên nhận dữ liệu |
| Mất DB | Đáp ứng cho catalog/WS và phục hồi sau lỗi | Dừng PostgreSQL thật: health 503, catalog 200 từ cache, WS mới nhận heartbeat. Khởi động DB lại: health 200, TCP accepted |
| Import địa danh | Đáp ứng qua profile Java | Kiểm chứng thêm mã, khôi phục tên/active, vô hiệu mã cũ, giữ nguyên quan sát |
| Collector bền vững | Đáp ứng qua Java | Test batch/outbox/restart/ACK sai; helper giữ SQLite nguồn khi xuất |
| Docker và Run launcher | Đã cập nhật cấu hình | Compose validate, launcher `--check`; Docker runtime chưa kiểm chứng |

Kiểm thử lỗi provider dùng HTTP server cục bộ mô phỏng 429/5xx, response quá lớn và body treo để không lệ thuộc quota mạng. Các lệnh gọi provider thật dùng database tạm, dự báo không ghi vào observations; current có ghi quan sát vào database tạm.

## Chạy lại

Trong `source/server`:

```sh
mvn verify
# PostgreSQL dùng RIÊNG cho test; test có create/drop bảng
mvn -Dtest=ApiIntegrationTest \
  -Dweather.database-url=jdbc:postgresql://127.0.0.1:15439/junit_parity \
  -Dweather.database-user=weather \
  -Dspring.jpa.database-platform=org.hibernate.dialect.PostgreSQLDialect test
```

Ở root repository, sau khi dựng hai backend localhost cùng **database thử**, source=simulator và cùng JWT_SECRET test:

```sh
python source/verification/compare_backends.py
# Mặc định HTTP: FastAPI 18801, Java 18802; TCP: 19901/19902
java source/verification/ConcurrentSmoke.java
python -m unittest discover -s source/verification -p 'test_*.py'
```

Runner đối chiếu tạo tài khoản và quan sát để kiểm thử: chỉ dùng database riêng, không dùng Neon/dữ liệu thật. Các token/mật khẩu không được ghi ra báo cáo. Baseline FastAPI có thể trích xuất từ Git (`f63561a`) sang thư mục tạm; không phải khôi phục đè backend Java.

## Giới hạn còn lại

Chưa chạy Docker runtime, bài JMeter dài hạn hoặc browser E2E thủ công. Chưa đo nhiều producer/địa điểm và quota toàn quốc; `COLLECTOR_ALL_WARDS` là lựa chọn chủ động cần cân nhắc quota. Kiểm thử đã phát hiện và sửa các lỗi nêu trên, không phải bảo đảm phần mềm không bao giờ phát sinh lỗi.

Minh chứng đã lưu: `source/verification/evidence/compatibility-20261112.txt` và `concurrent-smoke-20261112.json`.
