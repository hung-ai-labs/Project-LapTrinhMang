# Weather Stream — Phân tích nghiệp vụ

Phiên bản 0.1 · Ngày 20/10/2026 · Trạng thái: **đề xuất để nhóm duyệt trước khi triển khai tiếp**.

## 1. Mục tiêu và bối cảnh

Người xem cần biết thời tiết hiện tại, biến động gần đây, dự báo ngắn hạn và chỉ số bất thường
ở địa điểm quan tâm. Nhóm cần chứng minh kiến thức lập trình mạng bằng một luồng dữ liệu liên tục,
truyền TCP socket, phục vụ đồng thời nhiều client và xử lý mất kết nối/gửi lại.

Hệ thống đề xuất: nguồn khí tượng → collector → TCP ingestion → PostgreSQL/Neon →
WebSocket → React. REST phục vụ snapshot, lịch sử, cảnh báo và dự báo.
Nhà cung cấp thường được **poll qua HTTPS**; luồng collector → server → browser là streaming
của hệ thống, không mô tả nhầm provider đang cung cấp socket streaming nếu họ không hỗ trợ.

## 2. Phạm vi

| Phạm vi | Nội dung |
|---|---|
| MVP bắt buộc | Chọn địa điểm; hiện tại; lịch sử/biểu đồ; streaming nhiều client; trạng thái kết nối và dữ liệu cũ; cảnh báo theo ngưỡng kèm lịch sử; dự báo nhiệt độ 1 giờ; đánh giá model so với baseline; Docker và tài liệu giao thức |
| Nền tảng hiện có | TCP NDJSON + ACK/UUID; simulator; REST/WS; PostgreSQL/Alembic; React; cảnh báo tức thời; persistence baseline |
| Cần phát triển | Adapter dữ liệu thật; bảng nghiệp vụ mới; lịch sử cảnh báo/cooldown; biểu đồ; freshness; inference AI thực; đánh giá; khả năng phục hồi |
| Sau MVP | Tài khoản, địa điểm yêu thích, email/push, bản đồ, dự báo nhiều ngày, quản trị qua web, nhiều worker/broker |

**Không bắt buộc đăng nhập để xem MVP.** Người vận hành dùng cấu hình/CLI; chưa có màn hình admin.
MVP dự báo nhiệt độ 1 giờ, không cam kết tự dự báo bão/lũ hoặc thay cảnh báo khí tượng chính thức.
MVP đủ chức năng theo bảng trên chưa được xem là hoàn thành chỉ vì base đã chạy.

## 3. Tác nhân và ranh giới

| Mã | Tác nhân | Vai trò |
|---|---|---|
| A01 | Người xem | Chọn địa điểm, xem dữ liệu, cảnh báo và dự báo |
| A02 | Người vận hành | Cấu hình nguồn/ngưỡng, chạy collector, bật model, xem sức khỏe hệ thống |
| A03 | Nhà cung cấp thời tiết | Hệ thống ngoài cung cấp quan sát/lịch sử qua HTTPS |
| A04 | TCP Producer | Collector hoặc simulator độc lập gửi bản tin và chờ ACK |

Collector nằm trong phạm vi giải pháp tổng thể; trong use case của **Weather Stream Server + Web**,
producer là tác nhân kỹ thuật ngoài ranh giới đó. AI inference là thành phần nội bộ, không vẽ thành
người dùng hay dịch vụ AI bên ngoài khi chưa chọn kiến trúc đó. Neon là hạ tầng lưu trữ, không phải
actor nghiệp vụ của use case. Đào tạo model do người vận hành kích hoạt ngoài request phục vụ người xem.

## 4. Yêu cầu chức năng và nghiệm thu

