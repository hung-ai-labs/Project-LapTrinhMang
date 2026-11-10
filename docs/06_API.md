# API Weather Stream

## Docs tương tác

- Swagger: `http://localhost:8000/docs`.
- ReDoc: `http://localhost:8000/redoc`.
- OpenAPI JSON: `http://localhost:8000/openapi.json`.

Docs công khai, nhóm theo Health, Province, Ward, Observation, Forecast, Auth và User. OpenAPI mô tả schema thật của request, response và lỗi. Base path của REST là `/api/v1`.

## Response chung

API thành công trả `{"success":true,"data":...}`. API danh sách đặt metadata pagination trong data. Ví dụ với snapshot đi kèm, `GET /api/v1/provinces?q=Hà&page=1&page_size=1`:

```json
{
  "success": true,
  "data": {
    "count": 2,
    "next": "http://localhost:8000/api/v1/provinces?q=H%C3%A0&page=2&page_size=1",
    "previous": null,
    "results": [{"id": "01", "name": "Hà Nội"}]
  }
}
```

Thứ tự query parameter có thể khác ví dụ. Quy tắc phân trang:

- page bắt đầu từ 1, mặc định 1; page_size mặc định 25, trong khoảng 1–100.
- count là tổng bản ghi sau khi lọc, results là dữ liệu của trang hiện tại.
- next/previous là URL đầy đủ, giữ nguyên bộ lọc; null nếu không có trang tương ứng.
- Danh sách rỗng ở trang 1 trả count=0, results=[], next/previous=null.
- Trang vượt phạm vi trả HTTP 404; tham số sai trả HTTP 422.
- History dùng bộ lọc city và nguồn WEATHER_SOURCE; frontend yêu cầu page_size=60.

Thất bại giữ HTTP status phù hợp:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "http_404",
    "message": "Trang không tồn tại.",
    "details": null
  }
}
```

Lỗi validation có code=validation_error và details gồm loc/message/type. Lỗi không echo password/token đầu vào hoặc trả chi tiết nội bộ máy chủ. HTTP 401 giữ WWW-Authenticate: Bearer. Logout thành công trả HTTP 200 với success=true/data=null.

OpenAPI JSON giữ chuẩn OpenAPI để Swagger/ReDoc hoạt động. WebSocket, TCP ACK và OPTIONS preflight dùng giao thức riêng, không bọc theo response REST.

## API xem dữ liệu công khai

Không cần Authorization, không cần đăng nhập và không cần cấu hình JWT để xem các API này:

| Method | Endpoint | Nội dung/tham số |
|---|---|---|
| GET | `/health` | Kiểm tra DB; lỗi DB trả 503 |
| GET | `/weather/{city}/current` | Observation mới nhất và cảnh báo |
| GET | `/weather/{city}/history` | History phân trang; page/page_size |
| GET | `/weather/{city}/forecast` | Persistence baseline, is_ai=false |
| GET | `/provinces` | Tỉnh/thành active; q/page/page_size |
| GET | `/provinces/{province_id}` | Chi tiết tỉnh/thành active |
| GET | `/wards` | Phường/xã và tỉnh active; province_id/q/page/page_size |
| GET | `/wards/{ward_id}` | Chi tiết phường/xã active |
| POST | `/geography/nearest-ward` | Tọa độ → ward gần nhất |

City hiện là hanoi/danang/hcm. Chưa có thời tiết cho nguồn đã chọn trả 404, không yêu cầu đăng nhập. Danh mục cần import trước; mã giữ dạng chuỗi như `01`, `00004`.

```bash
curl 'http://localhost:8000/api/v1/provinces?page=1&page_size=25'
curl 'http://localhost:8000/api/v1/wards?province_id=01&page=1&page_size=25'
curl 'http://localhost:8000/api/v1/geography/nearest-ward' \
  -H 'Content-Type: application/json' \
  -d '{"latitude":21.04,"longitude":105.836}'
