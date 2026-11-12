# Kết quả Apache JMeter

Bắt đầu UTC: 2026-11-10T12:33:35.730000+00:00
Thời gian lấy mẫu: 167.37 giây; số thread đỉnh: 100.
Khoảng cùng giữ đủ 100 WebSocket thành công: 109.89 giây.

Số liệu gồm cả ramp-up và kết thúc; req/s tính trên toàn cửa sổ đo.
p50/p95 dùng nearest rank, gồm cả request lỗi. WS connect đo handshake;
WS verify chỉ kiểm tra nhận update đúng Ward/nguồn, không đo độ trễ truyền tin.

| Nhóm | Samples | Lỗi | Lỗi % | p50 ms | p95 ms | Max ms | req/s |
|---|---:|---:|---:|---:|---:|---:|---:|
| Current weather | 12000 | 0 | 0.00 | 30 | 78 | 151 | 71.70 |
| Provinces | 12000 | 0 | 0.00 | 31 | 80 | 149 | 71.70 |
| WS connect | 100 | 0 | 0.00 | 9 | 86 | 1544 | 0.60 |
| WS verify and close | 100 | 0 | 0.00 | 1 | 2 | 45 | 0.60 |
| Wards | 12000 | 0 | 0.00 | 34 | 84 | 151 | 71.70 |
| Weather history | 12000 | 0 | 0.00 | 34 | 83 | 155 | 71.70 |

Thông lượng HTTP tổng: 286.79 req/s.
Ngưỡng đề xuất: từng API có lỗi < 1% và p95 ≤ 1000 ms; đủ 100 WS mở/kiểm tra thành công; thread đỉnh ≥ 100.
Mỗi API phải đủ 12000 mẫu và có khoảng giữ đồng thời đủ WS.

Kết luận theo ngưỡng đề xuất: **ĐẠT**.
Đây là kết quả của kịch bản và môi trường đã đo, không phải sức tải tối đa.
