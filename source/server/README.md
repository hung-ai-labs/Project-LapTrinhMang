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
