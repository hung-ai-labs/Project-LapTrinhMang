# Chạy bản Spring Boot

Backend hiện dùng Java 17 và Maven. Xem [hướng dẫn backend](../source/server/README.md).

1. Tạo `source/server/.env` từ `.env.example`, điền kết nối DB và JWT_SECRET.
2. Đảm bảo `java -version`, `mvn -version`, `npm -v` chạy được trong terminal.
3. Cài frontend bằng `npm ci` trong `source/client`.
4. PyCharm chọn Python bất kỳ còn hợp lệ cho root `main.py`, working directory là root dự án; Run để mở cả Maven backend và React. Launcher chỉ dùng thư viện chuẩn Python, không cần cài FastAPI.
5. Mở http://localhost:8080 cho giao diện; http://localhost:8000/docs là Swagger. Cổng 8000 gốc không phải trang React.

Debug backend Java: mở Maven project trong IntelliJ IDEA, chọn JDK 17, Run/Debug `WeatherApplication`, working directory `source/server`.

Khởi động bình thường không sửa database. Chỉ dùng profile `init-db` khi chủ động tạo DB mới. Không dùng lệnh Alembic ở phiên bản Java.
