# Prompt Figma — Weather Stream

Ngày 03/11/2026 · Dùng cho Figma AI/Make hoặc gửi designer.
Đây là brief thiết kế, không yêu cầu gọi API, triển khai backend hay thay đổi database.
Nguồn tính năng: [Bản đồ tính năng và màn hình](03_Y_TUONG_TINH_NANG_VA_MAN_HINH.md).

Sao chép toàn bộ nội dung trong khối dưới đây. Nếu công cụ giới hạn độ dài, làm bốn trang MVP trước,
sau đó dùng phần đăng nhập/đăng ký làm lượt bổ sung.

```text
Thiết kế giao diện high-fidelity và clickable prototype cho “Weather Stream”, một ứng dụng web theo dõi thời tiết tại Việt Nam, cảnh báo theo ngưỡng và dự báo nhiệt độ 1 giờ.

1. MỤC TIÊU VÀ PHẠM VI
Người dùng xem được thời tiết ngay với tư cách khách, không bắt buộc đăng nhập. MVP có bốn trang: Tổng quan, Lịch sử, Cảnh báo, Dự báo. Bổ sung hai frame Đăng nhập/Đăng ký nhưng không đưa auth thành điều kiện để xem thời tiết. Ba thành phố: Hà Nội, Đà Nẵng, TP. Hồ Chí Minh.
Một nguồn dự kiến là Open-Meteo; một chế độ simulator riêng phục vụ demo. Không thiết kế marketplace chọn nhiều provider. Không mô tả dữ liệu provider như số đo trạm trực tiếp.
Giao diện là thiết kế đích: dữ liệu thật, AI đã train, lịch sử cảnh báo và auth backend chưa được triển khai đầy đủ trong base. Ghi trạng thái này trong annotation ngoài frame. Dùng dữ liệu mock rõ ràng, không gọi API hoặc thu thập credentials.

2. ART DIRECTION
Tạo cảm giác một weather app chỉn chu, nhẹ, dễ hiểu, dành cho người xem thời tiết. Nền bầu trời chuyển sắc theo buổi sáng/chiều/tối, cloud/sun/moon illustration tối giản và card bán trong suốt vừa phải. Ưu tiên typography, khoảng trắng, biểu đồ và tính dễ đọc; không lạm dụng glassmorphism, gradient tím, neon, hiệu ứng 3D hoặc nền chuyển động mạnh.
Bảng màu tham khảo: navy #101B2D, sky blue #5CA9E6, teal #35BDA6, nền sáng #F3F7FB, amber #E6A23C và red #D95C59. Dùng semantic tokens và một font hỗ trợ tiếng Việt như Inter/Be Vietnam Pro.
Desktop 1440 px, grid 12 cột, nội dung tối đa khoảng 1200 px; mobile 390 px, 4 cột. Spacing theo thang 8 px, card radius 16–20 px. Thiết kế light và dark variants, không tạo hai bộ component rời nhau. Giữ văn bản tương phản tốt trên nền trời.
Toàn bộ UI bằng tiếng Việt có dấu, giọng văn rõ ràng. Đơn vị °C, %, km/h; mưa ghi đúng đơn vị/kỳ đo. Hiển thị giờ Việt Nam (UTC+7).

3. APP SHELL
Header có logo Weather Stream, điều hướng “Tổng quan / Lịch sử / Cảnh báo / Dự báo”, liên kết Đăng nhập/Đăng ký nhỏ. Mobile dùng navigation phù hợp, không ép bảng desktop thu nhỏ.
Bộ chọn thành phố giữ nguyên ngữ cảnh giữa các trang. Trạng thái kết nối và độ mới dữ liệu là hai thông tin độc lập: “Đang trực tuyến”, “Đang kết nối lại” và “Dữ liệu chưa được cập nhật”. Không hiển thị TCP, Neon, database connection string hoặc model training controls trên trang người dùng.
Footer có nguồn dữ liệu và múi giờ; frame demo có badge “Dữ liệu mô phỏng”.

4. TRANG TỔNG QUAN
Tạo điểm nhìn chính là tên thành phố và nhiệt độ lớn. Hiển thị thời điểm quan sát, nguồn và diễn giải thời tiết có căn cứ từ dữ liệu mẫu.
Ba metric card: Độ ẩm, Tốc độ gió, Lượng mưa. Tách “quan sát lúc nào” khỏi “kết nối còn hoạt động”.
Một forecast card “Nhiệt độ 1 giờ tới” có thời điểm đích và badge phương pháp. Một khu cảnh báo hiện hành có giá trị/ngưỡng và CTA “Xem chi tiết”. Có biểu đồ nhiệt độ gần đây và CTA “Xem lịch sử”.
Dùng layout bất đối xứng có thứ bậc rõ: hero weather card lớn, forecast/alert nhỏ hơn, lịch sử bên dưới. Không dàn mọi thứ thành các thẻ KPI giống nhau.

5. TRANG LỊCH SỬ
Bộ lọc thành phố, “24 giờ / 7 ngày / Tùy chọn”, metric “Nhiệt độ / Độ ẩm / Gió / Mưa”.
Biểu đồ có trục, đơn vị, legend và tooltip thời gian. Đoạn thiếu dữ liệu phải đứt, không nối thành đường giả.
Bảng có thời gian quan sát, nhiệt độ, độ ẩm, gió, mưa và nguồn, kèm pagination. Mobile giữ các cột quan trọng và có tương tác xem chi tiết thay vì chữ quá nhỏ. Không thêm Export CSV ngoài phạm vi.

6. TRANG CẢNH BÁO
Tab “Đang diễn ra / Đã kết thúc”, lọc loại chỉ số và khoảng thời gian. Một item là một đợt cảnh báo, không phải một dòng mới mỗi lần cập nhật.
Hiển thị loại cảnh báo, địa điểm, mức độ, chỉ số, ngưỡng, thời điểm bắt đầu và cập nhật cuối. Mở drawer chi tiết với diễn biến chỉ số, đường ngưỡng và thời điểm kết thúc nếu có.
Thiết kế ba tình huống khác nhau: “Không có cảnh báo đang diễn ra”, “Chưa có dữ liệu để đánh giá”, “Dữ liệu cũ — chưa thể đánh giá lại”. Không dùng lời khẳng định “an toàn tuyệt đối”.
Ngưỡng mock minh họa: nhiệt độ ≥35°C, mưa ≥20 mm/h, gió ≥50 km/h. Gắn nhãn ngưỡng demo, không trình bày như cảnh báo khí tượng chính thức.

7. TRANG DỰ BÁO
Trọng tâm là dự báo nhiệt độ đúng 1 giờ kế tiếp. Hiển thị thời điểm phát hành, thời điểm đích và phương pháp.
Biểu đồ gồm lịch sử đến hiện tại, một mốc “Hiện tại” và đúng một điểm +1 giờ. Nét liền cho lịch sử, nét đứt cho dự báo; nếu hiển thị baseline và AI cùng lúc phải có legend rõ. Không tạo dự báo AI 7 ngày hoặc 24 điểm tương lai khi phạm vi chỉ là 1 giờ.
Thiết kế các variants:
- “Mô hình AI của nhóm”: có model version và thông tin đầu vào.
- “Baseline”: “Giữ nguyên nhiệt độ quan sát mới nhất”, nhãn “Chưa sử dụng AI”.
- “Chưa đủ dữ liệu” hoặc “Model chưa sẵn sàng”: fallback có lý do nếu còn quan sát hợp lệ.
- Không có quan sát: không hiển thị số dự báo thay thế bằng 0.
- Dữ liệu cũ: hiển thị rõ tuổi dữ liệu và tính chất tham khảo.
Một accordion “Phương pháp và đánh giá” chứa version, khoảng thời gian đánh giá và bảng MAE/RMSE so với baseline. Dùng placeholder “Chưa có kết quả đánh giá” khi chưa có kết quả; không bịa 98% accuracy, confidence hoặc sai số thực nghiệm.
Dự báo từ provider, nếu xuất hiện ở phần mở rộng, phải ghi nhãn riêng; không gọi đó là AI do nhóm huấn luyện.

8. ĐĂNG NHẬP / ĐĂNG KÝ — FRAMES BỔ SUNG
Giữ chung ngôn ngữ thiết kế, có minh họa bầu trời phù hợp theme và form dễ đọc.
Đăng nhập: email, mật khẩu, hiện/ẩn mật khẩu, nút Đăng nhập.
Đăng ký: họ tên, email, mật khẩu, độ mạnh mật khẩu, xác nhận mật khẩu; trạng thái xác nhận khớp/chưa khớp, inline errors.
Có đường chuyển giữa hai form và “Tiếp tục với tư cách khách” về Tổng quan. Google login ở disabled/unavailable state. Chỉ làm prototype form/validation; không mô phỏng thành công như bằng chứng auth backend đã hoạt động.

9. COMPONENTS VÀ TRẠNG THÁI
Tạo variables cho color/type/spacing/radius, Auto Layout và reusable components: header/nav, city picker, metric card, weather hero, forecast card, alert item, source badge, connection indicator, freshness badge, tabs, date filter, chart tooltip, table/pagination, drawer, button, input/password, toast và skeleton.
Có default/hover/focus/disabled/error states. Trạng thái trang: loading, empty, API error có retry, online+fresh, online+stale, reconnecting giữ giá trị cuối, đang đồng bộ lại.
Không chỉ phân biệt trạng thái bằng màu; kèm icon và nhãn. Tap target khoảng 44 px, thứ tự focus hợp lý, hỗ trợ reduced motion và trạng thái focus rõ.

10. CLICKABLE PROTOTYPE
Kết nối các luồng:
A. Tổng quan → chọn Đà Nẵng → dữ liệu và nội dung các trang giữ đúng thành phố.
B. Tổng quan → Lịch sử → đổi thời gian/metric → xem tooltip và bảng.
C. Tổng quan có cảnh báo demo → Cảnh báo → mở/đóng drawer.
D. Dự báo → xem variants AI / baseline / thiếu dữ liệu.
E. Online → reconnecting → đang đồng bộ → online; thêm một variant WS online nhưng dữ liệu stale.
F. Đăng nhập ↔ Đăng ký → Tiếp tục với tư cách khách.
Dùng component states và prototype interactions; những nút điều hướng chính phải có điểm đến.

11. DELIVERABLES
Tổ chức file thành các page: 00 Brief & Scope, 01 Foundations, 02 Components, 03 Desktop, 04 Mobile, 05 Prototype & States.
Bàn giao bốn trang MVP desktop/mobile hoàn chỉnh, hai auth frames bổ sung, bộ component/variables và annotations để developer biết trạng thái/logic nghiệp vụ.
Đánh dấu toàn bộ số liệu là dữ liệu minh họa trong annotations; các frame simulator có badge “Dữ liệu mô phỏng”. Không dùng số liệu mẫu như kết quả kiểm định AI.
Không thêm chatbot AI, radar/map, dự báo bão/lũ, màn hình admin, subscription/billing, hoặc yêu cầu đăng nhập để xem thời tiết.
```
