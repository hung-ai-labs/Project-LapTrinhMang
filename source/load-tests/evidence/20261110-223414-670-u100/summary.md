# Kết quả Apache JMeter

Bắt đầu UTC: 2026-11-10T15:34:26.488000+00:00
Thời gian lấy mẫu: 184.89 giây; số thread đỉnh: 100.
Khoảng cùng giữ đủ 100 WebSocket thành công: 129.23 giây.

Số liệu gồm cả ramp-up và kết thúc; req/s tính trên toàn cửa sổ đo.
p50/p95 dùng nearest rank, gồm cả request lỗi. WS connect đo handshake;
WS verify chỉ kiểm tra nhận update đúng Ward/nguồn, không đo độ trễ truyền tin.

| Nhóm | Samples | Lỗi | Lỗi % | p50 ms | p95 ms | Max ms | req/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| Current weather | 12000 | 0 | 0.00 | 70 | 142 | 285 | 64.90 |
| Provinces | 12000 | 0 | 0.00 | 71 | 144 | 290 | 64.90 |
| WS connect | 100 | 0 | 0.00 | 20 | 1026 | 2523 | 0.54 |
| WS verify and close | 100 | 0 | 0.00 | 1 | 2 | 70 | 0.54 |
| Wards | 12000 | 0 | 0.00 | 75 | 148 | 293 | 64.90 |
| Weather history | 12000 | 0 | 0.00 | 75 | 148 | 295 | 64.90 |

Thông lượng HTTP tổng: 259.61 req/s.
Ngưỡng đề xuất: từng API có lỗi < 1% và p95 ≤ 1000 ms; đủ 100 WS mở/kiểm tra thành công; thread đỉnh ≥ 100.
Mỗi API phải đủ 12000 mẫu và có khoảng giữ đồng thời đủ WS.

Kết luận theo ngưỡng đề xuất: **ĐẠT**.
Đây là kết quả của kịch bản và môi trường đã đo, không phải sức tải tối đa.
