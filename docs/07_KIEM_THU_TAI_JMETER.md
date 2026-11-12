# Báo cáo kiểm thử tải Apache JMeter — 10/11/2026

## Cập nhật: lượt chạy lại lúc 22:34

Đã chạy lại đầy đủ trên cùng nhánh, không sửa mã ứng dụng. **ĐẠT** ngưỡng đề xuất.
Lượt đo bắt đầu `2026-11-10T15:34:26.488Z` (22:34:26 giờ Việt Nam), kéo dài **184,89 giây**.
Giữ cấu hình 100 user, ramp-up 30 giây, 120 vòng/user và nghỉ 1 giây/vòng; database giữ lại
từ lần trước, có **354 observations** lúc bắt đầu, publisher tiếp tục thêm 1 bản tin/giây.

| API | Request | Lỗi | p50 | p95 | Max |
|---|---:|---:|---:|---:|---:|
| Provinces | 12.000 | 0 | 71 ms | 144 ms | 290 ms |
| Wards | 12.000 | 0 | 75 ms | 148 ms | 293 ms |
| Current weather | 12.000 | 0 | 70 ms | 142 ms | 285 ms |
| Weather history | 12.000 | 0 | 75 ms | 148 ms | 295 ms |

Tổng **48.000 HTTP, 0 lỗi, 259,61 request/giây**. Đủ 100 WS mở/kiểm tra thành công,
cùng giữ đủ kết nối trong **129,23 giây**; WS handshake p95 **1.026 ms**, max **2.523 ms**.
Ngưỡng p95 ≤1.000 ms đang áp dụng cho API HTTP; WS chỉ kiểm tra mở thành công và nhận update đúng.
Thông lượng thấp hơn lượt đầu và thời gian phản hồi cao hơn; chưa thể quy nguyên nhân
cho ứng dụng vì số liệu nền/tài nguyên máy chưa được kiểm soát đủ và dataset đã tăng.

- [Summary lượt mới](../source/load-tests/evidence/20261110-223414-670-u100/summary.md).
- [Cấu hình](../source/load-tests/evidence/20261110-223414-670-u100/run.json),
  [môi trường và SHA-256](../source/load-tests/evidence/20261110-223414-670-u100/environment.json),
  [48.200 mẫu gốc nén gzip](../source/load-tests/evidence/20261110-223414-670-u100/samples.jtl.gz).
- HTML local: `source/load-tests/results/20261110-223414-670-u100/html/index.html`.

Đã dừng stack kiểm thử sau lượt chạy, giữ volume dữ liệu. Những phần bên dưới mô tả lượt đầu lúc 19:33;
các giới hạn phạm vi kiểm thử vẫn áp dụng cho cả hai lượt. Không chạy lại unit test backend ở lượt này.

## Kết luận

**Đạt ngưỡng baseline đề xuất cho kịch bản 100 người dùng đã đo.** 48.000 request HTTP
không có lỗi; p95 từng API 78–84 ms. 100 kết nối WebSocket mở thành công, nhận bản tin đúng
Ward/nguồn simulator, không có đóng bất thường được phát hiện. Chưa cần sửa hiệu năng ứng dụng
chỉ để đáp ứng lượt đo này; chưa xác định sức tải tối đa hoặc độ ổn định khi chạy dài.

Đây là một lượt đo trên máy local với lịch sử nhỏ, cùng một Ward. Không suy rộng thành cam kết
cho Neon, môi trường production, nhiều Ward, dữ liệu lịch sử lớn, auth hoặc forecast Open-Meteo.

## Môi trường và kịch bản

- Nhánh: `test/jmeter-load-test-100-users`; mã ứng dụng tại commit
  `eb1b136b4a429445c14382b326320981a1795fba`, không sửa mã backend/frontend khi đo.
- Thời gian bắt đầu: **19:33:35 ngày 10/11/2026, Asia/Ho_Chi_Minh**
  (`2026-11-10T12:33:35.730Z`); cửa sổ lấy mẫu 167,37 giây.
- Windows, Intel Core i7-13650HX, 20 logical CPU, RAM vật lý khoảng 23,73 GiB.
  Docker Engine 29.9.2 được cấp 20 CPU và khoảng 11,54 GiB RAM.
- Apache JMeter 5.6.3, Java 17; JMeter và Docker trên cùng máy. Có collector của stack
  `weather-stream` chạy nền; không cô lập toàn bộ tài nguyên máy.
- Nginx → FastAPI **một worker** → PostgreSQL 17 local. Compose/volume riêng, không dùng Neon.
- Danh mục 34 tỉnh/3.321 Ward; **151 observations** ở thời điểm bắt đầu. Ward `00004`, tỉnh `01`.
  Dữ liệu thời tiết mô phỏng; publisher TCP thêm 1 bản tin/giây trong lúc đo.
- Ramp-up 30 giây, 100 thread, mỗi user 120 vòng, nghỉ 1 giây mỗi vòng. Một WS/user giữ suốt phiên.
  Mỗi vòng đọc provinces, wards, current, history (page_size=60) tuần tự.
