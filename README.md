# Weather Stream

Dự án môn Lập trình mạng: React + **Java 17 / Spring Boot** + PostgreSQL/Neon, dữ liệu Open-Meteo, streaming qua TCP và WebSocket, đóng gói Docker.

Backend đã chuyển từ FastAPI sang Spring Boot. Mã Python backend cũ xem trong lịch sử Git trước thay đổi này; không còn dùng Uvicorn/Alembic để chạy phiên bản hiện tại. `INSTRUCTION.md` của thầy giữ nguyên.

## Chạy phát triển

Build giao diện một lần, rồi chạy server — **tất cả trên một cổng**:

```sh
cd source/client && npm ci && npm run build

cd ../server
cp .env.example .env
# Điền DATABASE_URL và JWT_SECRET (ít nhất 32 ký tự)
mvn spring-boot:run
```

Mở **http://localhost:8000** là ra giao diện. Swagger: http://localhost:8000/docs · TCP: 9000.

Spring Boot phục vụ luôn bản build React (`source/client/dist`), nên không cần mở cổng thứ hai.
Sửa giao diện thì chạy lại `npm run build` và tải lại trang — không phải khởi động lại server.

Muốn **hot reload** khi làm frontend thì bật thêm Vite ở terminal khác; nó proxy `/api` sang 8000:

```sh
cd source/client && npm run dev -- --port 8080
```

Lúc đó dùng http://localhost:8080. Đây là tùy chọn cho lúc code, không bắt buộc để chạy.

Nút Run `main.py` trong PyCharm vẫn chạy Maven + React qua launcher Python tiêu chuẩn; backend thực thi bằng Java. Hướng dẫn chi tiết và luồng controller/security/service/repository: [source/server/README.md](source/server/README.md).

## Docker và database

Cấu hình `.env` root từ `.env.example`. Neon đang ở schema `0004` có thể dùng lại; không cần khởi tạo lại. Với PostgreSQL **mới**:

```sh
docker compose up -d db
docker compose --profile setup run --build --rm db-init
docker compose up --build -d server client
```

Server không tự chạy DDL/migration. Profile `db-init` là thao tác khởi tạo chủ động; không xóa dữ liệu. Khi dùng database có schema cũ hơn `0004`, hoàn tất migration bằng phiên bản cũ trước khi đổi backend.

Bật collector Java cho danh sách xã rõ ràng:

```sh
COLLECTOR_WARD_IDS=00004 docker compose --profile live up --build -d collector
```

Demo simulator: đặt `WEATHER_SOURCE=simulator` trong `.env`, chạy lại server rồi `docker compose --profile demo up -d simulator`. Simulator là công cụ Python độc lập gửi NDJSON TCP, không phải backend web.

## Chức năng và giao thức

- Đăng ký/đăng nhập JWT HS256, hash Argon2id; logout thu hồi JWT; lưu địa chỉ cá nhân.
- API tỉnh/thành, phường/xã, tìm địa điểm gần nhất; người dùng xem thời tiết không cần đăng nhập.
- Current Open-Meteo, lịch sử quan sát API, cảnh báo ngưỡng nhiệt/mưa/gió.
- Preview giờ tiếp theo, dự báo 7 ngày theo xã và dự báo theo giờ/ngày 3 thành phố.
- TCP NDJSON: frame tối đa 8 KiB, idempotency theo event UUID, ACK; WS theo xã và heartbeat 15 giây.
- Chatbot Gemini streaming qua **SSE**, có nhiều đoạn chat và lịch sử hội thoại, cần đăng nhập.
  Số liệu thời tiết lấy qua function calling nên không bị bịa; hỏi về nghiên cứu thì dùng RAG
  (pgvector + `gemini-embedding-001`) trên chính các báo cáo trong repo, trả lời kèm trích dẫn.
  Đặt `GEMINI_API_KEY` trong `source/server/.env`, build chỉ mục bằng profile `index-docs`.
- Database lưu UTC; frontend hiển thị giờ Việt Nam. Đơn vị °C, %, km/h, mm/h.
- Collector Java có outbox file và gửi lại qua TCP. Chạy một JVM để hub và listener dùng chung trạng thái.
- Dự báo Open-Meteo và luật ngưỡng không phải mô hình AI do nhóm tự huấn luyện.

