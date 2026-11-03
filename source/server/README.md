# Server · FastAPI

Chạy từ thư mục này. Hướng dẫn đầy đủ về Docker, Neon, TCP, WebSocket và API nằm tại [README chính](../../README.md).

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# Khởi động PostgreSQL ở root: docker compose up -d db
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Dùng Python 3.12+, một worker. Swagger: http://localhost:8000/docs.
`app/network` xử lý TCP/WebSocket; `services` xử lý ingestion, cảnh báo;
`services/forecast.py` cung cấp interface predictor để tích hợp model AI sau này;
`schemas` định nghĩa hợp đồng; `db` quản lý ORM/session; `alembic` quản lý schema.

```bash
ruff check .
pytest -q
alembic revision --autogenerate -m "describe change"
```

Pytest tự cấu hình SQLite tạm, TCP port ngẫu nhiên; không ghi vào Neon.
Kiểm tra PostgreSQL thực bằng `docker compose --profile demo up --build -d --wait` ở root.

Các model export qua `from app.db import ...`; không còn module `app.db.models`.
Migration `0002` nâng từ `0001` lên schema gồm danh mục tỉnh/phường xã, user/session,
cảnh báo, forecast baseline và `created_at`/`updated_at` chung cho mọi model.
Nhập danh mục đã cố định phiên bản bằng `python ../scripts/import_administrative_units.py --apply`
sau khi migrate; bỏ `--apply` để chỉ kiểm tra snapshot mà không kết nối database.
Nguồn và giấy phép nằm ở [source/data/administrative](../data/administrative/README.md).

HTTP API trong Swagger/ReDoc được nhóm theo model/chức năng. Mọi endpoint danh sách
trả `{count, next, previous, results}` và nhận `limit` (1–500), `offset` (từ 0).
`count` được tính sau khi lọc; các liên kết trang giữ nguyên query filter.
Current/forecast/nearest-ward trả đối tượng riêng. Xem hợp đồng và ví dụ tại README root.
