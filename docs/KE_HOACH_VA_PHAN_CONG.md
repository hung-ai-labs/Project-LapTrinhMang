# Chức năng ưu tiên và phân công

## Mục tiêu bản nộp tối thiểu

Xem thời tiết của một số thành phố; lưu lịch sử; cập nhật nhiều client bằng socket;
cảnh báo khi vượt ngưỡng; dự báo có đánh giá; chạy được bằng Docker và giải thích được giao thức.
Phân công dưới đây là đề xuất cho **Thắng** và **Đức**, chưa phải GitHub Issue có assignee.
Chưa có MSSV, họ tên đầy đủ hoặc GitHub username nên để bổ sung, không tự điền.

## Base hiện có

- [x] FastAPI REST API, health check có truy vấn database.
- [x] PostgreSQL + SQLAlchemy async + Alembic; cấu hình thay URL sang Neon.
- [x] TCP NDJSON, validation, ACK, UUID chống trùng khi retry, giới hạn frame và timeout.
- [x] Publisher dữ liệu mô phỏng, retry khi mất kết nối.
- [x] WebSocket theo thành phố, heartbeat, giới hạn hàng đợi; React tự reconnect và tải bù REST.
- [x] Dashboard, lịch sử, cảnh báo theo ngưỡng demo; dự báo persistence baseline.
- [x] Docker Compose, kiểm thử backend và CI build frontend/stack.
- [ ] Dữ liệu thời tiết thật và mô hình AI đã huấn luyện/đánh giá: **chưa có**.

## Thứ tự nên làm

| Ưu tiên | Chức năng | Thắng phụ trách | Đức phụ trách | Tiêu chí hoàn thành |
|---|---|---|---|---|
| P0 · bước 1 | Chạy và hiểu base | Đọc TCP ingestion, ORM, migration; chạy publisher | Chạy React, quan sát WS trong DevTools | Cả hai tự chạy Docker demo; giải thích được TCP khác WebSocket |
| P0 · bước 2 | Dữ liệu thật | Viết adapter Open-Meteo hoặc provider đã chọn; timeout, retry, chuẩn hóa đơn vị, timestamp UTC | Hiện nguồn, giờ cập nhật, trạng thái dữ liệu cũ/lỗi | Có dữ liệu thật vào DB và WS; lỗi provider không làm server chết; không giả dữ liệu thật |
| P0 · bước 3 | Xem hiện tại và lịch sử | API khoảng thời gian, phân trang, index; unique provider/city/time | Biểu đồ nhiệt độ/độ ẩm/mưa; chọn thành phố, trạng thái trống/loading/lỗi | Đổi thành phố không lẫn dữ liệu; REST và realtime nhất quán |
| P0 · bước 4 | Streaming ổn định | Quản lý client TCP, xác thực producer, đo số kết nối, kiểm tra out-of-order | Reconnect, báo dữ liệu cũ, tải bù lịch sử; kiểm tra nhiều tab | Demo ít nhất 3 client, ngắt và nối lại producer/WS, không trùng bản ghi |
| P1 · bước 5 | Cảnh báo | Bảng alert, rule cấu hình, cooldown/chống lặp, lưu lịch sử | Banner/toast, danh sách và bộ lọc mức độ | Mô phỏng vượt ngưỡng tạo đúng cảnh báo; không spam khi cập nhật liên tục |
| P1 · bước 6 | AI dự báo | Dataset lịch sử, pipeline train/inference, version model, API forecast | Hiện forecast, thời điểm dự báo, phương pháp, sai số và biểu đồ so sánh | Có model và báo cáo MAE/RMSE so với persistence trên tập test theo thời gian |
| P1 · bước 7 | Hoàn thiện | Kiểm thử socket, migration, Neon; logs lỗi | Responsive, accessibility, kiểm thử thao tác chính | Máy khác chạy theo README; không cần chỉnh source |
| P2 · sau MVP | Tài khoản/yêu thích/thông báo | Auth, quyền, API favorites, lưu đăng ký | Đăng nhập, thành phố yêu thích, cài đặt | Chỉ làm sau khi P0/P1 ổn định |

## Gợi ý triển khai AI

Thắng bắt đầu bằng dự báo nhiệt độ 1 giờ tới từ chuỗi quan sát; thử Linear Regression
và Random Forest trước khi cân nhắc LSTM. Chia train/validation/test theo thời gian,
không random split làm rò rỉ tương lai; không train trên dữ liệu simulator để báo cáo độ chính xác.
Giữ baseline persistence trong API để so sánh MAE/RMSE. Lưu model ngoài Git hoặc dùng artifact phù hợp;
chỉ công bố AI khi có pipeline suy luận thực và kết quả kiểm định.

Đức thiết kế phần dự báo để hiển thị rõ nguồn dự báo, horizon, thời điểm cập nhật,
trường hợp model chưa sẵn sàng và fallback. Nếu thêm LLM, chỉ dùng để diễn giải kết quả có sẵn,
không để LLM tự bịa số liệu dự báo. Ngưỡng cảnh báo demo không thay thế cảnh báo khí tượng chính thức.

## Các đầu việc cùng làm

1. Thắng chốt schema và ví dụ JSON với Đức trước khi đổi API; cập nhật README và TypeScript type cùng PR.
2. Mỗi người tự commit phần mình, dùng nhánh `feat/<ten-chuc-nang>` và review chéo trước khi merge.
3. Cả hai cùng kết nối Neon bằng `.env` riêng và chạy migration; không chia sẻ mật khẩu trong Git/ảnh demo.
4. Cùng chuẩn bị sơ đồ, báo cáo và demo: producer → TCP → DB → WS → nhiều trình duyệt;
   thử dữ liệu sai, TCP chia/gộp gói, ACK bị mất, reconnect, cảnh báo và forecast.
5. Ghi số client, tần suất bản tin, độ trễ p50/p95, thời gian reconnect từ phép đo thực.
   Chưa đo thì không điền kết quả vào README.

## Điều kiện trước khi nộp

- [ ] Bổ sung họ tên/MSSV/email và chủ đề đăng ký trong README.
- [ ] Hoàn tất P0/P1, dữ liệu thật và AI có đánh giá.
- [ ] Có ảnh thật trong `statics/`, không dùng ảnh placeholder làm minh chứng.
- [ ] Chạy CI thành công và clone/chạy thử trên máy sạch.
- [ ] Mỗi thành viên có commit của mình và giải thích được phần phụ trách.
