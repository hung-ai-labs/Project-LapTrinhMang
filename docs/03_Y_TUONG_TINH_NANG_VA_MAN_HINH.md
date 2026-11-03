# Weather Stream — Ý tưởng tính năng và màn hình

Ngày 03/11/2026 · Brief sản phẩm phục vụ thiết kế Figma.
Nguồn phạm vi: [BA](01_PHAN_TICH_NGHIEP_VU.md), [UML](02_THIET_KE_UML.md),
[kế hoạch chức năng](KE_HOACH_VA_PHAN_CONG.md). Đây là tổng hợp ý tưởng và thiết kế đích, không phải xác nhận mọi chức năng đã chạy.

## 1. Ý tưởng sản phẩm

**Weather Stream — Theo dõi thời tiết, nhận biết thay đổi, xem dự báo ngắn hạn.**

Người dùng chọn thành phố, biết ngay số liệu mới nhất, xem diễn biến và nhận cảnh báo khi chỉ số vượt ngưỡng.
Điểm khác biệt của đồ án là dữ liệu được đẩy đến nhiều trình duyệt qua socket, có thể nhận biết mất kết nối,
và có dự báo nhiệt độ 1 giờ kèm phương pháp/độ mới dữ liệu rõ ràng.

Đề xuất MVP sử dụng **một provider Open-Meteo**, bên cạnh simulator dành cho kiểm thử.
Đây là hướng chọn nguồn đã được đề xuất trong cuộc trao đổi, chưa phải adapter đã tích hợp.
Không cần một màn hình chọn hàng loạt nhà cung cấp hoặc trộn dữ liệu nhiều API.
Dữ liệu Open-Meteo cần ghi rõ nguồn và tính chất dựa trên mô hình, không mô tả là trạm đo trực tiếp.

## 2. Bản đồ tính năng và hiện trạng

| Nhóm | Trải nghiệm người dùng | Hiện có trong code | Phần cần phát triển |
|---|---|---|---|
| Thời tiết hiện tại | Chọn Hà Nội/Đà Nẵng/TP.HCM; xem nhiệt độ, độ ẩm, gió, mưa | Có dashboard, chọn thành phố, số liệu từ simulator và nhãn nguồn | Collector Open-Meteo, freshness và hiển thị chi tiết nguồn |
| Realtime | Số liệu tự đổi, biết đang online/mất kết nối | Có TCP producer, WS và reconnect | Phân biệt dữ liệu cũ với kết nối còn mở; tải bù theo cursor/gap |
| Lịch sử | Xem biến động qua biểu đồ và bảng, lọc thời gian | Có bảng tối đa 60 bản tin ở UI, API history giới hạn | Trang riêng, biểu đồ, bộ lọc ngày/giờ và phân trang |
| Cảnh báo | Biết chỉ số vượt ngưỡng, xem diễn biến một đợt | Có cảnh báo tức thời theo ngưỡng demo | Lưu lịch sử, active/resolved, rule snapshot, cooldown và lọc |
| Dự báo | Xem nhiệt độ 1 giờ tới và phương pháp dùng để dự báo | Có persistence baseline, is_ai=false | Model đã train/đánh giá, lưu forecast metadata và so sánh baseline |
| Tài khoản | Đăng nhập/đăng ký, vẫn có thể xem với tư cách khách | Có UI, validation và thanh độ mạnh mật khẩu | Backend auth và đăng nhập Google; không thuộc luồng bắt buộc MVP |
| Vận hành | Theo dõi sức khỏe DB/nguồn và cấu hình | Có health DB, cấu hình qua env/CLI | Health nguồn, freshness, rule/model config; chưa cần admin dashboard |

Đăng nhập/đăng ký có giao diện không đồng nghĩa đã có tài khoản người dùng trong database.
AI có vị trí trên giao diện không đồng nghĩa model đã được huấn luyện.

## 3. Cấu trúc màn hình

### S01 — Tổng quan

- Header: logo, 4 mục điều hướng, liên kết đăng nhập tùy chọn.
- Bộ chọn thành phố luôn nhìn thấy, dùng chung ngữ cảnh với các trang khác.
- Khối thời tiết chính: tên thành phố, nhiệt độ lớn, trạng thái, nguồn, thời điểm quan sát.
- Ba chỉ số phụ: độ ẩm, tốc độ gió, lượng mưa và đơn vị phù hợp.
- Trạng thái kết nối và độ mới dữ liệu hiển thị riêng.
- Tóm tắt dự báo nhiệt độ 1 giờ; tóm tắt cảnh báo đang có.
- Biểu đồ nhiệt độ gần đây và liên kết xem lịch sử.
- Footer ghi nguồn, giờ Việt Nam; khi simulator hoạt động phải có nhãn “Dữ liệu mô phỏng”.

### S02 — Lịch sử thời tiết

