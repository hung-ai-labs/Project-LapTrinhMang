# Weather Stream

Dự án môn Lập trình mạng: React + **Java 17 / Spring Boot** + PostgreSQL/Neon, dữ liệu Open-Meteo, streaming qua TCP và WebSocket, đóng gói Docker.

Backend đã chuyển từ FastAPI sang Spring Boot. Mã Python backend cũ xem trong lịch sử Git trước thay đổi này; không còn dùng Uvicorn/Alembic để chạy phiên bản hiện tại. `INSTRUCTION.md` của thầy giữ nguyên.

## Chạy phát triển

```sh
cd source/server
cp .env.example .env
# Điền DATABASE_URL và JWT_SECRET (ít nhất 32 ký tự)
mvn spring-boot:run
```

Terminal thứ hai:

```sh
cd source/client
npm ci
npm run dev -- --port 8080
```

Web: http://localhost:8080 · Swagger: http://localhost:8000/docs · TCP: 9000.

Nút Run `main.py` trong PyCharm vẫn chạy Maven + React qua launcher Python tiêu chuẩn; backend thực thi bằng Java. Hướng dẫn chi tiết và luồng controller/security/service/repository: [source/server/README.md](source/server/README.md).

## Docker và database

Cấu hình `.env` root từ `.env.example`. Neon đang ở schema `0004` có thể dùng lại; không cần khởi tạo lại. Với PostgreSQL **mới**:

```sh
docker compose up -d db
docker compose --profile setup run --build --rm db-init
docker compose up --build -d server client
```

Server không tự chạy DDL/migration. Profile `db-init` là thao tác khởi tạo chủ động; không xóa dữ liệu. Khi dùng database có schema cũ hơn `0004`, hoàn tất migration bằng phiên bản cũ trước khi đổi backend.

Bật collector Java cho danh sách xã rõ ràng:

```sh
COLLECTOR_WARD_IDS=00004 docker compose --profile live up --build -d collector
```

Demo simulator: đặt `WEATHER_SOURCE=simulator` trong `.env`, chạy lại server rồi `docker compose --profile demo up -d simulator`. Simulator là công cụ Python độc lập gửi NDJSON TCP, không phải backend web.

## Chức năng và giao thức

- Đăng ký/đăng nhập JWT HS256, hash Argon2id; logout thu hồi JWT; lưu địa chỉ cá nhân.
- API tỉnh/thành, phường/xã, tìm địa điểm gần nhất; người dùng xem thời tiết không cần đăng nhập.
- Current Open-Meteo, lịch sử quan sát API, cảnh báo ngưỡng nhiệt/mưa/gió.
- Preview giờ tiếp theo, dự báo 7 ngày theo xã và dự báo theo giờ/ngày 3 thành phố.
- TCP NDJSON: frame tối đa 8 KiB, idempotency theo event UUID, ACK; WS theo xã và heartbeat 15 giây.
- Database lưu UTC; frontend hiển thị giờ Việt Nam. Đơn vị °C, %, km/h, mm/h.
- Collector Java có outbox file và gửi lại qua TCP. Chạy một JVM để hub và listener dùng chung trạng thái.
- Dự báo Open-Meteo và luật ngưỡng không phải mô hình AI do nhóm tự huấn luyện.

API giữ prefix `/api/v1`, envelope `{success,data,error}` và snake_case để React dùng tiếp. Tài liệu API trực tiếp tại Swagger.

## Cấu trúc

```text
source/server/       Spring Boot: controller, security, service, repository, entity, dto, network
source/client/       React + TypeScript
source/data/         Snapshot địa danh và manifest
source/scripts/      Launcher PyCharm và simulator TCP độc lập
source/load-tests/   JMeter + minh chứng lịch sử
```

Kiểm tra: `mvn test` và `mvn package` trong `source/server`; `npm test` và `npm run build` trong `source/client`.

Các tài liệu cũ trong `docs/` có thể mô tả FastAPI; ưu tiên README này và README backend cho cách chạy hiện hành. Kết quả tải 100 user trước đây thuộc backend Python, cần đo lại sau chuyển Java.

Báo cáo đối chiếu sau chuyển đổi và các lỗi đã sửa: [kiểm tra tương đương Spring Boot](docs/08_KIEM_TRA_TUONG_DUONG_SPRING_BOOT.md).
