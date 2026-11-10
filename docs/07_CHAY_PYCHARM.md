# Chạy Weather Stream bằng PyCharm

## Bấm nút Run của cấu hình main hiện có

Cấu hình `main` của dự án trỏ tới `$PROJECT_DIR$/main.py`. File này nay gọi launcher
để chạy backend và React. Chọn `main` ở thanh công cụ rồi bấm nút tam giác Run màu xanh;
không cần tạo lại Run Configuration. Mặc định không bật collector hoặc chạy migration.

Mở http://localhost:8080 sau khi console báo Vite ready. Nếu muốn collector, vào
Edit Configurations → main → Parameters: `--collector --ward-id 00004`.
Kiểm tra cấu hình mà không khởi động service: Parameters `--check` (xóa khi chạy thật).
Dừng phiên server cũ nếu cổng 8000/8080/9000 đã được sử dụng.

## 1. Chuẩn bị một lần

Mở thư mục root `Project-LapTrinhMang` bằng PyCharm. Cần Python 3.12+ và Node.js 22.12+.
Chọn Python Interpreter là:

```text
$PROJECT_DIR$/source/server/.venv/bin/python
```

Trên Windows: `source\server\.venv\Scripts\python.exe`.
Nếu chưa có virtualenv, chạy ở Terminal tại root:

```bash
python3 -m venv source/server/.venv
source/server/.venv/bin/python -m pip install -r source/server/requirements-dev.txt
cd source/client
npm ci
```

Windows dùng executable Python trong `Scripts` tương ứng. Với máy đang cấu hình sẵn, giữ nguyên `.env`.
Không chép `.env.example` đè lên `.env` đang có kết nối Neon và JWT_SECRET.

Backend và collector đọc **`source/server/.env`**, không phải `.env` root dùng cho Docker.
Các biến cần có: DATABASE_URL, JWT_SECRET, WEATHER_SOURCE=provider, ENABLE_TCP=true,
TCP_HOST=127.0.0.1, TCP_PORT=9000. Không chia sẻ secret trong Run Configuration, Git hoặc ảnh chụp.

## 2. Cách nhanh nhất: chạy Backend + React cùng lúc

**Run → Edit Configurations → + → Python**:

| Trường | Giá trị |
|---|---|
| Name | Weather Stream - All |
| Script path | `$PROJECT_DIR$/source/scripts/run_dev.py` |
| Parameters | `--service all` |
| Working directory | `$PROJECT_DIR$` |
| Python interpreter | `source/server/.venv/bin/python` |

`$PROJECT_DIR$` là ký hiệu đường dẫn dự án trong bảng; nếu ô nhập không mở rộng macro,
chọn đường dẫn thật bằng nút chọn file/thư mục của PyCharm.

Bấm **Run**. Mở:

- Web: http://localhost:8080
- Swagger: http://localhost:8000/docs
- TCP ingestion: localhost:9000

Script không chạy Docker, migration, import danh mục hoặc xóa dữ liệu. Không bật collector mặc định.
Nếu port bị chiếm, dừng phiên backend/frontend cũ rồi chạy lại; script không tự kill process khác.
Dừng toàn bộ bằng Ctrl+C trong Run console hoặc Stop (SIGINT/SIGTERM). Nếu IDE force-kill,
kiểm tra các process con còn giữ cổng trước lần chạy tiếp theo.

Terminal tương đương, chạy từ root:

```bash
source/server/.venv/bin/python source/scripts/run_dev.py --service all
```

## 3. Bật dữ liệu Open-Meteo

Database phải có danh mục tỉnh/xã, tọa độ và schema hiện tại trước khi collector chạy.
Chọn một vài mã Ward qua Swagger `GET /api/v1/wards`; mã phải tồn tại và có tọa độ.
Không mặc định chạy toàn bộ 3.321 phường/xã khi thử trên máy cá nhân.

Trong configuration trên, đổi Parameters thành:

```text
--service all --collector --ward-id 00004
```

`00004` là ví dụ; kiểm tra mã trong database trước khi dùng. Có thể lặp `--ward-id` để chọn nhiều nơi.
Collector chỉ khởi động khi backend/DB health đã sẵn sàng; cập nhật current mỗi 15 phút,
outbox SQLite ở `source/server/.collector/` để giữ bản tin chưa có ACK.
Nếu chủ động muốn toàn bộ danh mục: `--service all --collector --all-wards`; cân đối quota API và dung lượng DB.
Dự báo tương lai lấy on-demand qua backend khi mở giao diện dự báo, không phải collector current.

## 4. Chạy riêng và Debug backend

Tạo ba Python Run Configurations cùng script `run_dev.py` và interpreter như trên:

| Name | Parameters | Công dụng |
|---|---|---|
| Backend | `--service backend` | Bấm **Debug** để đặt breakpoint FastAPI; chạy trong process interpreter của PyCharm |
| Frontend | `--service frontend` | Chạy React ở 8080 bằng npm; debug Python không debug được TypeScript |
| Collector | `--service collector --ward-id 00004` | Chạy sau backend, đọc .env và gửi TCP |

Nếu chỉ muốn auto reload backend khi sửa source, thêm `--reload`; **bỏ cờ này khi Debug**
để breakpoint không bị tách sang subprocess reload. Khi Debug backend đang pause tại breakpoint,
collector hoặc API client có thể timeout — tiếp tục chạy để nhận bản tin retry.

Cách native không qua launcher: Python configuration dạng **Module name** `uvicorn`,
Parameters `app.main:app --host 127.0.0.1 --port 8000`,
Working directory `$PROJECT_DIR$/source/server`, cùng interpreter .venv.
Frontend chạy Terminal tại `source/client`: `npm run dev -- --host 127.0.0.1 --port 8080 --strictPort`.
Collector chạy Terminal tại `source/server`: `.venv/bin/python ../scripts/collect_open_meteo.py --ward-id 00004`.

## 5. Kiểm tra trước khi chạy

Từ root:

```bash
source/server/.venv/bin/python source/scripts/run_dev.py --check
source/server/.venv/bin/python source/scripts/run_dev.py --collector --ward-id 00004 --check
```

`--check` kiểm tra dependency/config và in lệnh/cwd, không gọi provider hoặc ghi database.
Không in DATABASE_URL hoặc JWT_SECRET.

## 6. Migration và danh mục là thao tác riêng

```bash
cd source/server
.venv/bin/alembic current
# Chỉ upgrade khi đã review migration và xử lý dữ liệu:
.venv/bin/alembic upgrade head
# Kiểm tra snapshot trước, không ghi DB:
.venv/bin/python ../scripts/import_administrative_units.py
# Khi cần nhập danh mục lần đầu:
.venv/bin/python ../scripts/import_administrative_units.py --apply
```

Migration `0004` hiện xóa observations cũ trước khi đổi city → ward_id. Không dùng upgrade
như bước reset mỗi lần chạy. Database Neon đã ở head thì không cần migrate/import lại để mở web.

Máy sleep/đóng nắp sẽ làm collector tạm ngưng; để thu thập 24/7 cần server luôn hoạt động.