| Mã | Yêu cầu | Ưu tiên | Điều kiện nghiệm thu |
|---|---|---|---|
| FR01 | Liệt kê/chọn địa điểm | Must | Ban đầu hỗ trợ Hà Nội, Đà Nẵng, TP.HCM; mã địa điểm hợp lệ; đổi địa điểm không trộn dữ liệu |
| FR02 | Xem thời tiết hiện tại | Must | Hiện nhiệt độ, độ ẩm, gió, mưa, nguồn, thời gian quan sát và freshness; chưa có dữ liệu thì có trạng thái trống |
| FR03 | Xem lịch sử | Must | Lọc địa điểm/khoảng thời gian, phân trang; biểu đồ theo thời gian; chỉ trả dữ liệu đúng nguồn đã chọn |
| FR04 | Thu thập dữ liệu thật | Must | Collector chuẩn hóa đơn vị/timezone, có timeout/retry và tôn trọng hạn mức provider; không giả lập dữ liệu khi provider lỗi |
| FR05 | Tiếp nhận TCP | Must | NDJSON; validate; lưu bền vững rồi ACK; retry cùng event ID không tạo thêm bản ghi; bản tin sai không làm sập listener |
| FR06 | Cập nhật realtime | Must | Client đăng ký theo địa điểm; nhận đúng địa điểm/nguồn; ít nhất 3 client demo hoạt động đồng thời |
| FR07 | Phục hồi kết nối | Must | Tự reconnect có backoff; tải bù REST; loại trùng; không để event đến muộn ghi đè snapshot mới hơn |
| FR08 | Cảnh báo ngưỡng | Must | Đánh giá trên dữ liệu hợp lệ còn mới; sinh cảnh báo theo rule, lưu lịch sử; chống phát lặp trong cùng đợt vượt ngưỡng |
| FR09 | Xem lịch sử cảnh báo | Must | Lọc địa điểm/khoảng thời gian; thấy mức độ, thời điểm bắt đầu/kết thúc và rule tạo cảnh báo |
| FR10 | Xem dự báo 1 giờ | Must | Hiện thời điểm phát hành/đích, phương pháp, model version, dữ liệu đầu vào; thiếu dữ liệu/model lỗi thì fallback có nhãn |
| FR11 | Đánh giá model | Must | Train/validation/test theo thời gian; báo MAE/RMSE và so sánh persistence trên cùng tập test thực; lưu version/dataset window |
| FR12 | Theo dõi vận hành | Must | Health phân biệt DB/collector/độ mới dữ liệu; log có event ID, lỗi và thời gian xử lý, không ghi secrets |
| FR13 | Cấu hình rule/model | Should | Người vận hành đổi qua cấu hình/CLI có validation; chỉ bật model có metadata và kết quả đánh giá |

## 5. Quy tắc nghiệp vụ

| Mã | Quy tắc đề xuất |
|---|---|
| BR01 | Đơn vị chuẩn: °C, %, km/h, mm/h. Chỉ chuyển precipitation sang mm/h khi biết kỳ tích lũy của provider; không đổi tên đơn vị để giả chuẩn hóa. Timestamp lưu UTC, UI giờ Việt Nam. |
| BR02 | Tách nguồn thật và simulator; không gộp hai nguồn vào cùng cửa sổ forecast hoặc đánh giá AI. Mỗi event mang source ID và location ID. |
| BR03 | ACK accepted chỉ sau commit; DB lỗi trả lỗi có thể retry; UUID giữ nguyên khi gửi lại. Trùng UUID nhưng payload khác phải trả conflict, không coi là gửi lại hợp lệ. |
| BR04 | Ngoài event ID, collector cần khóa chống trùng tự nhiên theo nguồn/địa điểm/thời điểm quan sát khi poll lại cùng dữ liệu. Chốt cách xử lý provider sửa số liệu ở mục quyết định mở. |
| BR05 | Current = quan sát có observed_at lớn nhất trong địa điểm + nguồn; nhận muộn được lưu lịch sử nhưng không làm current lùi thời gian. Loại bỏ thời gian vượt tương lai quá ngưỡng clock skew cấu hình. |
| BR06 | Freshness tách khỏi kết nối WS. WS vẫn mở nhưng provider ngừng cập nhật thì UI phải hiện dữ liệu cũ. Đề xuất stale_after = 2 × chu kỳ dữ liệu của nguồn; simulator mặc định 30 giây. |
| BR07 | Rule demo: nhiệt độ ≥35°C, mưa ≥20 mm/h, gió ≥50 km/h. Đây là ngưỡng minh họa, chưa phải chuẩn khí tượng. Rule thật phải được người vận hành chốt. |
| BR08 | Mỗi địa điểm + nguồn + rule chỉ có tối đa một đợt cảnh báo đang active. Vượt ngưỡng mở đợt; các quan sát tiếp theo cập nhật đợt, không tạo đợt mới. Trở lại dưới ngưỡng đóng đợt. |
| BR09 | Đề xuất cooldown 15 phút cho thông báo lặp cùng rule; đóng/mở đợt vẫn được ghi lịch sử. Dữ liệu stale không kết luận đã an toàn; giữ cảnh báo trước đó kèm nhãn không có quan sát mới. |
| BR10 | Model inference chỉ dùng lịch sử có sẵn tại thời điểm phát hành. Không dùng tương lai, dữ liệu simulator hoặc model chưa duyệt để báo kết quả AI thực. |
| BR11 | Thiếu số mẫu, model lỗi hoặc dữ liệu stale: trả baseline nếu còn quan sát hợp lệ và ghi rõ fallback/stale; nếu chưa có quan sát, trả unavailable thay vì bịa forecast. |
| BR12 | Mỗi forecast lưu generated_at, target_at, input_from/to, input observation cuối, phương pháp và model version nếu có. Thiết kế đích đề xuất target_at = generated_at + 1 giờ; thời gian quan sát đầu vào vẫn giữ nguyên để nhận biết dữ liệu stale. Kết quả dự báo provider phải ghi nhãn riêng với AI của nhóm. |
| BR13 | Live WebSocket là best-effort; history DB là nguồn phục hồi. Khi queue đầy có thể bỏ event live cũ, client phải có cách phát hiện gap và tải bù. Không cam kết exactly-once broadcast. |

