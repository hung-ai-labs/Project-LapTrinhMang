# Hướng dẫn làm việc trong dự án Weather Stream

- Yêu cầu hiện tại của người dùng: FastAPI, React, PostgreSQL/Neon, Docker; streaming qua TCP và WebSocket.
- Giữ nguyên `INSTRUCTION.md` của thầy. Toàn bộ mã nguồn nằm trong `source/`.
- Hướng dẫn build/run và giao thức chính nằm tại `README.md` ở root.
- Code, tên biến và comment kỹ thuật dùng tiếng Anh; tài liệu/UI dùng tiếng Việt.
- Không commit `.env`, chuỗi kết nối Neon hay API key. Cập nhật `.env.example` khi thêm cấu hình.
- Timestamp lưu UTC, hiển thị theo Asia/Ho_Chi_Minh. Đơn vị: °C, %, km/h, mm/h.
- Base dùng một worker: TCP listener và WebSocket hub trong cùng process.
- Không gắn nhãn AI cho baseline hoặc gắn nhãn dữ liệu thật cho simulator.
- Sau thay đổi backend: chạy `ruff check .` và `pytest -q` tại `source/server`.
- Sau thay đổi frontend: chạy `npm run build` tại `source/client`.
- Phân công ưu tiên: xem `docs/KE_HOACH_VA_PHAN_CONG.md`.
