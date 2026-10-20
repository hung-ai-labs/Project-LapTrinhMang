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

## Mô tả hệ thống

```mermaid
flowchart LR
    P[Python publisher mô phỏng] -->|TCP NDJSON + ACK :9000| T[FastAPI TCP listener]
    T --> V[Validation + UUID chống trùng]
    V --> D[(PostgreSQL local / Neon)]
    V --> H[WebSocket hub theo thành phố]
    H -->|WS / WSS| R[React dashboard]
    R -->|HTTP REST: hiện tại / lịch sử / baseline| A[FastAPI API :8000]
    A --> D
```

Publisher gửi dữ liệu liên tục qua **TCP socket thuần**; server kiểm tra và lưu trước khi ACK,
sau đó broadcast **WebSocket** tới các client đang theo dõi thành phố tương ứng.
HTTP dùng để truy vấn hiện tại/lịch sử và khôi phục dữ liệu khi reconnect. WebSocket chạy trên TCP,
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

## Giao tiếp và hợp đồng dữ liệu

### REST / WebSocket

| Endpoint | Giao thức | Kết quả |
|---|---|---|
| `/api/v1/health` | HTTP GET | Kiểm tra DB, trả 503 khi không kết nối được |
| `/api/v1/cities` | HTTP GET | `hanoi`, `danang`, `hcm` |
| `/api/v1/weather/{city}/current` | HTTP GET | Quan sát mới nhất + cảnh báo; 404 nếu chưa có |
| `/api/v1/weather/{city}/history?limit=60` | HTTP GET | Mới nhất trước, giới hạn 1–500 bản tin |
| `/api/v1/weather/{city}/forecast` | HTTP GET | Baseline 1 giờ; `is_ai: false` |
| `/api/v1/ws/weather/{city}` | WebSocket | `weather.update` và `heartbeat` mỗi 15 giây khi rảnh |

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
DB là nguồn lịch sử. React reconnect theo exponential backoff tối đa 15 giây rồi tải snapshot/history.

## Kiểm thử và demo

```bash
cd source/server
source .venv/bin/activate
ruff check .
pytest -q
```

Tests dùng SQLite tạm, không ghi Neon: TCP chia/gộp frame, validation/oversize, UUID retry,
lưu DB → broadcast WS, lọc thành phố, REST/history/forecast. PostgreSQL/migration kiểm tra thêm
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
curl 'http://localhost:8000/api/v1/weather/hanoi/history?limit=5'
```

Demo nhiều tab: mở dashboard 3 tab, chọn 3 thành phố, theo dõi frame WebSocket ở DevTools.
Dừng/chạy lại simulator để kiểm tra publisher retry; dừng/chạy lại server để kiểm tra React reconnect.
Kết quả kiểm tra base ngày 20/10/2026: 6/6 bài pytest pass, Ruff pass, frontend build pass;
Docker Compose chạy PostgreSQL và migration thành công. Smoke test đã xác minh TCP ACK/chống trùng,
REST history/forecast và WebSocket qua Nginx. Chưa có benchmark tải hoặc kiểm định mô hình AI.

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
ngay sau commit; client có thể phục hồi dữ liệu bằng REST history. Chỉ tải lại tối đa 60 quan sát
khi reconnect ở UI hiện tại. Xem thứ tự triển khai và phân công trong tài liệu kế hoạch.

## Tài liệu tham khảo

- [Mẫu đồ án và hướng dẫn của thầy](https://github.com/hungdn1701/jnp-project-starter/tree/main)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [SQLAlchemy PostgreSQL / Psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg)
- [Neon: kết nối ứng dụng](https://neon.com/docs/connect/connect-from-any-app)
- [Vite: Getting Started](https://vite.dev/guide/)