```

Nearest trả data gồm ward, province, distance_km và match_type=nearest. Haversine chọn tọa độ đại diện gần nhất, không xác định ranh giới chính xác. API không lưu GPS hay tự sửa tài khoản. Không có ward có tọa độ trả 404.

## Tài khoản là tùy chọn

Tài khoản phục vụ thông tin cá nhân và lưu địa chỉ mặc định. Dashboard, thời tiết, địa danh và docs đều xem được khi là khách.

| Method | Endpoint | Quyền | Kết quả trong data |
|---|---|---|---|
| POST | `/auth/register` | Công khai | TokenOut, HTTP 201; email trùng 409 |
| POST | `/auth/login` | Công khai | TokenOut; sai thông tin 401 |
| GET | `/auth/me` | JWT | id/name/email của chính user |
| POST | `/auth/logout` | JWT | null; thu hồi toàn bộ JWT hiện có của user |

Register nhận name/email/password; login nhận email/password. Password dài 8–128 ký tự. TokenOut gồm access_token, token_type=bearer, expires_in và user. Lấy token tại `response.data.access_token`. Các endpoint cấp token cần JWT_SECRET hợp lệ; API công khai không bị ảnh hưởng nếu chưa cấu hình key.

Swagger có nút Authorize để nhập access token khi thử API cá nhân. Client lưu token trong sessionStorage theo tab, reload giữ phiên trong cùng tab; đóng tab/hết hạn cần đăng nhập lại; chưa có refresh-token API.

## Địa chỉ riêng của user

| Method | Endpoint | Mục đích |
|---|---|---|
| GET | `/users/me/address` | Đọc địa chỉ kèm ward/province |
| PATCH | `/users/me/address` | Lưu ward mặc định và ghi chú địa chỉ |
| DELETE | `/users/me/address` | Bỏ địa chỉ/ward mặc định |

Ba endpoint dùng Bearer JWT để xác định người cần lưu. Không cho đọc/sửa địa chỉ người khác và không nhận user_id từ client. Chưa lưu địa chỉ thì data chứa address_text/ward/province đều null.

PATCH nhận ward_id bắt buộc và address_text tùy chọn, tối đa 500 ký tự, được trim. Ward hoặc tỉnh không active/không tồn tại trả 404 và giữ địa chỉ cũ. GET vẫn đọc được địa điểm đã lưu nếu danh mục sau đó chuyển inactive.

```bash
curl -X PATCH 'http://localhost:8000/api/v1/users/me/address' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"ward_id":"00004","address_text":"Địa chỉ riêng tùy chọn"}'
```

Response data gồm address_text, ward và province. Xóa địa chỉ không xóa danh mục hoặc thời tiết chung. Logout làm token cũ mất quyền đọc/sửa địa chỉ; dữ liệu của các tài khoản được tách riêng.

## WebSocket

`/api/v1/ws/weather/{city}` công khai và không cần token. Event weather.update/heartbeat giữ giao thức trong README và không chứa email/địa chỉ riêng. WebSocket không được liệt kê như HTTP operation trong OpenAPI.

## Dự báo tương lai Open-Meteo

`GET /api/v1/weather/{city}/provider-forecast?days=7` — công khai, `days` từ 1 đến 16.
Trả `success/data` gồm `source=open-meteo`, `is_project_ai=false`, `retrieved_at`, `timezone`,
`hourly` và `daily`. HTTP 502 nếu provider timeout, lỗi hoặc dữ liệu không hợp lệ; không trả số liệu giả.
Cache trong RAM 15 phút theo city/days, các request cùng lúc dùng lại kết quả sau khi fetch thành công.

- Hourly: `time` UTC, `temperature` °C, `humidity` %, `wind_speed` km/h,
  `precipitation` mm tích lũy trong giờ trước mốc hiển thị, `rain_probability` %.
- Daily: `date` theo giờ Việt Nam, nhiệt độ min/max, tổng mưa mm/ngày,
  xác suất mưa cao nhất và gió cao nhất. Giá trị thiếu giữ null, UI hiện “—”.
- `retrieved_at` là thời điểm lấy dữ liệu, không phải thời điểm model được phát hành.
- Dự báo provider được phục vụ riêng; không ghi vào observations hoặc thay thế baseline tại `/forecast`.

Trang `/forecast?city=hanoi` có bộ chọn thành phố, 3/7/16 ngày, thẻ từng ngày và bảng theo giờ.
Nguồn và đơn vị theo [tài liệu Open-Meteo](https://open-meteo.com/en/docs).
