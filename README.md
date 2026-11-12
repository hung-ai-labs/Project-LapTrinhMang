# Weather Stream — Đồ án Lập trình mạng

Hệ thống xem thời tiết, streaming dữ liệu, cảnh báo và nền tảng tích hợp AI dự báo.
Base theo [starter của thầy](https://github.com/hungdn1701/jnp-project-starter/tree/main):
giữ `source/client`, `source/server`, `statics` và nguyên bản `INSTRUCTION.md`.

## Thông tin nhóm

| Thành viên | MSSV / Email | Phần phụ trách đề xuất |
|---|---|---|
| Thắng — bổ sung họ tên đầy đủ | Chưa cung cấp | Backend, TCP socket, data, PostgreSQL/Neon, AI |
| Đức — bổ sung họ tên đầy đủ | Chưa cung cấp | React, WebSocket client, dashboard, biểu đồ/cảnh báo |

Tên nhóm và chủ đề đăng ký chính thức: **cần bổ sung**.
Chi tiết chức năng cần làm trước và tiêu chí hoàn thành: [Kế hoạch và phân công](docs/KE_HOACH_VA_PHAN_CONG.md).

## Tài liệu phân tích và thiết kế

- [Phân tích nghiệp vụ BA: phạm vi, yêu cầu, use case, quy tắc và nghiệm thu](docs/01_PHAN_TICH_NGHIEP_VU.md).
- [Bộ UML: 9 sơ đồ, nguồn PlantUML và ảnh PNG/SVG](docs/02_THIET_KE_UML.md).
- [Ý tưởng tính năng và bản đồ màn hình](docs/03_Y_TUONG_TINH_NANG_VA_MAN_HINH.md).
- [Prompt Figma cho giao diện desktop/mobile](docs/04_PROMPT_FIGMA.md).

Đây là thiết kế MVP đề xuất để review trước khi phát triển tiếp; các chức năng/bảng mới trong thiết kế chưa được triển khai.

## Mô tả hệ thống

```mermaid
flowchart LR
    P[Python publisher mô phỏng] -->|TCP NDJSON + ACK :9000| T[FastAPI TCP listener]
    T --> V[Validation + UUID chống trùng]
    V --> D[(PostgreSQL local / Neon)]
    V --> H[WebSocket hub theo thành phố]
    H -->|WS / WSS| R[React dashboard]
    R -->|HTTP REST: hiện tại / dự báo| A[FastAPI API :8000]
    A --> D
```

Publisher gửi dữ liệu liên tục qua **TCP socket thuần**; server kiểm tra và lưu trước khi ACK,
sau đó broadcast **WebSocket** tới các client đang theo dõi thành phố tương ứng.
HTTP dùng để truy vấn hiện tại và khôi phục dữ liệu khi reconnect. WebSocket chạy trên TCP,
nhưng có handshake và framing riêng; trình duyệt không kết nối trực tiếp raw TCP.

Base có dữ liệu **mô phỏng**, chưa kết nối API khí tượng thật. Dự báo hiện tại là
**persistence baseline** (giữ nguyên nhiệt độ quan sát mới nhất cho 1 giờ kế tiếp), trả `is_ai: false`.
Đây là điểm nối để bổ sung AI, chưa phải model AI đã huấn luyện.

## Công nghệ

| Thành phần | Công nghệ |
|---|---|
| Server | Python 3.12+, FastAPI, Uvicorn, asyncio TCP sockets |
| Client | React 19, TypeScript, Vite 7, native WebSocket |
| Database | PostgreSQL 17 / Neon, SQLAlchemy 2 async, Psycopg 3, Alembic |
| Triển khai | Docker Compose, Nginx proxy REST/WebSocket |
| Kiểm tra | Pytest, Ruff, TypeScript build, GitHub Actions |

## Chạy nhanh bằng Docker

Cần Docker Engine/Desktop có Compose, Git. Chạy lệnh ở root repository:

```bash
cp .env.example .env
docker compose --profile demo up --build -d --wait
```

- Dashboard: http://localhost:8080
- Swagger: http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health
- TCP ingestion: `127.0.0.1:9000`; PostgreSQL local: `127.0.0.1:5433`.
- Profile `demo` bật simulator, mỗi 3 giây một bản tin, luân phiên 3 thành phố.
  Đợi tối đa khoảng 9 giây để mỗi thành phố có dữ liệu.
- Server tự chạy `alembic upgrade head` trước khi khởi động. Volume `weather_data` giữ dữ liệu.

```bash
docker compose --profile demo logs -f server simulator
# Dừng, giữ database:
docker compose --profile demo down
```

Muốn tự chạy publisher trên máy host:

```bash
docker compose up --build -d --wait
python3 source/scripts/publish_weather.py --interval 3
# Hoặc gửi đúng 6 bản tin:
python3 source/scripts/publish_weather.py --count 6 --interval 1
```

Nếu cổng bị chiếm, đổi `POSTGRES_PORT`, `API_PORT`, `WEB_PORT`, `TCP_PORT` trong `.env`
rồi chạy lại. Khi đổi `WEB_PORT`, cập nhật `CORS_ORIGINS` để cho phép đúng origin của dashboard;
đổi TCP port thì truyền `--port` tương ứng cho publisher host. URL và ví dụ bên dưới dùng cổng mặc định.

Không chạy đồng thời simulator Docker và publisher host nếu chỉ muốn một nguồn demo.
TCP port chỉ publish trên localhost cho bản base, chưa có xác thực/TLS ở raw TCP.

## Chạy development không build Docker app

Cần Python 3.12+ và Node.js 22.12+. Có thể dùng PostgreSQL Docker hoặc Neon.

Terminal 1, PostgreSQL local:

```bash
docker compose up -d db
```

Terminal 2:

```bash
cd source/server
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Terminal 3:

```bash
cd source/client
npm ci
npm run dev
```

Terminal 4, từ root:

```bash
python3 source/scripts/publish_weather.py
```

Mở http://localhost:5173. Vite và Nginx đều proxy `/api` bao gồm WebSocket;
frontend dùng cùng origin nên không cần lưu URL backend trong mã nguồn.

## Dùng PostgreSQL trên Neon

Tạo database trong Neon Console, sao chép connection string của database cần dùng.
Không có credentials Neon được đặt trong repository.

- Với Docker: thay `DATABASE_URL` trong `.env` ở root.
- Với development: thay trong `source/server/.env`.
- Đổi prefix thành `postgresql+psycopg://`, giữ hostname, database, user/password đã URL-encode
  và các tham số bảo mật Neon cung cấp, gồm `sslmode=require`.

```dotenv
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@YOUR-ENDPOINT.neon.tech/DBNAME?sslmode=require
```

Development chạy `alembic upgrade head` từ `source/server`. Docker tự migrate khi server khởi động.
Compose vẫn khởi động DB local do dependency, nhưng khi đặt URL Neon thì ứng dụng ghi vào Neon.
Có thể dùng URL pooled cho runtime; khi migration DDL gặp giới hạn pooler, dùng URL direct
cùng database để chạy `alembic upgrade head`. Không commit `.env` và không đưa URL vào log/ảnh.

Chức năng lịch sử quan sát đã được gỡ khỏi giao diện; API lịch sử vẫn được giữ. Backend vẫn lưu quan sát
để lấy thời tiết hiện tại và chống trùng bản tin TCP; thay đổi này không xóa dữ liệu trong DB.

## Giao tiếp và hợp đồng dữ liệu

### Model và danh mục tỉnh/phường xã

Backend dùng một file cho mỗi model trong `source/server/app/db/`, export qua `app.db`:
`User`, `Observation`, `Province`, `Ward`. Base cung cấp `created_at` và `updated_at` chung;
User giữ các trường JWT của main, có thêm địa chỉ và ward mặc định nullable.

Snapshot đi kèm có 34 tỉnh/thành và 3.321 đơn vị cấp xã. Từ `source/server`, dùng môi trường
Python backend và database đã cấu hình:

```bash
alembic upgrade head
python ../scripts/import_administrative_units.py          # Chỉ kiểm tra, không ghi DB
python ../scripts/import_administrative_units.py --apply  # Nhập toàn bộ danh mục
```

PR bổ sung một migration `0003_geographic_catalog.py` sau hai migration của main.
Xem [thiết kế database](docs/05_THIET_KE_DATABASE.md),
[snapshot và giấy phép](source/data/administrative/README.md),
[kế hoạch kiểm thử](.plans/plan_process/2026-11-03-db-models-import-test-plan.md).

### REST / WebSocket

REST API dùng response `{success, data}`; danh sách nằm trong
`data.count/next/previous/results`, nhận `page` (mặc định 1) và `page_size`
(mặc định 25, tối đa 100). Các liên kết trang là URL đầy đủ và giữ bộ lọc.
Chi tiết request/response, lỗi và quyền truy cập: [API docs](docs/06_API.md).
Swagger `/docs`, ReDoc `/redoc` và OpenAPI `/openapi.json` công khai, nhóm API theo model/chức năng.

Xem thời tiết, tỉnh/xã và tìm xã gần nhất không cần đăng nhập. Tài khoản chỉ dùng
cho thông tin cá nhân và địa chỉ mặc định; API địa chỉ riêng dùng JWT của chính user.

| Endpoint | Giao thức | Kết quả |
|---|---|---|
| `/api/v1/health` | HTTP GET | Kiểm tra DB, trả 503 khi không kết nối được |
| `/api/v1/wards/{ward_id}/weather/history?page=1&page_size=60` | HTTP GET | Lịch sử quan sát phân trang, mới nhất trước |
| `/api/v1/wards/{ward_id}/weather/current` | HTTP GET | Quan sát mới nhất + cảnh báo; 404 nếu chưa có |
| `/api/v1/wards/{ward_id}/weather/forecast` | HTTP GET | Baseline 1 giờ; `is_ai: false` |
| `/api/v1/wards/{ward_id}/weather/future` | HTTP GET | Open-Meteo 7 ngày theo giờ; 168 mốc; không lưu DB |
| `/api/v1/ws/wards/{ward_id}/weather` | WebSocket | `weather.update` và `heartbeat` mỗi 15 giây khi rảnh |
| `/api/v1/provinces` | HTTP GET | Tỉnh/thành active; q/page/page_size; công khai |
| `/api/v1/wards?province_id=01` | HTTP GET | Phường/xã active; province_id/q/page/page_size; công khai |
| `/api/v1/geography/nearest-ward` | HTTP POST | Tọa độ → ward gần nhất; công khai |
| `/api/v1/users/me/address` | GET/PATCH/DELETE | Địa chỉ riêng của user; cần Bearer JWT |

Timestamp đầu vào bắt buộc có timezone, chuẩn hóa UTC trước khi lưu bằng `TIMESTAMPTZ` trên PostgreSQL.
UI hiển thị giờ Việt Nam. Đơn vị: nhiệt độ °C, độ ẩm %, tốc độ gió km/h, lượng mưa mm/h.
Ngưỡng **minh họa**: nhiệt độ ≥35°C, mưa ≥20 mm/h, gió ≥50 km/h; chưa phải cảnh báo khí tượng chính thức.

### TCP ingestion

Server lắng nghe cổng 9000, mỗi frame là một JSON UTF-8 kết thúc bằng newline (`\n`),
tối đa 8192 byte, timeout đọc 60 giây. Không coi mỗi lần `recv` là một bản tin:
một bản tin có thể bị chia nhiều đoạn hoặc nhiều bản tin cùng một lần truyền.

```json
{"event_id":"8d24e03b-908a-4a0b-b38f-5a5b3a0b790c","city":"hanoi","temperature":36,"humidity":80,"wind_speed":55,"rainfall":25,"source":"simulator","observed_at":"2026-10-20T05:00:00Z"}
```

ACK sau khi commit thành công:

```json
{"status":"accepted","event_id":"8d24e03b-908a-4a0b-b38f-5a5b3a0b790c"}
```

Retry cùng `event_id` trả `status: duplicate`, không ghi hoặc broadcast lần nữa.
Publisher giữ nguyên UUID bản tin chưa có ACK khi reconnect (at-least-once delivery).
UUID là khóa chống trùng; không tái sử dụng UUID cho payload khác.
Frame sai trả `invalid_observation`; DB lỗi trả `storage_unavailable`; quá giới hạn/timeout trả
`frame_limit_or_timeout` và đóng kết nối.

Bản tin WebSocket:

```json
{
  "type": "weather.update",
  "observation": {
    "id": "8d24e03b-908a-4a0b-b38f-5a5b3a0b790c",
    "city": "hanoi", "temperature": 36, "humidity": 80,
    "wind_speed": 55, "rainfall": 25, "source": "simulator",
    "observed_at": "2026-10-20T05:00:00Z"
  },
  "alerts": [
    {"code": "heat", "severity": "warning", "message": "Nhiệt độ cao từ 35°C."}
  ]
}
```

Ví dụ trên rút gọn danh sách cảnh báo; bản tin mẫu thực tế còn có cảnh báo mưa và gió.
Hub giới hạn 32 event mỗi subscriber, bỏ event cũ nhất khi chậm. Stream là live best-effort;
DB là nguồn lịch sử. React reconnect theo exponential backoff tối đa 15 giây rồi tải snapshot hiện tại.
Client còn giám sát heartbeat 15 giây của server: quá 45 giây không có bản tin thì tự đóng socket
và reconnect, trạng thái hiển thị “Mất kết nối · đang thử lại” → “Đang đồng bộ dữ liệu” → “Đang trực tuyến”.

### Mất mạng và phục hồi

Danh mục tỉnh/xã và lịch sử nằm trong PostgreSQL (Neon theo mặc định), nên khi mất mạng thì cả
client lẫn server đều mất dữ liệu. Hệ thống xử lý theo hai lớp.

**Client**

- Danh mục tỉnh/xã, quan sát hiện tại và dự báo đều được ghi nhớ trong `localStorage`
  và hiển thị ngay khi mở app, kể cả khi đang mất mạng.
- Mọi nguồn dữ liệu tự thử lại theo backoff 1s → 10s và giữ nguyên bản gần nhất khi lỗi.
- Khi trình duyệt báo `online` thì WebSocket nối lại ngay (không chờ hết backoff) và danh mục,
  current, dự báo được tải lại đồng thời.
- Trong lúc mất kết nối, giao diện chỉ hiện **một thông báo** và đánh dấu “dữ liệu cũ” / “dự báo cũ”; khi có mạng lại thì mọi thông báo biến mất.

**Server**

- Danh mục được cache trong RAM 10 phút.
- Khi database không truy cập được, `/api/v1/provinces` và `/api/v1/wards` vẫn trả bản cache kèm
  header `X-Data-Stale: true` (503 nếu chưa có bản cache nào), WebSocket vẫn mở để stream trong
  bộ nhớ tiếp tục chạy.
- Kết nối database có timeout 5 giây nên lỗi hiện ra nhanh thay vì treo.

## Kiểm thử và demo

```bash
cd source/server
source .venv/bin/activate
ruff check .
pytest -q
```

Tests dùng SQLite tạm, không ghi Neon: TCP chia/gộp frame, validation/oversize, UUID retry,
lưu DB → broadcast WS, lọc thành phố, REST current/history/forecast. PostgreSQL/migration kiểm tra thêm
qua Compose; CI chạy cả backend, build frontend và smoke test stack.

```bash
cd source/client
npm ci
npm run build
```

Sau khi stack demo chạy, ở root:

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/weather/hanoi/current
```

Demo nhiều tab: mở dashboard 3 tab, chọn 3 thành phố, theo dõi frame WebSocket ở DevTools.
Dừng/chạy lại simulator để kiểm tra publisher retry; dừng/chạy lại server để kiểm tra React reconnect.
Kết quả kiểm tra base ngày 20/10/2026: 6/6 bài pytest pass, Ruff pass, frontend build pass;
Docker Compose chạy PostgreSQL và migration thành công. Smoke test đã xác minh TCP ACK/chống trùng,
REST current/history/forecast và WebSocket qua Nginx. Chưa có benchmark tải hoặc kiểm định mô hình AI.

Ảnh chạy thật với **dữ liệu mô phỏng**:

![Dashboard Weather Stream nhận dữ liệu mô phỏng](statics/demo-dashboard.jpg)

Bổ sung kết quả đo thực và ảnh cho các chức năng hoàn thiện trước khi nộp.

## Cấu trúc dự án

```text
.
├── README.md
├── INSTRUCTION.md                   # Giữ nguyên từ starter
├── AGENTS.md
├── compose.yaml
├── .env.example
├── .github/workflows/ci.yml
├── docs/KE_HOACH_VA_PHAN_CONG.md
├── statics/                         # Tài nguyên và dataset minh họa
└── source/
    ├── .gitignore
    ├── client/                      # React + TypeScript + Vite + Nginx
    │   └── src/{hooks,lib}
    ├── server/
    │   ├── app/{api,core,db,schemas,services,network}
    │   ├── alembic/versions/
    │   └── tests/
    ├── scripts/publish_weather.py   # Producer TCP bằng Python stdlib
    └── examples/pycharm_sample.py   # File mẫu ban đầu của thư mục, giữ để tham khảo
```

## Giới hạn và hướng phát triển

Base chạy **một Uvicorn worker** vì TCP listener và WebSocket hub nằm trong process;
chưa dùng Redis/message broker. Nếu mở rộng nhiều worker cần tách ingestion và pub/sub.
Chưa có provider thật, mô hình AI, auth, alert history/cooldown, dữ liệu cũ/stale indicator,
metric benchmark hay notification ngoài ứng dụng. Chưa đảm bảo broadcast bền vững nếu process chết
ngay sau commit; client tải lại quan sát mới nhất bằng REST current khi reconnect. Xem thứ tự triển khai và phân công trong tài liệu kế hoạch.

## Tài liệu tham khảo

- [Mẫu đồ án và hướng dẫn của thầy](https://github.com/hungdn1701/jnp-project-starter/tree/main)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [SQLAlchemy PostgreSQL / Psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg)
- [Neon: kết nối ứng dụng](https://neon.com/docs/connect/connect-from-any-app)
- [Vite: Getting Started](https://vite.dev/guide/)

## Cập nhật: JWT và Open-Meteo (03/11/2026)

Đã triển khai backend tài khoản và collector provider. Những mô tả “chưa có auth/provider” ở phần base
và tài liệu BA/UML cũ mô tả thời điểm khởi tạo; không dùng làm trạng thái hiện tại của hai tính năng này.

### JWT

Migration `0002` thêm `users` (email unique, password_hash Argon2, token_version, created_at).
Cấu hình `JWT_SECRET` ngẫu nhiên tối thiểu 32 ký tự trong cả `.env` root và `source/server/.env`.
Không đưa secret lên Git. Sinh bằng `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.
JWT HS256 mặc định 30 phút, kiểm tra signature/issuer/audience/expiry và token version tại DB.

| Endpoint | Method | Nội dung |
|---|---|---|
| `/api/v1/auth/register` | POST JSON | `{name,email,password}` → token + user, email trùng 409 |
| `/api/v1/auth/login` | POST JSON | `{email,password}` → token + user, sai thông tin 401 |
| `/api/v1/auth/me` | GET Bearer JWT | Thông tin tài khoản, không trả password hash |
| `/api/v1/auth/logout` | POST Bearer JWT | Thu hồi token hiện có, HTTP 200 với success=true/data=null |

Frontend đã nối form đăng ký/đăng nhập, hiện tên và đăng xuất. Token lưu trong sessionStorage theo tab, không lưu localStorage;
reload giữ phiên trong cùng tab; đóng tab/hết hạn cần đăng nhập lại. Chưa có refresh token, Google login, xác minh email, quên mật khẩu hay rate limit.
Weather API vẫn công khai cho khách. Trước triển khai Internet cần HTTPS và giới hạn đăng nhập tại gateway.

### Open-Meteo

Collector độc lập dùng Python stdlib, poll mặc định 15 phút, timeout/retry, UUID ổn định theo thành phố +
thời gian nguồn, chờ TCP ACK; không chuyển sang giả lập khi provider lỗi. `current.precipitation` là lượng mm
trong `current.interval` giây, collector quy đổi thành mm/h; đây là tốc độ trung bình quy đổi, không phải
số đo trạm hay xác nhận mưa cực đoan. Dữ liệu current do mô hình cung cấp, không phải AI do nhóm train.

```bash
# Development, sau khi chạy backend:
python3 source/scripts/collect_open_meteo.py --once
python3 source/scripts/collect_open_meteo.py
# Docker, .env cần JWT_SECRET và WEATHER_SOURCE=provider:
docker compose --profile live up --build -d --wait
```

Mặc định `WEATHER_SOURCE=provider`: REST và WS chỉ phục vụ provider, không trộn lịch sử simulator.
Muốn demo simulator, đặt `WEATHER_SOURCE=simulator` rồi bật profile demo, dừng collector nếu không cần.
Backend local chạy migration: `cd source/server && .venv/bin/alembic upgrade head`.
Tắt simulator khi demo dữ liệu provider. Collector có thể giữ event chờ ACK trong RAM;
không có hàng đợi bền vững qua restart. Base chưa xử lý correction cùng timestamp của provider.

Nguồn: [Open-Meteo API](https://open-meteo.com/en/docs), dữ liệu [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Frontend có attribution. Ngưỡng cảnh báo vẫn là demo; AI dự báo vẫn là persistence baseline.


## Dashboard theo phường/xã

Chọn tỉnh/thành phố để tải danh sách phường/xã trong tỉnh đó, sau đó chọn phường/xã để xem
thời tiết hiện tại và dự báo. Bộ chọn dùng mã Province/Ward từ database,
không dùng tên làm khóa; danh mục được đọc đủ các trang. Đổi tỉnh sẽ xóa Ward đang chọn và
xóa số liệu địa điểm cũ; request/socket cũ được hủy để tránh lẫn dữ liệu.
Tỉnh/thành dùng để lọc danh sách Ward, không có xã đại diện hoặc phép lấy trung bình toàn tỉnh.

`Observation.ward_id` bắt buộc, FK tới `wards.id`; tỉnh/thành được tra qua `Ward.province_id`.
API REST theo `/api/v1/wards/{ward_id}/weather/current|history|forecast`, WebSocket theo
`/api/v1/ws/wards/{ward_id}/weather`; envelope `{success,data}` và phân trang `data.results`.
Forecast giờ kế tiếp theo Ward hiện lấy hourly từ Open-Meteo, không phải persistence baseline hay AI của nhóm.

Migration `0004` hiện có `DELETE FROM observations`, sau đó bỏ `city`, thêm `ward_id`
và index theo Ward/nguồn/thời gian. **Chạy migration này sẽ xóa toàn bộ lịch sử quan sát cũ.**
Không chạy trên Neon trước khi sao lưu và thống nhất cách chuyển đổi dữ liệu; việc pull code
không đồng nghĩa đã cho phép xóa dữ liệu.

Collector dùng môi trường Python backend, đọc Ward active có tọa độ và Province active từ DB.
Chạy từ `source/server` để đọc đúng `.env`: `python ../scripts/collect_open_meteo.py --ward-id 00004 --once`.
Bỏ `--ward-id` để lấy toàn bộ Ward hợp lệ; có thể lặp cờ này để chọn nhiều Ward.
HTTP chia lô 25 điểm, rải trong chu kỳ 900 giây; TCP sender chạy riêng với tối đa 5 event/giây,
đối chiếu ACK event_id và SQLite outbox bền vững tối đa 20.000 event. Hàng đợi đầy thì ngừng
lấy thêm dữ liệu; Docker live dùng volume collector_state. Batch giảm request mạng nhưng không
đảm bảo giảm quota provider cùng tỷ lệ; cần cân đối quota và dung lượng DB khi lấy toàn quốc.
Publisher giả lập cần Ward có thật: `python ../scripts/publish_weather.py --ward-id 00004`.
Profile demo cũng cần nhập danh mục Ward trước khi phát dữ liệu.
## Trang dự báo Open-Meteo

Mở `/forecast` hoặc chọn “Dự báo Open-Meteo” trên dashboard. Hỗ trợ ba thành phố,
xem 3/7/16 ngày và chi tiết nhiệt độ, độ ẩm, gió, lượng mưa/xác suất mưa theo giờ.
Chọn từng ngày để xem tối đa 24 giờ của ngày đó; mặc định xem tối đa 24 mốc dự báo sắp tới.
Frontend kiểm tra lại mỗi 15 phút; backend cache 15 phút. Lỗi provider có thông báo/thử lại;
không dùng simulator thay thế. Bản dự báo lấy trước đó được giữ nếu lần refresh tự động bị lỗi.

API mới: `GET /api/v1/weather/{city}/provider-forecast?days=7`. Đơn vị mưa hourly là mm trong một giờ,
daily là mm/ngày. Giá trị null hiển thị “—”. Đây là dự báo mô hình Open-Meteo, **không phải AI của nhóm**
hoặc cảnh báo khí tượng chính thức. Không cần migration; dữ liệu forecast được cache trong RAM,
không lưu vào bảng observations. Chi tiết xem [API](docs/06_API.md).

API dự báo theo Ward: `GET /api/v1/wards/{ward_id}/weather/future` cố định 7 ngày, trả tối đa
168 mốc giờ bắt đầu từ giờ tròn kế tiếp. Dùng `rainfall` (mm/giờ), `rain_probability`, `rain`,
`showers`, `weather_code`; thời gian trả về theo giờ Việt Nam (`+07:00`). Dữ liệu chỉ cache RAM, không ghi DB.

### Điều hướng giao diện

Thanh điều hướng dùng chung có Tổng quan (`/`), Cảnh báo (`/alerts`)
và Dự báo (`/forecast`). Chuyển trang giữ thành phố đang chọn trong phiên giao diện và hỗ trợ
Back/Forward; link Dự báo không còn dùng query string để quyết định route.
Trang Cảnh báo hiển thị ngưỡng demo trên quan sát
mới nhất, chưa có lịch sử các đợt cảnh báo. Vite/Nginx hỗ trợ tải trực tiếp các đường dẫn này.

## Chạy bằng PyCharm

Xem [hướng dẫn Run/Debug PyCharm](docs/07_CHAY_PYCHARM.md).
Launcher tại `source/scripts/run_dev.py` chạy backend + React, tùy chọn collector theo Ward;
không tự migrate hay reset dữ liệu. Từ root: `source/server/.venv/bin/python source/scripts/run_dev.py`.
Kiểm tra cấu hình không khởi động server: thêm `--check`.