- Kiểm tra HTTP 200, success=true, danh mục không rỗng, current/history đúng Ward/nguồn;
  kiểm tra WS nhận ít nhất một update đúng Ward/nguồn, không message sai/đóng bất thường.

## Số đo

| API | Request | Lỗi | p50 | p95 | Max |
|---|---:|---:|---:|---:|---:|
| Provinces | 12.000 | 0 | 31 ms | 80 ms | 149 ms |
| Wards | 12.000 | 0 | 34 ms | 84 ms | 151 ms |
| Current weather | 12.000 | 0 | 30 ms | 78 ms | 151 ms |
| Weather history | 12.000 | 0 | 34 ms | 83 ms | 155 ms |

- Tổng HTTP: **286,79 request/giây**, tính trên toàn cửa sổ gồm ramp-up và kết thúc.
- Số user đỉnh: **100**. Khoảng cùng giữ đủ 100 WS thành công: **109,89 giây**.
- WS handshake: 100/100 thành công, p50 9 ms, p95 86 ms, max 1.544 ms.
- WS kết thúc: 100/100 kiểm tra thành công. Số update từng user nằm trong `environment.json`.
- p50/p95 dùng nearest rank; số liệu HTTP bao gồm tất cả mẫu, không loại warm-up hay request chậm.
- Một snapshot Docker lúc đo: server CPU 96,43%, RAM 75,25 MiB; PostgreSQL CPU 33,76%, RAM
  49,85 MiB; Nginx CPU 30,34%, RAM 26,47 MiB. CPU theo quy ước Docker (100% tương ứng một CPU),
  **không phải giá trị đỉnh/trung bình của cả lượt đo** và chưa đủ để xác định điểm nghẽn.

Ngưỡng đề xuất trước khi đo: từng API lỗi <1%, p95 ≤1.000 ms; đủ mẫu mỗi API; đủ 100 WS
mở/kiểm tra thành công và có khoảng cùng giữ đủ socket. Đây chưa phải SLA đã được nhóm phê duyệt.

## Bằng chứng và chạy lại

- [Hướng dẫn chuẩn bị/chạy](../source/load-tests/README.md).
- [Summary sinh từ mẫu gốc](../source/load-tests/evidence/20261110-193324-600-u100/summary.md).
- [Cấu hình lượt đo](../source/load-tests/evidence/20261110-193324-600-u100/run.json).
- [Môi trường, SHA-256 mẫu gốc và kết quả WS từng user](../source/load-tests/evidence/20261110-193324-600-u100/environment.json).
- [48.200 sample JMeter gốc nén gzip](../source/load-tests/evidence/20261110-193324-600-u100/samples.jtl.gz)
  gồm 48.000 HTTP + 100 WS connect + 100 WS verify/close.

Tính lại summary từ dữ liệu đã lưu, không cần chạy server:

```powershell
python -X utf8 source/load-tests/summarize.py source/load-tests/evidence/20261110-193324-600-u100/samples.jtl.gz --users 100 --loops 120
```

HTML dashboard và JTL chưa nén của lượt chạy nằm trong
`source/load-tests/results/20261110-193324-600-u100/` trên máy đo, được bỏ qua bởi Git.
Muốn dựng lại HTML trên máy khác, giải nén gzip rồi dùng JMeter `-g <samples.jtl> -o <thu-muc-moi>`.

## Kiểm tra bổ sung và giới hạn

- Smoke 2 user/3 vòng thành công trước lượt chính thức.
- Bộ tổng hợp đã được kiểm tra với lượt thành công, lượt WS lỗi và lượt thiếu sample;
  hai trường hợp sau trả exit code 1. Ruff cho mã đo tải: pass; `git diff --check`: pass.
- Backend `ruff check .`: pass. Backend `pytest -q`: **86 pass, 4 fail** trên môi trường
  Windows/Python 3.14 hiện tại, trong mã có sẵn trước thay đổi này: 3 lỗi kiểm tra/import
  snapshot do checkout CRLF không khớp SHA-256, 1 lỗi `test_concurrency_limit_and_bounded_queue`
  (maximum=1, expected=2). Không sửa backend hoặc các test này trong nhánh kiểm thử tải.
- Không đo thời gian render React, độ trễ truyền tin end-to-end, mất từng event, reconnect,
  auth, forecast, nhiều producer, soak test hoặc tải phân tán. Kiểm tra WS chỉ đảm bảo nhận
  ít nhất một update/phiên và các message nhận được có đúng Ward/nguồn.

Trước khi kết luận cho triển khai thật: lặp lại nhiều lượt với dataset lớn/đa Ward và máy phát
tải riêng, thêm soak/reconnect, đo độ trễ TCP ACK và WS end-to-end, chạy bài forecast với provider
giả lập có kiểm soát. Khi tối ưu, so sánh cùng dataset/tài nguyên/cấu hình và giữ một worker
cho đến khi TCP listener/hub được tách ra kiến trúc pub/sub phù hợp.