Các giá trị freshness/cooldown/clock skew là **đề xuất thiết kế**, chưa phải cấu hình đã triển khai.

## 6. Use case đặc tả

### UC01 — Xem thời tiết theo địa điểm

- Actor: A01. Trigger: mở dashboard/chọn địa điểm. Tiền điều kiện: địa điểm thuộc danh sách hỗ trợ.
- Luồng chính: tải danh sách → chọn địa điểm → mở subscription → tải snapshot/history → merge theo ID/thời gian → hiển thị số liệu/nguồn/freshness → tiếp tục nhận live event.
- Thay thế: chưa có dữ liệu → trạng thái trống; API lỗi → báo lỗi và cho retry; dữ liệu cũ → giữ số liệu cuối kèm nhãn stale.
- Hậu điều kiện: UI chỉ hiển thị đúng địa điểm + nguồn đang chọn.
- Truy vết: FR01, FR02, FR06, FR07; BR02, BR05, BR06.

### UC02 — Xem lịch sử

- Actor: A01. Tiền điều kiện: chọn địa điểm + nguồn và khoảng thời gian hợp lệ.
- Luồng chính: gửi bộ lọc → kiểm tra phạm vi/giới hạn → đọc DB theo cursor → trả thứ tự thời gian → vẽ biểu đồ/bảng → tải trang tiếp theo nếu cần.
- Thay thế: khoảng thời gian sai → lỗi validation; khoảng trống → thông báo không có dữ liệu, không nối giả thành đường liên tục.
- Hậu điều kiện: kết quả có đơn vị và thời gian rõ ràng. Truy vết: FR03; BR01, BR02.

### UC03 — Tiếp nhận quan sát TCP

- Actor: A04. Tiền điều kiện: producer được phép kết nối, payload theo hợp đồng.
- Luồng chính: gom byte tới newline → kiểm tra frame/schema/đơn vị → kiểm tra UUID và khóa tự nhiên → transaction lưu quan sát → commit → đánh giá/cập nhật cảnh báo theo thời gian → phát live event → ACK.
- Thay thế: chia/gộp frame → buffer; sai schema → error; trùng cùng payload → duplicate; UUID khác payload → conflict; DB lỗi → rollback + retryable error; ACK mất → producer gửi lại cùng UUID.
- Hậu điều kiện: bản tin accepted có dữ liệu trong DB, tối đa một bản ghi nghiệp vụ cho cùng sự kiện.
- Truy vết: FR04, FR05, FR06, FR08; BR01–BR05, BR08, BR13.
- Chú ý: commit observation và alert có thể dùng cùng transaction trong implementation đích. Nếu tách như base hiện tại, cần bước reconciliation để xử lý chết process giữa hai bước; chưa có outbox trong MVP.