API giữ prefix `/api/v1`, envelope `{success,data,error}` và snake_case để React dùng tiếp. Tài liệu API trực tiếp tại Swagger.

## Cấu trúc

Đã [rà nhãn khô ngày mưa lớn và thử cải thiện tiếp](reports/Nhãn%20khô%20ngày%20mưa%20lớn.md): 72 hồ sơ hỗn hợp chưa tạo được nhãn khô khu vực × ngày đủ điều kiện train. Batch [21 fits phi tuyến có area_id](source/ml/hanoi_area_nonlinear_recall90_v1/README.md) kiểm chứng PASS; spline tăng nhẹ precision tại ngưỡng khóa nhưng P@R≥90 và AP gộp giảm so với Logistic area. Giữ mốc area hiện tại, chưa thay model/backend.

Đã thử [Logistic theo area_id với mục tiêu recall ≥90%](source/ml/hanoi_area_logistic_recall90_v1/README.md), 31 fits: bản thêm offset khu vực được chọn trên development. Precision tại recall ≥90% trên đường PR gộp 2023–2025 tăng 2,69% → 3,27% (chẩn đoán, không chọn ngưỡng theo test). Với ngưỡng khóa development, precision 1,85% → 2,30%, recall 95,79% → 94,70%, giảm 20,81% FP giả định. Cải thiện vừa phải, giữ nguyên candidate gốc và chưa tích hợp backend.

Đã thử [ngưỡng Logistic ưu tiên recall](source/ml/hanoi_logistic_recall_policy_v1/README.md), chọn riêng trên development 2021–2022: recall gộp 2023–2025 tăng 32,89% → 99,27%, đổi lại cảnh báo 96,29% mẫu khu vực × ngày, precision 1,05%. Có các mức 95%/99% development để đối chiếu. Đây là cấu hình nghiên cứu riêng, chưa tích hợp backend; trọng số candidate giữ nguyên.

Đã có [so sánh candidate với dự đoán Google công bố](reports/So%20sánh%20model%20công%20bố.md), dùng bản phát hành Zenodo và cùng 630.438 nhãn Hà Nội. Logistic có F1 trung bình cao hơn trong phép chiếu này; Google có AP/recall tốt hơn riêng 2025. Khác biệt về lưới, input và thời kỳ train không cho phép kết luận model nào mạnh hơn nói chung. Cách chạy và CSV nằm tại [published comparison v1](source/ml/hanoi_published_google_comparison_v1/README.md); candidate và benchmark giữ nguyên.

Dataset nghiên cứu **khu vực × ngày × thời tiết Hà Nội** và các CSV để xem nằm tại [source/data/groundsource/area_day](source/data/groundsource/area_day/README.md). Sau khi cài các thư viện trong `source/scripts/requirements-groundsource.txt`, chạy từ root bằng `python source/scripts/build_hanoi_area_day_dataset.py` để ghép lại; lần đầu cần mạng để tải thời tiết ERA5, các lần sau dùng cache. Đây là dữ liệu hồi cứu và báo cáo ngập yếu, chưa phải model AI đã train hoặc nhãn không ngập đã kiểm chứng.

Đã có [LightGBM thử nghiệm với nhãn 0 giả định](source/ml/hanoi_flood_demo/README.md), tách riêng khỏi backend đang chạy. Cài `python -m pip install -r source/scripts/requirements-hanoi-training.txt`, rồi chạy `python source/scripts/train_hanoi_flood_demo.py`; suy luận mẫu bằng `python source/scripts/predict_hanoi_flood_demo.py source/ml/hanoi_flood_demo/example_input.json`. Model chưa vượt baseline mưa trên test nhãn giả định và chưa được tích hợp làm cảnh báo sản phẩm.

