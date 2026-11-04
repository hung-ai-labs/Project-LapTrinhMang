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

Model được tách trực tiếp trong `app/db/`: `user.py`, `observation.py`, `province.py`,
`ward.py`, cùng Base và session. Import qua `from app.db import User, Observation, Province, Ward`.
Mọi model kế thừa `created_at`/`updated_at` từ Base; User giữ contract JWT của main.

Migration mới duy nhất trong PR là `0003_geographic_catalog.py`, kế thừa `0002_users`.
Sau khi migrate, dùng `python ../scripts/import_administrative_units.py --apply` để nhập
snapshot Việt Nam. Bỏ `--apply` để chỉ kiểm tra dữ liệu, không kết nối database.

Xem [thiết kế database](../../docs/05_THIET_KE_DATABASE.md) và
[nguồn dữ liệu/giấy phép](../data/administrative/README.md).

REST trả `{success, data}`; API danh sách dùng page/page_size và
`data.count/next/previous/results`. Swagger `/docs` và ReDoc `/redoc` công khai,
nhóm theo model. Xem [API docs](../../docs/06_API.md) cho hợp đồng đầy đủ.
Các API thời tiết/địa danh công khai; chỉ thông tin và địa chỉ riêng cần Bearer JWT.