### UC04 — Xem cảnh báo

- Actor: A01. Trigger: cập nhật realtime hoặc mở lịch sử cảnh báo.
- Luồng chính: hệ thống đánh giá rule trên quan sát mới còn fresh → mở/cập nhật/đóng đợt → lưu DB → gửi thông tin thay đổi → UI hiện banner và lịch sử.
- Thay thế: không có dữ liệu/stale → không kết luận an toàn; chưa vượt ngưỡng → hiển thị không có cảnh báo active với thời điểm đánh giá.
- Hậu điều kiện: truy được rule và quan sát sinh cảnh báo. Truy vết: FR08, FR09; BR06–BR09.

### UC05 — Xem dự báo nhiệt độ 1 giờ

- Actor: A01. Tiền điều kiện: chọn địa điểm + nguồn.
- Luồng chính: lấy lịch sử đến thời điểm cutoff → kiểm tra freshness/số mẫu → chọn model đang active → inference → lưu forecast metadata → trả dự báo và phương pháp → UI hiển thị.
- Thay thế: có quan sát nhưng model chưa sẵn sàng/lỗi/thiếu mẫu → persistence fallback có lý do; chưa có quan sát → unavailable; forecast đã có và còn hiệu lực → dùng cache theo watermark + model version.
- Hậu điều kiện: không gắn nhãn AI cho baseline. Truy vết: FR10, FR11; BR10–BR12.

### UC06 — Khôi phục sau mất kết nối

- Actor: A01; trigger kỹ thuật: WS đóng hoặc không nhận heartbeat.
- Luồng chính: báo reconnecting → backoff → nối lại → mở subscription trước khi đồng bộ → buffer live → tải snapshot và history từ cursor → merge/loại trùng → tiếp tục live.
- Thay thế: mất lâu hơn khoảng lưu dữ liệu → full resync và báo khoảng trống; hàng đợi đầy → đánh dấu gap rồi resync; đổi địa điểm trong lúc retry → hủy subscription/các request cũ.
- Hậu điều kiện: không nhân bản hàng và không hồi quy current. Truy vết: FR06, FR07; BR05, BR13.
- Đây là thiết kế đích: base mới chỉ tải 60 bản tin khi reconnect, chưa có cursor/gap detection.

### UC07 — Chuẩn bị và bật model

- Actor: A02. Luồng: chọn dữ liệu thật → chia theo thời gian → train → đánh giá cùng baseline → lưu artifact/metadata → duyệt/active version → dùng cho inference.
- Thay thế: dữ liệu không đủ/model không đạt mục tiêu → không quảng bá là cải thiện, giữ baseline và báo kết quả thực.
- Truy vết: FR11, FR13; BR10–BR12. Đào tạo không chạy trong HTTP request.

## 7. Yêu cầu phi chức năng — mục tiêu nghiệm thu đề xuất

| Mã | Tiêu chí | Cách kiểm chứng |
|---|---|---|
| NFR01 | Ít nhất 3 client đồng thời; p95 từ server nhận frame tới UI cập nhật ≤2 giây với simulator 1 event/giây trên máy demo | Đo bằng timestamp + correlation ID; báo cấu hình máy/số mẫu, không gộp độ trễ API provider |
| NFR02 | Retry không làm tăng số dòng cho cùng event; lỗi một TCP client không ảnh hưởng client khác | Gửi lại UUID, payload sai, chia/gộp frame và reset kết nối |
| NFR03 | Sau server sẵn sàng, client reconnect trong ≤20 giây trong điều kiện mạng ổn định | Tắt/bật backend, đo thời gian; backoff tối đa 15 giây |
| NFR04 | Không hardcode secret; .env ngoài Git; Neon dùng TLS; TCP MVP chỉ mạng tin cậy/local | Rà soát Git, config và kết nối; nếu triển khai ngoài máy demo cần auth/TLS cho producer |
| NFR05 | Giới hạn frame 8 KiB, timeout đọc 60 giây, queue live 32 event/client; truy vấn lịch sử có giới hạn | Test oversize, client chậm và giới hạn API |
| NFR06 | Docker chạy theo README, DB có migration và API health; baseline chạy khi chưa có model | Clone sạch + cấu hình .env + chạy demo |