- Giữ thành phố đang chọn; bộ lọc 24 giờ/7 ngày/khoảng tùy chọn.
- Chọn metric nhiệt độ/độ ẩm/gió/mưa; trục và tooltip có đơn vị.
- Biểu đồ không nối kín các đoạn thiếu dữ liệu.
- Bảng có phân trang, thời gian quan sát, số liệu và nguồn.
- Không thêm chức năng xuất CSV trong MVP nếu chưa được thống nhất.

### S03 — Cảnh báo

- Tab “Đang diễn ra” / “Đã kết thúc”; lọc loại chỉ số và khoảng thời gian.
- Mỗi đợt cảnh báo có tiêu đề, giá trị, ngưỡng, thời điểm bắt đầu và cập nhật cuối.
- Mở chi tiết bằng drawer: diễn biến chỉ số, rule dùng để đánh giá, thời gian kết thúc nếu có.
- Dữ liệu cũ: ghi “Chưa đủ dữ liệu mới để đánh giá”, không hiển thị chắc chắn đã an toàn.
- Chưa có cảnh báo khác với chưa có dữ liệu.
- Ngưỡng demo không được thể hiện thành cảnh báo khí tượng chính thức.

### S04 — Dự báo

- Trọng tâm: nhiệt độ dự báo đúng 1 giờ kế tiếp, thời điểm phát hành và thời điểm đích.
- Nhãn phương pháp rõ ràng: “Mô hình AI của nhóm” hoặc “Baseline — giữ nguyên quan sát mới nhất”.
- Trạng thái chưa có model, thiếu mẫu, dữ liệu cũ, model lỗi và chưa có quan sát.
- Biểu đồ: lịch sử đến hiện tại; chỉ một điểm +1 giờ dự báo, phân biệt bằng nét đứt.
- Baseline và AI là hai phương pháp khác nhau; không gắn nhãn AI cho baseline.
- Mục thu gọn “Phương pháp và đánh giá”: version, cửa sổ đánh giá, MAE/RMSE so với baseline.
  Khi chưa đánh giá thì hiện “Chưa có kết quả đánh giá”, không bịa tỷ lệ chính xác.
- Forecast của provider, nếu có sau này, phải mang nhãn riêng; không tự thêm vào MVP.

### S05/S06 — Đăng nhập và đăng ký (bổ sung)

- Có email, mật khẩu, hiện/ẩn mật khẩu; đăng ký thêm họ tên và xác nhận mật khẩu.
- Validation, trạng thái lỗi, độ mạnh mật khẩu và xác nhận chưa khớp.
- “Tiếp tục với tư cách khách” dẫn về Tổng quan.
- Google login ở trạng thái chưa khả dụng. Ghi trạng thái backend chưa tích hợp trong annotation của bản thiết kế,
  không tạo một prototype đăng nhập thành công rồi khẳng định đã có auth thật.

## 4. Luồng prototype cần có

1. Tổng quan → chọn Đà Nẵng → toàn bộ số liệu/cảnh báo/dự báo đổi ngữ cảnh nhất quán.
2. Tổng quan → Lịch sử → chọn khoảng thời gian/metric → xem tooltip và trang bảng tiếp theo.
3. Tổng quan có mưa lớn demo → Cảnh báo → mở drawer → xem ngưỡng và diễn biến đợt cảnh báo.
4. Tổng quan → Dự báo → đổi variant AI sẵn sàng / baseline / thiếu dữ liệu.
5. Đang online → reconnecting → đồng bộ lại; dữ liệu cuối vẫn tồn tại với timestamp.
6. WS online nhưng nguồn ngừng cập nhật → stale, không chuyển nhầm sang offline.
7. Đăng nhập ↔ Đăng ký → Tiếp tục với tư cách khách → Tổng quan.

## 5. Nguyên tắc thiết kế

- Thiết kế cho người xem thời tiết, không biến trang chủ thành dashboard hạ tầng TCP/DB.
- Phong cách weather app tinh tế, chuyển sắc bầu trời theo thời gian trong ngày; card đủ tương phản,
  chỉ blur nhẹ, giảm chuyển động khi người dùng yêu cầu.
- Màu xanh da trời/xanh đậm làm nền tảng; amber cho cảnh báo, đỏ cho lỗi, xanh ngọc cho trạng thái ổn định.
- Không chỉ dùng màu để truyền đạt trạng thái; có icon và văn bản.
- UI tiếng Việt có dấu; thời gian giờ Việt Nam; nhãn nguồn/đơn vị dễ đọc.
- Tối thiểu desktop 1440 px và mobile 390 px; component/auto layout, không dựng toàn bộ bằng ảnh phẳng.
- Tất cả số liệu trong prototype là minh họa; ghi annotation ngoài frame và badge mô phỏng trong frame demo.
- Không thêm chatbot, bản đồ radar, dự báo bão/lũ, trang admin hoặc đăng ký trả phí vào phạm vi lần này.

Prompt dùng trực tiếp: [Prompt Figma](04_PROMPT_FIGMA.md).