Bản [train lại theo nhóm và phân tầng mùa](source/ml/hanoi_flood_season_v2/README.md) được lưu riêng. Từ root, chạy `python source/scripts/split_hanoi_by_season.py`, rồi `python source/scripts/train_hanoi_flood_demo.py --output source/ml/hanoi_flood_season_v2 --split-manifest source/ml/hanoi_flood_season_v2/grouped_split_manifest.parquet --model-name hanoi_reported_flood_season_v2`. Đây là phép đánh giá ngoại tuyến giữa các nhóm chưa thấy, có cả hai mùa; không thay thế test theo thời gian của bản đầu.

Điều tra chỉ số thấp và tái lập phép thử: [báo cáo chẩn đoán](source/ml/hanoi_flood_diagnostics/README.md), chạy từ root bằng `python source/scripts/diagnose_hanoi_flood_model.py`. Phép thử không ghi đè model v2.

Đã có [dataset nhiều năm 2015–2025, thời tiết và bão](source/data/groundsource/multiyear_2015_2025/README.md) và [thử nghiệm v3](source/ml/hanoi_flood_multiyear_v3/README.md): chọn model/ngưỡng qua 5 năm validation cuốn chiếu, so sánh có/không bão, fit lại trên toàn bộ 1.902 khu vực. Kết quả chưa ổn định qua các năm; model refit chưa có test tương lai và chưa tích hợp cảnh báo sản phẩm. Chạy lần lượt `python source/scripts/build_hanoi_multiyear.py`, `python source/scripts/train_hanoi_multiyear.py`, `python source/scripts/refit_hanoi_all_areas.py`, `python source/scripts/verify_hanoi_multiyear.py`; bước ghép cần file NOAA và cache/nguồn như README dataset.

Nguyên nhân v3 và các phép thử chẩn đoán: [báo cáo nhiều năm](source/ml/hanoi_flood_multiyear_diagnostics/README.md), tái lập bằng `python source/scripts/diagnose_hanoi_multiyear.py`. Chẩn đoán không thay model v3 hoặc tối ưu ngưỡng triển khai theo test.

Đã thử [v4 với lịch sử khu vực và ngưỡng cuốn chiếu](source/ml/hanoi_flood_history_v4/README.md): F1 năm 2023/2024/2025 tăng lên 0,107/0,205/0,153 trên cùng 587 khu vực so sánh; các năm này đã được xem trước, chưa phải test mù mới. Có bản refit cho 1.902 khu vực và predictor riêng. [Khảo sát IFS thay ERA5](source/data/groundsource/alternative_rain_audit/README.md) chưa cho cơ sở thay nguồn mưa; v4 tiếp tục dùng ERA5. Chưa tích hợp vào cảnh báo sản phẩm.

Đã khóa [chuẩn so sánh v1 và ba baseline](source/ml/hanoi_benchmark_v1/README.md): cùng 587 khu vực, hàng/nhãn/folds và lịch sử quá khứ, AP là metric chính; baseline mốc được chọn từ development là mưa × lịch sử. Chạy `python source/scripts/benchmark_hanoi_baselines.py freeze`, `python source/scripts/benchmark_hanoi_baselines.py run`, `python source/scripts/verify_hanoi_benchmark.py`. Không cần mạng hoặc train lại model; checksum bảo vệ protocol và dữ liệu đã khóa.

Đã chạy [phần 2: model đơn giản và ablation](source/ml/hanoi_simple_ablation_v1/README.md), đủ 49 lượt fit: Logistic chọn từ development đạt F1 0,183/0,252/0,320 trong 2023/2024/2025. Thêm chu kỳ mùa làm giảm AP trên ba năm so sánh trong chuỗi ablation dù giúp development; chưa quy toàn bộ sai số v4 cho mùa. Model mới chưa đạt đủ gate development đã khóa, vẫn là ứng viên thử nghiệm. Chạy `python source/scripts/train_hanoi_simple_ablation.py`, `python source/scripts/verify_hanoi_simple_ablation.py`; benchmark và model cũ giữ nguyên.

Đã có [đối chứng cùng sáu input và v4 bỏ riêng mùa](source/ml/hanoi_paired_controls_v1/README.md), 18 fits mới. Logistic vẫn vượt hai cấu hình LightGBM cùng input về AP/F1 qua ba năm. V4 bỏ đúng hai biến mùa tăng F1 lên 0,163/0,227/0,232, giúp xác nhận vấn đề khái quát theo mùa nhưng chưa vượt Logistic về F1. Chạy `python source/scripts/train_hanoi_paired_controls.py`, `python source/scripts/verify_hanoi_paired_controls.py`; vẫn là so sánh hồi cứu trên các năm đã xem trước.