Đây là mục tiêu, **chưa phải kết quả benchmark**. Availability của provider/Neon là phụ thuộc ngoài;
UI cần phân biệt lỗi hệ thống với dữ liệu nguồn bị cũ.

## 8. Dữ liệu nghiệp vụ đề xuất

| Khái niệm | Mục đích | Hiện trạng |
|---|---|---|
| Location | Mã, tên, tọa độ, chu kỳ nguồn/freshness phù hợp | Hiện hardcode 3 thành phố, chưa có bảng |
| DataSource | Nguồn provider/simulator, chu kỳ cập nhật, trạng thái | Hiện chỉ có chuỗi source |
| WeatherObservation | Quan sát, đơn vị, thời gian, nguồn và khóa chống trùng | Có bảng observations, cần bổ sung FK/received_at/khóa tự nhiên |
| AlertRule | Metric, ngưỡng, operator, mức độ, cooldown, version | Hiện hardcode, chưa có bảng |
| WeatherAlert | Một đợt cảnh báo, trạng thái, thời gian và rule snapshot | Chưa lưu DB |
| ModelVersion | Artifact reference, loại model, window dữ liệu, MAE/RMSE, trạng thái | Chưa có bảng |
| Forecast | Kết quả, horizon, lineage đầu vào, phương pháp và model version | Hiện tính baseline trực tiếp, chưa lưu DB |

Class diagram là mô hình miền đề xuất; **không đồng nghĩa đã tạo 7 bảng**. `alembic_version`
là bảng kỹ thuật, không phải thực thể nghiệp vụ. Chưa thiết kế User/Favorite trong MVP.

## 9. Quyết định còn mở để chốt cùng nhóm

| Mã | Cần chốt | Đề xuất tạm thời | Ảnh hưởng |
|---|---|---|---|
| OQ01 | Provider thật và quyền dùng dữ liệu | Chọn sau khi kiểm tra điều khoản, hạn mức, lịch sử và đơn vị | Chu kỳ thu thập, freshness, khả năng train |
| OQ02 | Dữ liệu lịch sử có đủ để train theo giờ? | Nhiệt độ horizon 1 giờ; bắt đầu baseline, chỉ chọn model sau khi có dataset | Feature window và đánh giá |
| OQ03 | Có tài khoản trong lần nộp đầu không? | Chưa có, xem công khai | Không phát sinh auth/user schema |
| OQ04 | Chu kỳ provider, clock skew, freshness, cooldown | Freshness 2 chu kỳ, skew 5 phút, cooldown 15 phút để thảo luận | Rule, UI và dữ liệu tới muộn |
| OQ05 | Provider hiệu chỉnh dữ liệu cũ | Lưu revision hoặc upsert có audit; chưa chọn trước khi hiểu API | Khóa tự nhiên và lineage |
| OQ06 | Phân công Thắng/Đức | Bảng hiện tại ghi Đức backend, Thắng frontend; README và phần văn xuôi ghi ngược | Chưa sửa phân công khi chưa có xác nhận |
| OQ07 | Chính sách lưu lịch sử | Đề xuất 90 ngày quan sát để ước lượng dung lượng; giữ metadata model/forecast cho báo cáo | Phân trang, tải bù, chi phí; chưa bật xóa tự động |

## 10. Thứ tự triển khai sau khi duyệt thiết kế

1. Chốt phạm vi, provider, đơn vị và chu kỳ; thống nhất hợp đồng event/API và UML.
2. Bổ sung Location/DataSource và migration; hoàn thiện adapter thật và ingestion idempotent.
3. Hoàn thiện realtime, freshness và phục hồi; đo demo nhiều client.
4. Bổ sung cảnh báo bền vững, rule/cooldown và lịch sử; cập nhật UI.
5. Chuẩn bị dataset, baseline/model, đánh giá, inference/forecast metadata và UI.
6. Nghiệm thu theo FR/NFR, hoàn thiện báo cáo. Không thay database hoặc code chỉ vì tài liệu này đã được viết.

Bộ sơ đồ: [Thiết kế UML](02_THIET_KE_UML.md).
