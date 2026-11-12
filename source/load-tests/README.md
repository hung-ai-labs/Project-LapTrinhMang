# Kiểm thử tải Apache JMeter — 100 người dùng

> Backend hiện là Spring Boot. Các minh chứng trong `evidence/` thuộc bản Python cũ; chưa chứng minh tải bản Java.

Mục tiêu: đo baseline trước khi tối ưu. Mỗi người dùng mở **một WebSocket giữ suốt phiên**,
đọc 4 API theo thứ tự provinces → wards → current → history, nghỉ 1 giây rồi lặp lại.
100 người dùng thực hiện request tuần tự trong từng phiên, không đồng nghĩa 100 request
đang xử lý ở mọi thời điểm. Đây là kịch bản đọc chủ động, không phải mô phỏng chính xác
tần suất request của giao diện hiện tại. Không tải trang/render React bằng trình duyệt.

Publisher gửi 1 bản tin mô phỏng/giây qua raw TCP, server commit PostgreSQL rồi phát WebSocket.
Mỗi phiên phải nhận ít nhất một `weather.update` đúng Ward và nguồn simulator, không có
message lỗi hoặc đóng kết nối ngoài dự kiến. Chưa đo độ trễ end-to-end, mất từng event,
reconnect hoặc tải nhiều producer TCP. WS connect chỉ đo thời gian mở kết nối.

Không đưa forecast vào bài này vì endpoint hiện gọi Open-Meteo. Đo forecast cần provider
giả lập có kiểm soát hoặc một bài riêng phù hợp quota; kết quả này không xác nhận sức tải forecast/auth.

## Chuẩn bị trên Windows

- Docker Desktop đang chạy, Python 3, JDK **17+**.
- Giải nén [Apache JMeter 5.6.3](https://archive.apache.org/dist/jmeter/binaries/).
  Không cần plugin WebSocket: Groovy dùng Java HttpClient.
- Chạy lệnh từ root repository. Compose riêng không đọc `.env` của ứng dụng, không dùng Neon,
  giữ một worker và database riêng; cổng 18080 (Nginx), 18000 (API), 19000 (TCP).
- Mật khẩu/secret trong Compose này chỉ là giá trị công khai cho môi trường local kiểm thử.

```powershell
docker compose -f source/load-tests/compose.yaml up -d db
docker compose -f source/load-tests/compose.yaml --profile setup run --build --rm db-init
docker compose -f source/load-tests/compose.yaml up --build -d --wait server client
python -X utf8 source/scripts/publish_weather.py --port 19000 --ward-id 00004 --count 60 --interval 0.01
docker compose -f source/load-tests/compose.yaml --profile stream up -d simulator
```

Profile Java `init-db` nhập 34 tỉnh và 3.321 Ward từ snapshot trong jar. Dữ liệu thời tiết hoàn toàn mô phỏng.
Lần đầu có tối thiểu 60 quan sát; chạy lại tiếp tục tích lũy, cần ghi số dòng khi so sánh benchmark.

## Chạy đo

```powershell
$jmeter = 'C:/tools/apache-jmeter-5.6.3'
$jdk = 'C:/Program Files/Java/jdk-17'
# Smoke test trước khi đo chính thức:
./source/load-tests/run.ps1 -JMeterHome $jmeter -JavaHome $jdk -Users 2 -Ramp 1 -Loops 3
# Chính thức: ramp-up 30 giây, 120 vòng/user, nghỉ 1 giây/vòng:
./source/load-tests/run.ps1 -JMeterHome $jmeter -JavaHome $jdk
```

Runner kiểm tra API trước, ghi cấu hình/thời gian UTC, chạy JMeter không giao diện rồi tạo
`results/<thoi-diem>-u100/{samples.jtl,jmeter.log,run.json,summary.md,html/index.html}`.
Theo [hướng dẫn Apache](https://jmeter.apache.org/usermanual/get-started.html), dùng chế độ
CLI cho tải và tạo HTML dashboard bằng `-e -o`. Không mở listener GUI khi đo.
Thư mục results không đưa vào Git; mẫu đo đã chọn được giữ trong `evidence/`.

Ngưỡng **đề xuất để đánh giá baseline**, chưa phải SLA đã thống nhất:

- Từng API: tỷ lệ lỗi < 1%, p95 ≤ 1.000 ms; response HTTP 200, `success=true`, có dữ liệu đúng.
- Đủ 100 WS mở/kiểm tra thành công và có khoảng thời gian cùng giữ đủ 100 socket.
- Đủ `users × loops` mẫu cho mỗi API; không kết luận đạt từ lượt bị dừng sớm.

Runner báo lỗi nếu không đạt, dù tiến trình JMeter tự trả exit code 0. Summary tách HTTP/WS,
tính p50/p95 bằng nearest rank (kể cả mẫu lỗi), thông lượng trên toàn cửa sổ gồm ramp-up/kết thúc.
Không coi thông lượng HTTP + sample WS là req/s API. HTML giữ số liệu JMeter gốc theo từng label.

Có thể đổi `-Users`, `-Ramp`, `-Loops`, `-Think`, `-TargetHost`, `-Port`, `-Scheme`, `-Ward`,
`-Province`; WS assertion vẫn yêu cầu nguồn simulator. Test ngắn hơn ramp-up có thể không giữ
đủ người đồng thời và sẽ không đạt. Mặc định JMX khi mở trực tiếp cần truyền `-Jscripts=<thu-muc-load-tests>`;
runner đã truyền đường dẫn này. Dùng runner để có preflight, kết quả và kiểm tra ngưỡng đầy đủ.

## Đọc kết quả và đo lại sau tối ưu

Giữ cùng CPU/RAM Docker, worker, dataset, số user, ramp, think time và tần suất publisher.
Ghi commit, số observations, dịch vụ nền, warm/cold cache; đo lại nhiều lượt trước khi kết luận.
Kiểm tra CPU/RAM, log timeout/DB pool, p95 từng API, số socket và thông lượng.
Chỉ tối ưu sau khi có bằng chứng điểm nghẽn. Không tăng worker khi TCP/hub còn trong process.

```powershell
docker stats --no-stream
docker compose -f source/load-tests/compose.yaml logs --tail 100 server simulator
# Dừng toàn bộ môi trường đo; giữ volume để xem lại dữ liệu:
docker compose -f source/load-tests/compose.yaml --profile stream down
```

Để thử Neon hoặc máy triển khai thật, chuẩn bị môi trường simulator riêng rồi đổi target;
không thay URL database của môi trường đang dùng chỉ để chạy benchmark.