Đã pin [candidate Logistic C=0,1](source/ml/hanoi_logistic_candidate_v1/README.md) với trọng số, scaler, ngưỡng và catalogue nguyên trạng; đây là mốc nghiên cứu, chưa refit hoặc triển khai. [Nghiên cứu cải thiện tiếp](reports/Cải%20thiện%20Logistic%20cảnh%20báo%20ngập.md) tách lỗi mưa thấp, lịch sử thưa và các vùng có cùng input nhưng nhãn khác, đề xuất bốn công thức có giới hạn 24 fits. Kết quả chạy tiếp nằm ở đoạn dưới; báo cáo nghiên cứu giữ nguyên như thời điểm lập kế hoạch. Đăng ký/kiểm chứng bằng `python source/scripts/register_hanoi_logistic_candidate.py register` và `verify`.

Đã chạy [bốn biến thể Logistic, 24 fits](source/ml/hanoi_logistic_extensions_v1/README.md): thêm mưa trước 1/3 ngày chỉ tăng nhẹ AP trung bình 0,1540 → 0,1556; thêm tọa độ, smoothing prior 1.095 ngày và tương tác mưa chưa cải thiện ổn định. Chưa hướng nào đạt đủ gate development; giữ candidate gốc. Chạy `python source/scripts/train_hanoi_logistic_extensions.py` và `python source/scripts/verify_hanoi_logistic_extensions.py`.

Đã đối chiếu [paper: target, input và cách training](reports/Paper%20và%20thử%20nghiệm%20ngập.md), đồng thời chạy [ba hướng mới từ cấu trúc mưa, 18 fits](source/ml/hanoi_paper_experiments_v1/README.md): spline Logistic, rolling mưa 3/6 giờ qua nửa đêm và chỉ số API bảy ngày. API chỉ tăng AP trung bình 0,154014 → 0,154225; chưa có gain đủ lớn hoặc đạt gate development, giữ candidate gốc. Kiểm chứng độc lập PASS. Chạy `python source/scripts/train_hanoi_paper_experiments.py` và `python source/scripts/verify_hanoi_paper_experiments.py`.

Đã [thử phương pháp paper với input mới](reports/Tái%20lập%20phương%20pháp%20ngập.md): tải [DEM thực và năm đặc trưng địa hình](source/data/groundsource/terrain_static_v1/README.md), chạy [24 fits cây/Random Forest/Logistic có địa hình](source/ml/hanoi_terrain_models_v1/README.md) và [sáu fits LSTM học chuỗi thời tiết 96 giờ](source/ml/hanoi_hourly_sequence_v1/README.md). Dữ liệu và model đều kiểm chứng PASS; chưa nhánh nào vượt candidate ổn định. LSTM nhỏ bốn epoch là thử nghiệm có giới hạn, không phải tái lập đầy đủ Google hoặc kết luận toàn bộ họ LSTM kém. Giữ benchmark và candidate gốc.

```text
source/server/       Spring Boot: controller, security, service, repository, entity, dto, network
source/client/       React + TypeScript
source/data/         Snapshot địa danh và manifest
source/scripts/      Launcher PyCharm và simulator TCP độc lập
source/load-tests/   JMeter + minh chứng lịch sử
```

Kiểm tra: `mvn test` và `mvn package` trong `source/server`; `npm test` và `npm run build` trong `source/client`.

Các tài liệu cũ trong `docs/` có thể mô tả FastAPI; ưu tiên README này và README backend cho cách chạy hiện hành. Kết quả tải 100 user trước đây thuộc backend Python, cần đo lại sau chuyển Java.

Báo cáo đối chiếu sau chuyển đổi và các lỗi đã sửa: [kiểm tra tương đương Spring Boot](docs/08_KIEM_TRA_TUONG_DUONG_SPRING_BOOT.md).
