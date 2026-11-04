# Plan: thời tiết theo Ward, dự báo giờ kế tiếp và dashboard

Ngày: 04/11/2026. Trạng thái: **CHƯA DUYỆT — CHỈ LẬP PLAN**.

## 1. Vấn đề

Yêu cầu đã chốt với người dùng:

- Observation có FK bắt buộc tới Ward. Tỉnh/thành tra qua `Ward.province_id`.
- **Collector lấy `current` theo lịch cố định mỗi 15 phút (900 giây) một chu kỳ.**
- **Observation chỉ lưu các mẫu từng lấy từ `current` của provider. History chỉ đọc lại những mẫu đó.**
- **Forecast giờ tới chỉ là preview: dashboard yêu cầu thì backend mới gọi Open-Meteo; không lưu
  vào Observation, outbox, bảng khác hay localStorage; không có job/timer lấy forecast nền.**
- **Cấu hình FE là hai bộ chọn tỉnh/thành phố và phường/xã ngay trên dashboard; không có bộ
  chỉnh chu kỳ lấy current. Collector vẫn chạy theo chu kỳ 15 phút đã chốt.**
- **Chỉ chọn tỉnh/thành: dashboard tự dùng Ward đầu tiên trong danh sách của tỉnh đó để hiển thị
  current/cảnh báo/preview; chưa tải và chưa hiển thị bất kỳ thành phần lịch sử nào.**
- **History chỉ bật khi người dùng chủ động chọn Ward trong dropdown, kể cả chọn chính Ward
  đầu tiên đang được dùng mặc định.**
- Có API current và API dự báo từ Open-Meteo cho mốc giờ tròn kế tiếp.
- Ví dụ 09:20 xem dự báo 10:00; không nội suy để tạo số liệu cho đúng 10:20.
- **Chỉ xóa dữ liệu observations cũ. Giữ nguyên Ward, Province, User.** Không xóa toàn bộ DB.
- Không tạo model archive, không có legacy_city, không chọn Ward đại diện tỉnh/thành.
- Viết lại collector lấy current từ tọa độ Ward, stream qua TCP rồi WebSocket.
- Chỉ trình bày plan để review; thay đổi source, test, cấu hình và dữ liệu phải đợi duyệt plan.

Snapshot code khi lập plan:

- `source/server/app/db/observation.py` vẫn chứa `city`, chưa có `ward_id`.
- Backend vẫn có `/weather/{city}/...` và baseline persistence.
- `source/scripts/collect_open_meteo.py` vẫn dùng LOCATIONS ba city, pending RAM và ACK chỉ xét status.
- Script đặt interval mặc định 900 nhưng `time.sleep(30 if pending else args.interval)` làm chu kỳ
  chuyển sang 30 giây khi còn pending; địa điểm đã gửi xong có thể bị fetch lại sớm. Lịch hiện tại
  cũng cộng thời gian chạy job vào thời gian nghỉ. Đây là hai hành vi phải sửa theo lịch 15 phút.
- Chưa có migration 0004 trong source hiện tại; head source là 0003.
- Worktree/index đã có thay đổi frontend chọn Province/Ward và README từ lượt trước. Không tự reset,
  ghi đè hoặc coi chúng là backend đã triển khai. Backend hiện tại chưa khớp frontend này.
- Chưa kiểm tra hoặc sửa DB ứng dụng trong lượt lập plan. Nội dung dưới đây là đề xuất, không phải
  kết quả triển khai hoặc kết quả kiểm thử mới.

## 2. Vì sao cần giải quyết

Frontend gọi API Ward sẽ không hoạt động với backend hiện chỉ nhận city. Nếu chỉ thay dropdown,
observation vẫn không có khóa địa lý đúng và các Ward trùng tên có thể bị lấy nhầm dữ liệu.

Dự báo hiện tại giữ nguyên nhiệt độ mới nhất; nó không phải dự báo tương lai từ Open-Meteo.
Không được giữ nhãn hoặc giá trị baseline rồi trình bày như dữ liệu provider.

HTTP provider và việc ghi DB phải được giới hạn tải. Không gọi provider cho từng Ward ngay trong
API danh sách hoặc theo số tab dashboard. Không cần đợi lấy hết toàn quốc mới gửi/lưu từng lô.

## 3. Hướng giải quyết

### 3.1. Trách nhiệm dữ liệu

| Thành phần | Trách nhiệm |
|---|---|
| Province | Danh mục tỉnh/thành, lọc danh sách Ward |
| Ward | Danh mục phường/xã, province_id và tọa độ đại diện của chính Ward |
| Observation | Chỉ các mẫu current đã thu thập cho một Ward; mẫu mới nhất phục vụ current, các mẫu cũ phục vụ history |
| Forecast API | Chỉ khi dashboard yêu cầu preview mới gọi Open-Meteo cho Ward được chọn; trả response, không ghi DB |
| SQLite outbox | Hàng đợi vận chuyển current chờ ACK; không phải model nghiệp vụ/DB archive |

Observation không có city/province_id/legacy_city. Không lưu lại province_id vào observation vì
đã xác định qua Ward. Không đưa bản dự báo tương lai vào current/history của Observation.

Đợt này không tạo bảng forecast và không lưu cache kết quả forecast đã hoàn tất. Dữ liệu preview chỉ
ở response/React state của dashboard. Các request đồng thời trùng Ward/tọa độ/giờ đích có thể dùng
chung một HTTP request đang chạy; kết thúc request thì bỏ trạng thái dùng chung. Lần xem/làm mới
sau đó gọi Open-Meteo lại. Không tái dùng một forecast đã tải xong để thay cho lần lấy mới.

Quy tắc ghi/đọc được chốt:

```text
Open-Meteo.current → SQLite outbox current → TCP → INSERT Observation
                                                    ↓
                                   current = mẫu mới nhất đã lưu
                                   history = những mẫu current đã lưu trước đó

Dashboard yêu cầu preview → API forecast → Open-Meteo.hourly → trả dashboard
                                                        không ghi Observation
```

Ví dụ: current 09:00 và 09:15 được lưu thành hai observation. Lúc 09:20 dashboard xem forecast
10:00 thì bản forecast không được INSERT. Đến 10:00, collector phải lấy current mới từ provider
rồi lưu; không tự chuyển forecast 10:00 đã xem trước đó thành current hoặc history. Khi một mẫu
không còn mới nhất, vẫn giữ nguyên row để history đọc lại, không tạo thêm row history riêng.

Collector chỉ yêu cầu/chuẩn hóa nhánh `current`, không thu thập nhánh `hourly` để gửi TCP.
Schema forecast không được đưa vào ObservationInput; dữ liệu forecast không đi qua ingestion/WS
current. Nếu sau này cần lưu lịch sử dự báo, phải lập yêu cầu riêng để review.

### 3.2. Hợp đồng API

| Endpoint | Nguồn | Kết quả/lỗi |
|---|---|---|
| GET /api/v1/provinces | DB | Danh mục active, phân trang hiện có |
| GET /api/v1/wards?province_id=... | DB | Ward active trong Province active; không gọi thời tiết |
| GET /api/v1/wards/{ward_id} | DB | Chi tiết Ward; giữ contract danh mục hiện có |
| GET /api/v1/wards/{ward_id}/weather/current | Observation | Mẫu mới nhất theo observed_at/id, lọc WEATHER_SOURCE; 404 nếu chưa có |
| GET /api/v1/wards/{ward_id}/weather/history | Các current đã lưu trong Observation | Chỉ đọc DB, không gọi provider/không INSERT; phân trang, rỗng nếu chưa có |
| GET /api/v1/wards/{ward_id}/weather/forecast | Open-Meteo khi dashboard yêu cầu preview | Trả dự báo giờ tròn kế tiếp; không đọc/ghi Observation, không phụ thuộc current đã có trong DB |
| WS /api/v1/ws/wards/{ward_id}/weather | Hub trong process | Current vừa commit, chỉ Ward và source được chọn; heartbeat riêng |

Các endpoint HTTP vẫn dùng `{success,data}` và error envelope hiện có. Ward không tồn tại/inactive
hoặc thuộc Province inactive: HTTP 404, WebSocket từ chối. Forecast có Ward nhưng thiếu tọa độ:
422 với thông báo rõ. Timeout/provider lỗi hoặc thiếu mẫu giờ đích: 503, không thay bằng baseline.
History giữ page/page_size tối đa 100; không trả hàng trăm nghìn dòng một lần.

Current và history chỉ đọc các mẫu current đã lưu trong DB, không tự gọi Open-Meteo hoặc INSERT
khi người dùng GET. Khi collector chưa lấy đến Ward, current trả 404 và UI báo chưa có dữ liệu; forecast vẫn có thể lấy theo tọa độ Ward đó.
Các API city cũ và schema city được thay bằng Ward; frontend và producer đổi đồng bộ.

Ví dụ forecast JSON đề xuất:

```json
{
  "success": true,
  "data": {
    "ward_id": "00004",
    "provider": "open_meteo",
    "method": "open_meteo_hourly",
    "data_kind": "model_forecast",
    "target_at": "2026-11-04T03:00:00Z",
    "fetched_at": "2026-11-04T02:20:00Z",
    "predicted_temperature": 29.1,
    "predicted_humidity": 79,
    "predicted_wind_speed": 12.3,
    "precipitation_mm": 0.2,
    "interval_seconds": 3600
  }
}
```

Các số trong JSON là minh họa contract, không phải dữ liệu live đã lấy.

### 3.3. Luồng current và stream

```text
Scheduler: khởi động → mỗi 15 phút (900 giây) bắt đầu một chu kỳ current
Collector: đọc Ward active + Province active + đủ tọa độ từ DB
  → chia lô tọa độ, rải trong chu kỳ → HTTP Open-Meteo current
  → chuẩn hóa và ghi từng lô vào SQLite outbox
  → TCP sender riêng, tối đa một event đang chờ ACK/kết nối
Backend: validate Ward/event → INSERT Observation → COMMIT
  → publish hub ward:{ward_id} → ACK event_id
Dashboard: WS + REST current theo Ward đang hiển thị, kể cả Ward đầu tiên dùng mặc định
           REST history chỉ khi người dùng đã chọn Ward thủ công
```

- **Chu kỳ lấy current cố định 15 phút = 900 giây**, không chỉ là giá trị mặc định có thể tự giảm
  khi TCP lỗi. Chạy lần đầu khi collector khởi động, sau đó theo nhịp 900 giây tính từ mốc ban đầu.
  Ví dụ khởi động 09:00 thì các chu kỳ được lên lịch lúc 09:00, 09:15, 09:30, 09:45.
- Dùng monotonic clock và fixed-rate: mốc tiếp theo tính từ lịch ban đầu, không lấy thời điểm job
  kết thúc rồi cộng thêm 15 phút. Bỏ cờ thay đổi chu kỳ ngắn hơn trong luồng chạy thường;
  `CURRENT_POLL_SECONDS = 15 * 60`. `--once` chỉ dành cho chạy một chu kỳ smoke theo yêu cầu.
- Batch mặc định 25, cấu hình 1–50 điểm. Rải các lô trong cửa sổ 15 phút; mỗi Ward được lên lịch
  lấy một lần trong một chu kỳ, không gọi đồng loạt hàng nghìn request tại cùng thời điểm.
- Một producer HTTP, một sender TCP riêng; producer không chạy trong backend. Không có hai job
  lấy current chạy chồng nhau. Nếu một job chậm kéo dài, bỏ các tick cũ đã lỡ và chạy tối đa một
  chu kỳ đang đến hạn; không chạy bù dồn nhiều job hoặc suy diễn dữ liệu cho các mốc đã lỡ.
- Sender mặc định tối đa 5 event/giây, giảm tốc tự nhiên theo thời gian ACK; tái sử dụng kết nối.
- SQLite outbox tối đa 20.000 event, nằm trên volume Docker. Nếu không còn chỗ cho một lô,
  bỏ qua việc lấy thêm trong chu kỳ đó và ghi log; kiểm tra lại ở kỳ 15 phút tiếp theo. Không chờ
  hàng đợi trong producer vô hạn, không tạo job chồng nhau, không bỏ event đã lấy. Sender vẫn
  drain/retry các current đã có. Event bị từ chối vĩnh viễn giữ trạng thái rejected để kiểm tra.
- Retry TCP 1, 2, 4... tối đa 60 giây chỉ gửi lại event hiện có trong outbox. **Không gọi provider
  để lấy current mới khi retry TCP**, không đưa lịch lấy current về 30 giây.
- HTTP timeout/5xx: ghi nhận lô lỗi và chờ kỳ lấy current tiếp theo cho các Ward đó; không mở
  vòng fetch lại 30/60 giây. Các lô khác trong cùng chu kỳ vẫn theo lịch đã rải. HTTP 429 dừng
  các request provider còn lại của chu kỳ, tôn trọng Retry-After; kỳ sau cũng chỉ fetch khi hết
  thời gian provider yêu cầu chờ. Lịch vẫn là 15 phút, không tự rút ngắn để chạy bù.
- Khi provider lỗi, process ngừng, hàng đợi đầy hoặc job quá chậm, không thể bảo đảm có mẫu mới
  ở mọi mốc. Phải log kỳ/lô bị lỡ và giữ mẫu cuối trong DB; không tạo số liệu giả để đủ 15 phút.
- Nếu provider trả lại cùng timestamp/payload ở kỳ tiếp theo thì deduplicate; không tạo một row
  mới chỉ để đủ số bản ghi theo lịch. `observed_at` luôn lấy từ current của provider.
- Bản tin ổn định theo UUID5(open-meteo:ward:{ward_id}:{observed_at}). ACK phải đúng event_id.
- Retry cùng ID và payload: duplicate, không thêm row/publish lại. Cùng ID khác payload:
  event_conflict, giữ mẫu đầu tiên và giữ bản gửi mới trong outbox rejected; không ghi đè lịch sử.
- Bản tin đến muộn được lưu history; current luôn chọn observed_at lớn nhất, UI không lùi current.
- TCP ingestion có semaphore 4, timeout xử lý 20 giây. Một backend worker; shutdown đóng client
  trước khi chờ listener đóng. Đây là biện pháp giới hạn tải, chưa phải số đo bảo đảm không đơ.

Tọa độ trả về của provider có thể là ô lưới khác tọa độ Ward. Ánh xạ batch theo thứ tự request với
kiểm tra đủ số phần tử; không ghép bằng tên Ward hoặc so sánh tọa độ grid với tọa độ request.
Nhiều Ward có thể cùng ô lưới và cùng số liệu; không quảng bá đây là số đo trạm riêng từng Ward.

3.321 Ward/15 phút có thể tạo 318.816 observation/ngày. Batch giảm request mạng nhưng không thể
mặc định giảm quota provider cùng tỷ lệ. Cho phép lặp --ward-id để thử một tập nhỏ trước khi bật
cả danh mục; đánh giá quota và dung lượng/retention trước khi chạy toàn quốc dài hạn.

### 3.4. Luồng forecast Open-Meteo

```text
Dashboard đang xem Ward và yêu cầu preview → GET /wards/{id}/weather/forecast
  → kiểm tra Ward và tọa độ
  → HTTP async Open-Meteo hourly (3 mốc giờ từ giờ hiện tại)
  → chọn đúng timestamp giờ tròn kế tiếp → trả preview và fetched_at
  → không gọi ingestion, không INSERT/UPDATE Observation, không ghi outbox
```

Dùng httpx.AsyncClient trong lifespan, thêm httpx vào runtime requirements. Client được đóng khi
shutdown. Không dùng urllib đồng bộ trên event loop FastAPI.

Giới hạn đề xuất: tối đa 2 HTTP provider đồng thời; tối đa 32 tác vụ forecast khác Ward đang chờ.
Các request đồng thời trùng (Ward ID, tọa độ, giờ đích) dùng chung một tác vụ **chưa hoàn tất**.
Không có TTL/LRU cache kết quả. Task xong được bỏ khỏi inflight; yêu cầu preview sau đó gọi
provider mới. Tổng thời gian chờ và fetch được chặn 12 giây. Client ngắt kết nối không hủy tác vụ
chung đang phục vụ tab khác; shutdown hủy và await các task còn lại. Không có request preview thì
không có hoạt động lấy forecast. Response forecast dùng `Cache-Control: no-store`.

Forecast service chỉ đọc tọa độ Ward và gọi HTTP; không có Session ghi dữ liệu, không gọi ingest,
không dùng SQLite outbox. Việc giới hạn tải không được biến thành một job prefetch forecast.

Giờ đích = floor(UTC hiện tại tới giờ) + 1 giờ. Nếu HTTP hoàn thành sau khi đã qua giờ đích,
tính lại và thử một lần cho giờ đích mới; không trả dự báo đã thành quá khứ.

Open-Meteo hourly cung cấp nhiệt độ/ẩm/gió tại mốc giờ; precipitation là tổng của giờ trước mốc đó.
Giữ precipitation_mm và interval_seconds=3600 trong forecast, hiển thị rõ cửa sổ lượng mưa.
Current vẫn quy đổi precipitation_mm × 3600/current.interval thành rainfall mm/h như contract cũ.
Nguồn: [Forecast API và định nghĩa hourly](https://open-meteo.com/en/docs).

### 3.5. Cấu hình chọn địa điểm ngay trên dashboard FE

Hai bộ chọn trên FE: **Tỉnh / Thành phố** và **Phường / Xã**. Không thêm cấu hình chỉnh chu kỳ
collector ở dashboard; lịch lấy current vẫn cố định 15 phút. Hai bộ chọn dùng ID, không dùng tên
làm định danh. Đọc đủ phân trang Province và chỉ các trang Ward thuộc Province đang chọn.

Tách hai khái niệm trong state FE:

- `selectedWardId`: Ward người dùng chủ động chọn; null nếu chỉ mới chọn tỉnh/thành.
- `effectiveWardId`: Ward đang dùng để hiển thị thời tiết = selectedWardId hợp lệ, nếu chưa có
  thì lấy `wards[0].id` của danh sách tỉnh hiện tại.
- `historyEnabled`: chỉ true khi selectedWardId hợp lệ trong danh sách tỉnh hiện tại. Chọn Ward
  mặc định tự động không được gán vào selectedWardId và không được tự bật history.

| Trạng thái FE | Current/cảnh báo/preview | Phần lịch sử |
|---|---|---|
| Chưa chọn tỉnh/thành | Chưa có Ward; không gọi weather API/WS | Không render, không gọi history |
| Vừa đổi tỉnh, đang tải Ward | Xóa dữ liệu tỉnh cũ, chờ danh sách mới | Ẩn ngay, hủy request history cũ |
| Đã chọn tỉnh, chưa chọn Ward thủ công | Dùng Ward đầu tiên trong list tỉnh đó | Không render tiêu đề/bảng/counter/placeholder; không gọi history |
| Chọn thủ công Ward đầu tiên | Vẫn dữ liệu Ward đầu tiên đang hiển thị | Bắt đầu gọi và hiển thị history của Ward đó |
| Chọn thủ công Ward khác | Dùng đúng Ward được chọn | Gọi và hiển thị history của Ward được chọn |
| Xóa lựa chọn Ward về chế độ mặc định | Trở lại Ward đầu tiên trong tỉnh hiện tại | Ẩn và dừng gọi history |
| Tỉnh không có Ward | Hiển thị trạng thái chưa có địa điểm, không gọi weather API/WS | Không render, không gọi history |

Quy tắc “Ward đầu tiên”:

- Là phần tử đầu tiên của danh sách API `/wards?province_id=...` theo thứ tự backend hiện có
  (`Ward.name`, sau đó `Ward.id`), cùng danh sách hiển thị trong dropdown. Không tự đổi thứ tự.
- Đây là mặc định hiển thị của FE, không phải Ward đại diện tỉnh/thành và không ghi thêm cờ/FK
  đại diện vào Province/Ward. Tiêu đề phải ghi tên Ward đang hiển thị và tỉnh/thành tương ứng.
- Nếu Ward đầu tiên chưa có observation hoặc chưa có tọa độ để forecast thì hiện trạng thái đúng
  của Ward đó; không âm thầm chuyển sang Ward khác có dữ liệu.
- Dropdown ban đầu giữ value rỗng với nhãn “Mặc định: [tên Ward đầu tiên] — chưa chọn thủ công”.
  Ward đầu tiên vẫn là một option có ID riêng. Nhờ vậy người dùng chọn chính Ward đầu tiên vẫn
  phát sinh thao tác chọn rõ ràng và bật history. Không đặt sẵn value của select bằng ID Ward đầu tiên.

Cách gọi dữ liệu và chuyển trạng thái:

- Đổi Province: reset selectedWardId và history ngay, abort request/đóng socket Ward cũ, tải danh
  sách Ward mới. Không dùng lại Ward đầu tiên hoặc history của tỉnh trước trong lúc chờ.
- Khi có effectiveWardId: gọi current, mở WS đúng Ward đó; nếu card preview đang hiển thị thì gọi
  forecast theo thao tác xem. Những việc này hoạt động cả khi historyEnabled=false.
- Chỉ historyEnabled=true mới gọi `/weather/history`, xử lý dữ liệu history, lên lịch recovery
  history và merge event WS vào history FE. Không fetch sẵn history rồi chỉ giấu bảng bằng CSS.
- Chọn thủ công chính Ward đầu tiên đang hiển thị: effectiveWardId không đổi, chỉ bật history;
  giữ current/preview/WS hiện có, không cần lấy lại forecast hoặc reconnect socket chỉ để bật history.
- Tắt history hoặc đổi tỉnh: hủy request history đang chạy, dừng recovery, trả visibleHistory=[]
  ngay trong render. Response đến muộn không được làm history xuất hiện trở lại.
- Mỗi 60 giây/reconnect chỉ đọc current từ DB; đọc thêm history khi historyEnabled=true. Lịch
  lấy current từ Open-Meteo vẫn mỗi 15 phút, không thay đổi theo lựa chọn hoặc recovery của FE.
- Forecast chỉ lấy khi xem preview/làm mới; không lấy do timer, reconnect, heartbeat hoặc event
  current. Qua giờ đích không tự ghi preview thành observation và không tự lấy forecast nền.
- Current/history/forecast có lỗi riêng: preview 503 không xóa current; khi đã chọn Ward thì history
  rỗng mới hiển thị “Chưa có lịch sử”. Chưa chọn Ward thủ công thì ẩn toàn bộ section history.
- Forecast ghi giờ đích, fetched_at và nguồn Open-Meteo; bỏ nhãn baseline trên card provider.
- “Đang trực tuyến” chỉ mô tả socket. Thời gian thời tiết vẫn là observed_at theo Asia/Ho_Chi_Minh.

Việc history bị ẩn chỉ là quy tắc FE. Collector vẫn lấy current mỗi 15 phút và lưu Observation
bình thường để sau khi chọn Ward, history đọc được những current đã lưu từ trước đó.

### 3.6. Reset observations và triển khai sau khi duyệt

1. Kiểm tra lại git diff/head migration/config đang dùng và DB đích, chỉ báo hostname/database đã
   che thông tin nhạy cảm và số lượng bản ghi. Không đưa URL/mật khẩu vào log/tài liệu.
2. Dừng collector/simulator/server phiên bản cũ để không ghi thêm city trong lúc đổi schema.
3. Kiểm tra FK thực tế tới observations; source hiện không định nghĩa bảng con nào cần xóa theo.
   Nếu runtime có FK ngoài dự kiến thì dừng để xem lại, không CASCADE sang các bảng khác.
4. Trong migration mới sau head thực tế: DELETE FROM observations, bỏ city/index cũ, thêm
   ward_id NOT NULL + FK RESTRICT và index Ward/source/time. PostgreSQL thực hiện trong transaction.
5. So sánh số lượng/định danh/tài khoản của Ward/Province/User trước và sau; observations = 0.
6. Khởi động backend mới, collector theo một tập Ward có tọa độ; chỉ mở rộng tập sau khi smoke đạt.
7. Build/apply dashboard; chọn Ward và chứng minh HTTP/TCP/DB/WS là cùng ward_id.

Người dùng đã chọn xóa observation cũ sau khi duyệt plan. Bước reset không tự tạo bảng archive,
không gán observation city cũ sang một Ward bất kỳ, không DROP DATABASE. Sau reset, lịch sử cũ
không còn trong hệ thống; chỉ có các observation Ward thu thập mới. Không tự xóa volume DB.

### 3.7. File dự kiến thay đổi

| File | Thay đổi |
|---|---|
| source/server/app/db/observation.py | city → ward_id FK bắt buộc, index mới |
| source/server/alembic/versions/0004_ward_observations.py | reset chỉ observations, đổi schema; tên revision xác minh theo head khi triển khai |
| source/server/app/schemas/weather.py | schema Ward input/output và ForecastOut thực từ provider |
| source/server/app/api/routes.py | current/history/forecast/WS theo Ward, envelope/lỗi |
| source/server/app/services/forecast.py | thay baseline bằng forecast preview async theo yêu cầu, không lưu kết quả |
| source/server/app/services/ingestion.py | validate Ward, idempotency/conflict, publish theo Ward |
| source/server/app/network/tcp.py | ACK ID, phân loại lỗi, semaphore/timeout |
| source/server/app/main.py | lifecycle HTTP client/tác vụ preview đang chạy và TCP clients, một worker |
| source/server/requirements.txt | httpx runtime |
| source/server/requirements-dev.txt | bỏ khai báo httpx trùng sau khi chuyển runtime nếu phù hợp |
| source/scripts/collect_open_meteo.py | đọc tọa độ Ward, batch/scheduler/outbox/TCP sender |
| source/scripts/publish_weather.py | simulator gửi ward_id, giữ source=simulator |
| compose.yaml, source/server/Dockerfile | collector dùng dependencies/DB config phù hợp, volume outbox |
| .gitignore, source/server/.dockerignore | loại state outbox khỏi Git/image |
| source/client/src/App.tsx | bộ chọn tỉnh/Ward, mặc định Ward đầu tiên, chỉ render history khi chọn Ward thủ công |
| source/client/src/hooks/useLocations.ts | phân trang; tách selectedWardId/effectiveWardId/historyEnabled; reset khi đổi Province |
| source/client/src/hooks/useWeather.ts | current/preview/WS theo effectiveWardId, history chỉ khi historyEnabled; tách lỗi preview |
| source/client/src/lib/api.ts | Ward/Forecast types và error status |
| source/client/src/styles.css | bộ chọn responsive, card forecast |
| tests liên quan tại source/server/tests | contract Ward, FK/reset, forecast theo yêu cầu/không ghi DB/failure, stream |
| README.md, source/server/README.md | chạy/migrate/reset, API Ward, đơn vị và nhãn forecast |

Giữ nguyên INSTRUCTION.md. Không thêm model archive, Province representative hoặc model forecast.
Nếu thêm cấu hình env trong lúc triển khai, cập nhật .env.example tương ứng; plan mặc định dùng
các giới hạn nội bộ/CLI nêu trên nên không cần thêm secret mới.

## 4. Code hiện tại

Các trích đoạn dưới đây là source thật đã đọc, không phải pseudocode.

`source/server/app/db/observation.py:9`:

```python
class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (Index("ix_observations_city_time", "city", "observed_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    city: Mapped[str] = mapped_column(String(64), nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[float] = mapped_column(Float, nullable=False)
    wind_speed: Mapped[float] = mapped_column(Float, nullable=False)
    rainfall: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

`source/server/app/services/forecast.py:13`:

```python
class PersistenceForecast:
    """Reference baseline; deliberately reported as non-AI in the API contract."""

    def predict(self, observation: ObservationOut) -> ForecastOut:
        return ForecastOut(
            city=observation.city,
            predicted_temperature=observation.temperature,
            target_at=observation.observed_at + timedelta(hours=1),
            based_on=observation.id,
        )
```

`source/server/app/api/routes.py:87`:

```python
@router.get("/weather/{city}/forecast", response_model=ApiResponse[ForecastOut], tags=["Forecast"])
async def forecast(city: City, session: AsyncSession = Depends(get_session)):
    event = await current_weather(city, session)
    return success(forecaster.predict(event.observation))
```

`source/scripts/collect_open_meteo.py:31`:

```python
return {
    "event_id": str(uuid5(NAMESPACE_URL, f"open-meteo:{city}:{observed}")),
    "city": city, "temperature": values[0], "humidity": values[1],
    "wind_speed": values[2], "rainfall": round(values[3] * 3600 / interval, 4),
    "source": "provider", "observed_at": observed,
}
```

`source/scripts/collect_open_meteo.py:70–84` — nguyên nhân nhịp lấy current có thể xuống 30 giây:

```python
pending = {}
while True:
    failed = False
    for city in LOCATIONS:
        try:
            if city not in pending:
                pending[city] = fetch(city)
            deliver(pending[city], args.host, args.port)
            del pending[city]
        except (OSError, ValueError, KeyError, TypeError):
            logging.warning("%s: provider/TCP unavailable; retry pending event next cycle", city)
            failed = True
    if args.once:
        raise SystemExit(1 if failed else 0)
    time.sleep(30 if pending else args.interval)
```

Khi một city còn pending, vòng sau chạy sau 30 giây. City khác đã xóa khỏi pending sẽ gọi fetch
lại. Plan mới thay vòng này bằng lịch 15 phút riêng và sender retry riêng.

`source/client/src/hooks/useWeather.ts:58` trong phần frontend đã có ở index:

```typescript
const [snapshot, records, prediction] = await Promise.allSettled([
  api<WeatherEvent>(`${base}/current`, abort.signal),
  api<PaginatedData<Observation>>(`${base}/history?page_size=60`, abort.signal),
  api<Forecast>(`${base}/forecast`, abort.signal),
]);
```

Đây là tiến độ frontend đang có, không chứng minh backend đã cung cấp các endpoint Ward.

`source/client/src/hooks/useLocations.ts:59–66` — code hiện tại chỉ trả Ward đã chọn, chưa có mặc định:

```typescript
const wards = provinceId && wardCatalog.provinceId === provinceId ? wardCatalog.options : [];
const wardLoading = Boolean(provinceId) &&
  (wardCatalog.provinceId !== provinceId || wardCatalog.loading);
const ward = wards.find((row) => row.id === wardId) ?? null;
return {
  provinces, wards, provinceId, wardId: ward?.id ?? null,
  province: provinces.find((row) => row.id === provinceId) ?? null,
  ward, provinceLoading, wardLoading,
```

Đây là trích đoạn mở đầu của return hiện có, không phải nguyên hàm. `App.tsx` hiện render section
history không điều kiện; hook useWeather hiện gọi history khi có bất kỳ wardId nào. Hai điểm này
phải đổi cùng phần chọn Ward mặc định để không lộ history khi chỉ mới chọn tỉnh.

## 5. Code sau khi sửa

**Tất cả code ở mục này là ĐỀ XUẤT CHƯA TRIỂN KHAI.** Các block xác định schema, query, parser,
reset và test cụ thể để review. Phần wiring đầy đủ của scheduler/giới hạn preview/CLI theo các giới hạn ở mục 3
sẽ được triển khai sau duyệt; không coi những block riêng lẻ này là một patch đã áp dụng/chạy được.

### 5.1. Model và migration

`source/server/app/db/observation.py` — toàn bộ model đề xuất:

```python
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        Index("ix_observations_ward_time", "ward_id", "source", "observed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ward_id: Mapped[str] = mapped_column(
        ForeignKey("wards.id", ondelete="RESTRICT"), nullable=False
    )
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[float] = mapped_column(Float, nullable=False)
    wind_speed: Mapped[float] = mapped_column(Float, nullable=False)
    rainfall: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

`source/server/alembic/versions/0004_ward_observations.py` — chưa triển khai:

```python
"""Reset old city observations and require Ward-based ingestion."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("DELETE FROM observations"))
    with op.batch_alter_table("observations") as batch:
        batch.drop_index("ix_observations_city_time")
        batch.drop_column("city")
        batch.add_column(sa.Column("ward_id", sa.String(20), nullable=False))
        batch.create_foreign_key(
            "fk_observations_ward", "wards", ["ward_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_index("ix_observations_ward_time", ["ward_id", "source", "observed_at"])


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM observations")):
        raise RuntimeError("Ward observations must be preserved before downgrading")
    with op.batch_alter_table("observations") as batch:
        batch.drop_index("ix_observations_ward_time")
        batch.drop_constraint("fk_observations_ward", type_="foreignkey")
        batch.drop_column("ward_id")
        batch.add_column(sa.Column("city", sa.String(64), nullable=False))
        batch.create_index("ix_observations_city_time", ["city", "observed_at"])
```

### 5.2. Schema và parser forecast

`source/server/app/schemas/weather.py` — thay trường city của input/output bằng ward_id:

```python
# ObservationInput:
ward_id: str = Field(min_length=1, max_length=20)
# ObservationOut:
ward_id: str
```

Thay toàn bộ ForecastOut — chưa triển khai:

```python
class ForecastOut(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    ward_id: str
    provider: Literal["open_meteo"] = "open_meteo"
    method: Literal["open_meteo_hourly"] = "open_meteo_hourly"
    data_kind: Literal["model_forecast"] = "model_forecast"
    target_at: AwareDatetime
    fetched_at: AwareDatetime
    predicted_temperature: float = Field(ge=-60, le=65)
    predicted_humidity: float = Field(ge=0, le=100)
    predicted_wind_speed: float = Field(ge=0, le=500)
    precipitation_mm: float = Field(ge=0)
    interval_seconds: Literal[3600] = 3600
```

`source/server/app/services/forecast.py` — phần parser thay baseline, chưa triển khai:

```python
from datetime import UTC, datetime, timedelta

from app.schemas.weather import ForecastOut

HOURLY_VARIABLES = "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation"


class ForecastUnavailable(ValueError):
    pass


def next_hour(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def parse_hourly(ward_id: str, payload: dict, target: datetime, fetched_at: datetime):
    expected = {
        "time": "unixtime", "temperature_2m": "°C", "relative_humidity_2m": "%",
        "wind_speed_10m": "km/h", "precipitation": "mm",
    }
    try:
        units, hourly = payload["hourly_units"], payload["hourly"]
        if any(units.get(key) != unit for key, unit in expected.items()):
            raise ForecastUnavailable("Unexpected forecast units")
        index = hourly["time"].index(int(target.timestamp()))
        values = [hourly[key][index] for key in HOURLY_VARIABLES.split(",")]
        if any(value is None or isinstance(value, bool) for value in values):
            raise ForecastUnavailable("Missing forecast value")
        return ForecastOut(
            ward_id=ward_id, target_at=target, fetched_at=fetched_at,
            predicted_temperature=values[0], predicted_humidity=values[1],
            predicted_wind_speed=values[2], precipitation_mm=values[3],
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ForecastUnavailable("Invalid or unavailable hourly forecast") from exc
```

ForecastOut bật `allow_inf_nan=False` để từ chối NaN/Infinity. Các timestamp đầu vào và target
đều UTC aware.

Request provider bên trong service preview async theo yêu cầu — chưa triển khai:

```python
response = await self.client.get(
    "https://api.open-meteo.com/v1/forecast",
    params={
        "latitude": latitude, "longitude": longitude,
        "hourly": HOURLY_VARIABLES, "forecast_hours": 3,
        "temperature_unit": "celsius", "wind_speed_unit": "kmh",
        "precipitation_unit": "mm", "timeformat": "unixtime", "timezone": "UTC",
    },
)
response.raise_for_status()
result = parse_hourly(ward_id, response.json(), target, datetime.now(UTC))
```

`self.client` là httpx.AsyncClient từ lifespan; không tạo client mới trên từng GET. Service.get()
bao đoạn fetch bằng single-flight chỉ khi đang chạy, semaphore và timeout ở mục 3.4. Những giới hạn này
phải có test trước khi nghiệm thu, không chỉ được ghi trong tài liệu.

Service single-flight **chỉ cho tác vụ đang chạy** trong cùng `app/services/forecast.py`,
chưa triển khai. Không giữ kết quả sau khi request hoàn tất:

```python
import asyncio

import httpx


class OpenMeteoForecast:
    def __init__(self, client, *, clock=None, max_pending=32):
        self.client = client
        self.clock = clock or (lambda: datetime.now(UTC))
        self.max_pending = max_pending
        self.inflight = {}
        self.slots = asyncio.Semaphore(2)

    async def get(self, ward_id, latitude, longitude):
        for _ in range(2):
            target = next_hour(self.clock())
            key = (ward_id, latitude, longitude, int(target.timestamp()))
            task = self.inflight.get(key)
            if task is not None and task.done():
                self.inflight.pop(key, None)
                task = None
            if task is None:
                if len(self.inflight) >= self.max_pending:
                    raise ForecastUnavailable("Forecast queue is full")
                task = asyncio.create_task(self._load(key, target))
                self.inflight[key] = task
                task.add_done_callback(lambda done, request_key=key: self._finished(request_key, done))
            result = await asyncio.shield(task)
            if result.target_at > self.clock():
                return result
        raise ForecastUnavailable("Forecast target expired during request")

    def _finished(self, key, task):
        if self.inflight.get(key) is task:
            self.inflight.pop(key, None)
        if not task.cancelled():
            task.exception()  # Consume errors even if all HTTP callers disconnected.

    async def _load(self, key, target):
        ward_id, latitude, longitude, _ = key
        try:
            async with asyncio.timeout(12):
                async with self.slots:
                    response = await self.client.get(
                        "https://api.open-meteo.com/v1/forecast",
                        params={
                            "latitude": latitude, "longitude": longitude,
                            "hourly": HOURLY_VARIABLES, "forecast_hours": 3,
                            "temperature_unit": "celsius", "wind_speed_unit": "kmh",
                            "precipitation_unit": "mm", "timeformat": "unixtime", "timezone": "UTC",
                        },
                    )
                    response.raise_for_status()
                    if len(response.content) > 256 * 1024:
                        raise ForecastUnavailable("Forecast response is too large")
                    return parse_hourly(ward_id, response.json(), target, self.clock())
        except (httpx.HTTPError, TimeoutError, ValueError, TypeError) as exc:
            raise ForecastUnavailable("Forecast provider unavailable") from exc

    async def aclose(self):
        tasks = tuple(self.inflight.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
```

Wiring lifespan trong `app/main.py` — chưa triển khai, đặt lúc startup và đóng ở finally:

```python
forecast_client = httpx.AsyncClient(
    timeout=httpx.Timeout(10.0, connect=5.0),
    limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
)
app.state.forecast_service = OpenMeteoForecast(forecast_client)
# Trong finally, trước engine.dispose():
await app.state.forecast_service.aclose()
await forecast_client.aclose()
```

Giới hạn body được kiểm tra sau khi HTTPX đọc response; nếu cần chặn từ lúc tải thay vì chỉ
kiểm tra payload sau tải, triển khai streaming read tối đa 256 KiB. Không mô tả cách kiểm tra này
như bảo đảm chặn hoàn toàn bộ nhớ mạng. Request giờ đích nhỏ và concurrency được giới hạn 2.

### 5.3. API current/forecast

`source/server/app/api/routes.py` — query/endpoint đề xuất, chưa triển khai:

```python
from fastapi import HTTPException, Request, Response
from app.services.geography import active_ward
from app.services.forecast import ForecastUnavailable


async def require_ward(session, ward_id):
    ward = await active_ward(session, ward_id)
    if ward is None:
        raise HTTPException(404, "Không tìm thấy phường/xã đang hoạt động.")
    return ward


async def current_weather(ward_id: str, session: AsyncSession) -> WeatherEvent:
    await require_ward(session, ward_id)
    record = await session.scalar(
        select(Observation)
        .where(Observation.ward_id == ward_id, Observation.source == get_settings().weather_source)
        .order_by(Observation.observed_at.desc(), Observation.id.desc())
        .limit(1)
    )
    if record is None:
        raise HTTPException(404, "Chưa có dữ liệu thời tiết cho phường/xã này.")
    observation = ObservationOut.model_validate(record)
    return WeatherEvent(observation=observation, alerts=evaluate_alerts(observation))


@router.get(
    "/wards/{ward_id}/weather/current", response_model=ApiResponse[WeatherEvent],
    tags=["Observation"],
)
async def current(ward_id: str, session: AsyncSession = Depends(get_session)):
    return success(await current_weather(ward_id, session))


@router.get(
    "/wards/{ward_id}/weather/forecast", response_model=ApiResponse[ForecastOut],
    tags=["Forecast"],
)
async def forecast(
    request: Request, response: Response, ward_id: str,
    session: AsyncSession = Depends(get_session),
):
    response.headers["Cache-Control"] = "no-store"
    ward = await require_ward(session, ward_id)
    if ward.latitude is None or ward.longitude is None:
        raise HTTPException(422, "Phường/xã chưa có tọa độ để lấy dự báo.")
    try:
        value = await request.app.state.forecast_service.get(
            ward.id, float(ward.latitude), float(ward.longitude)
        )
    except ForecastUnavailable as exc:
        raise HTTPException(503, "Chưa lấy được dự báo Open-Meteo. Vui lòng thử lại.") from exc
    return success(value)
```

History thay cùng bộ lọc `Observation.ward_id == ward_id` và require_ward trước query; các câu lệnh
paginate_query giữ nguyên. WS require_ward, kiểm tra Origin, subscribe `f"ward:{ward_id}"`.
Ingestion validate active_ward, tạo Observation từ Ward input và publish cùng key sau commit.

### 5.4. Collector và dashboard

`source/scripts/collect_open_meteo.py` — scheduler current cố định 15 phút, chưa triển khai:

```python
import logging
import time

CURRENT_POLL_SECONDS = 15 * 60


def next_current_due(previous_due, now):
    next_due = previous_due + CURRENT_POLL_SECONDS
    # Skip old ticks, keeping at most the latest due tick for immediate execution.
    skipped = max(0, int((now - next_due) // CURRENT_POLL_SECONDS))
    return next_due + skipped * CURRENT_POLL_SECONDS


def run_current_schedule(collect_cycle, stop, *, clock=time.monotonic):
    due = clock()
    while not stop.is_set():
        if stop.wait(max(0, due - clock())):
            break
        try:
            collect_cycle(cycle_start=due, deadline=due + CURRENT_POLL_SECONDS)
        except Exception:
            logging.exception("Current collection cycle failed; next scheduled cycle will retry")
        due = next_current_due(due, clock())
```

collect_cycle nhận một deadline cho cửa sổ 15 phút: chỉ đọc danh mục một lần/chu kỳ; rải lô theo
cycle_start; kiểm tra stop/deadline/capacity trước mỗi HTTP request và giới hạn timeout theo thời
gian còn lại. Hết cửa sổ hoặc hàng đợi đầy thì kết thúc chu kỳ, không thêm vòng sleep/retry fetch
ngắn bên trong. Việc vượt deadline do I/O phải được log; scheduler không mở producer thứ hai.
Sender TCP chạy luồng riêng và không được gọi collect_cycle hoặc fetch.

`source/scripts/collect_open_meteo.py` — query tọa độ đề xuất, chưa triển khai:

```python
statement = (
    select(Ward.id, Ward.latitude, Ward.longitude)
    .join(Province, Province.id == Ward.province_id)
    .where(
        Ward.is_active.is_(True), Province.is_active.is_(True),
        Ward.latitude.is_not(None), Ward.longitude.is_not(None),
    )
    .order_by(Ward.id)
)
if args.ward_id:
    statement = statement.where(Ward.id.in_(args.ward_id))
```

Thay payload chuẩn hóa current — chưa triển khai:

```python
return {
    "event_id": str(uuid5(NAMESPACE_URL, f"open-meteo:ward:{ward_id}:{observed}")),
    "ward_id": ward_id,
    "temperature": values[0], "humidity": values[1], "wind_speed": values[2],
    "rainfall": round(values[3] * 3600 / interval, 4),
    "source": "provider", "observed_at": observed,
}
```

Batch HTTP dùng danh sách latitude/longitude phân cách dấu phẩy. Chỉ enqueue sau khi kiểm tra số
response và chuẩn hóa các giá trị. Outbox add ghi transaction SQLite; sender gửi từng NDJSON và
chỉ finish khi ACK đúng ID/status. Đây là phần cần viết lại thay toàn bộ vòng pending theo city;
không áp dụng riêng hai block trên rồi giữ scheduler cũ.

#### FE: Ward mặc định và history chỉ bật khi chọn thủ công

Các block dưới đây là đề xuất chưa triển khai. Giữ state `selection.wardId` hiện có cho lựa chọn
thủ công, không tự set nó bằng Ward đầu tiên khi API danh mục trả về.

`source/client/src/hooks/useLocations.ts` — thay phần tính Ward/return liên quan:

```typescript
const wards = provinceId && wardCatalog.provinceId === provinceId ? wardCatalog.options : [];
const selectedWard = wards.find((row) => row.id === selection.wardId) ?? null;
const effectiveWard = selectedWard ?? wards[0] ?? null;
const selectedWardId = selectedWard?.id ?? null;
const effectiveWardId = effectiveWard?.id ?? null;
const historyEnabled = selectedWardId !== null;
```

Trả các trường sau từ hook cùng danh mục/loading/error và các action hiện có:

```typescript
selectedWardId,
effectiveWardId,
effectiveWard,
historyEnabled,
```

`selectProvince` vẫn đặt `{ provinceId: id || null, wardId: null }`; `selectWard` chỉ đặt một ID
hợp lệ từ danh sách Ward hiện tại, hoặc null khi chọn option mặc định. Không dùng effect tự chọn
Ward đầu tiên như lựa chọn thủ công.

`source/client/src/App.tsx` — cấu hình hook và dropdown, chưa triển khai:

```tsx
const locations = useLocations();
const weather = useWeather(locations.effectiveWardId, {
  historyEnabled: locations.historyEnabled,
});

<label className="location-field">
  <span>Phường / Xã</span>
  <select
    value={locations.selectedWardId ?? ""}
    disabled={!locations.provinceId || locations.wardLoading || !locations.wards.length}
    onChange={(event) => locations.selectWard(event.target.value)}
  >
    <option value="">
      {locations.wardLoading ? "Đang tải phường/xã…" :
        !locations.provinceId ? "Chọn tỉnh/thành trước" :
        locations.effectiveWard
          ? `Mặc định: ${locations.wards[0].name} — chưa chọn thủ công`
          : "Chưa có phường/xã"}
    </option>
    {locations.wards.map((ward) => <option key={ward.id} value={ward.id}>{ward.name}</option>)}
  </select>
</label>
```

Tiêu đề current hiển thị `locations.effectiveWard?.name`; context ghi tỉnh/thành đang chọn. Nút
làm mới preview kiểm tra `effectiveWardId`, không kiểm tra selectedWardId vì chế độ mặc định vẫn
được xem preview. Thay mọi tham chiếu `locations.wardId/locations.ward` trong các block App đề xuất
bằng `locations.effectiveWardId/locations.effectiveWard` tương ứng; riêng value dropdown dùng selectedWardId.

History section phải được render có điều kiện — chưa triển khai:

```tsx
{locations.historyEnabled && (
  <section className="glass history">
    <div className="section-heading">
      <h2>Lịch sử quan sát</h2><span>{weather.history.length} / 60 bản tin</span>
    </div>
    <div className="table-wrap" tabIndex={0} role="region" aria-label="Bảng lịch sử thời tiết">
      <table>
        <thead><tr><th>Thời gian</th><th>Nhiệt độ</th><th>Độ ẩm</th><th>Mưa</th></tr></thead>
        <tbody>
          {weather.history.map((record) => <tr key={record.id}>
            <td>{time(record.observed_at)}</td><td>{record.temperature} °C</td>
            <td>{record.humidity}%</td><td>{record.rainfall} mm/h</td>
          </tr>)}
          {!weather.history.length && <tr><td colSpan={4}>Chưa có lịch sử cho địa điểm này.</td></tr>}
        </tbody>
      </table>
    </div>
  </section>
)}
```

`source/client/src/hooks/useWeather.ts` — signature/khóa history đề xuất, chưa triển khai:

```typescript
export function useWeather(
  wardId: string | null,
  { historyEnabled = false }: { historyEnabled?: boolean } = {},
) {
  const historyKey = historyEnabled ? wardId : null;
  // Current, preview and WS effects depend on wardId, not historyEnabled.
  // History has its own effect, cancellation and records keyed by historyKey.
}
```

Tách effect history riêng để việc chọn thủ công Ward đầu tiên chỉ bật history, không reset
current/preview hoặc reconnect WS của cùng Ward. Trong effect history, guard nằm trước mọi GET:

```typescript
useEffect(() => {
  setHistoryState({ wardId: historyKey, records: [], error: "" });
  if (!historyKey) return;
  let disposed = false;
  const controller = new AbortController();
  const refreshHistory = async () => {
    try {
      const records = await api<PaginatedData<Observation>>(
        `/wards/${encodeURIComponent(historyKey)}/weather/history?page_size=60`, controller.signal,
      );
      if (!disposed) setHistoryState((previous) => ({
        wardId: historyKey,
        records: mergeHistory(
          previous.wardId === historyKey ? previous.records : [],
          records.results.filter((row) => row.ward_id === historyKey),
        ),
        error: "",
      }));
    } catch (error) {
      if (!disposed) setHistoryState((previous) => ({
        ...previous,
        error: error instanceof Error ? error.message : "Không tải được lịch sử.",
      }));
    }
  };
  void refreshHistory();
  const timer = setInterval(() => { void refreshHistory(); }, 60000);
  return () => {
    disposed = true;
    controller.abort();
    clearInterval(timer);
  };
}, [historyKey]);
```

Khởi tạo state history riêng bằng useState với `{wardId: null, records: [], error: ""}` và type
records là Observation[]. Hook chỉ trả history ra UI khi cả cờ lẫn khóa đều khớp:

```typescript
const visibleHistory = historyEnabled && historyState.wardId === wardId
  ? historyState.records : [];
```

Callback WS có thể cập nhật current/cảnh báo ở chế độ mặc định, nhưng chỉ merge vào historyState
khi khóa history đang active khớp incoming.ward_id. Dùng ref/callback cập nhật theo historyKey để
không giữ closure cũ khi chọn thủ công chính Ward mặc định. Reconnect chỉ gọi refreshHistory khi
historyKey đang active. Tắt history phải hủy cả request cũ và ref refresh; mọi response muộn bị bỏ.
Không gọi history từ refresh current hoặc refresh forecast ngoài effect/callback có guard này.

`source/client/src/lib/api.ts` — Forecast interface đề xuất, chưa triển khai:

```typescript
export interface Forecast {
  ward_id: string;
  provider: "open_meteo";
  method: "open_meteo_hourly";
  data_kind: "model_forecast";
  target_at: string;
  fetched_at: string;
  predicted_temperature: number;
  predicted_humidity: number;
  predicted_wind_speed: number;
  precipitation_mm: number;
  interval_seconds: 3600;
}
```

`source/client/src/App.tsx` — phần card thay baseline, chưa triển khai:

```tsx
<section className="glass forecast">
  <h2>{forecast ? `Dự báo ${time(forecast.target_at)}` : "Dự báo giờ kế tiếp"}</h2>
  <div className="forecast-line">
    <strong>{forecast?.predicted_temperature ?? "—"}<span>°C</span></strong>
  </div>
  {forecast ? <>
    <p>Độ ẩm {forecast.predicted_humidity}% · Gió {forecast.predicted_wind_speed} km/h</p>
    <p>Giáng thủy giờ kết thúc lúc {time(forecast.target_at)}: {forecast.precipitation_mm} mm</p>
    <small>Open-Meteo · Dữ liệu dự báo mô hình · Lấy lúc {time(forecast.fetched_at)}</small>
  </> : <p>{forecastError || "Chưa có dữ liệu dự báo cho phường/xã này."}</p>}
</section>
```

`useWeather.ts`: giữ cơ chế wardId/disposed/AbortController và mergeHistory đã có. Thêm
forecastError riêng, tách refreshForecast khỏi refreshCurrentHistory; bỏ gọi forecast mỗi khi nhận
weather.update. Forecast chỉ lấy khi preview của Ward được hiển thị hoặc người dùng bấm làm mới.
Không tạo timer forecast hoặc tự retry forecast theo lịch. Cleanup hủy request. Không để response
Ward cũ ghi vào state Ward mới. API lấy history không được kéo theo việc gọi forecast/provider.

Ví dụ phần refreshForecast trong `useWeather.ts` — chưa triển khai. Bổ sung `forecastError: string`
và `forecastLoading: boolean` vào WeatherState, khởi tạo rỗng/false trong empty(); lấy chúng từ hook
trong Dashboard. Đoạn này dùng update(), base, abort, disposed cùng effect Ward đã có:

```typescript
let forecastRefreshing = false;
const refreshForecast = async () => {
  if (disposed || forecastRefreshing) return;
  forecastRefreshing = true;
  update((previous) => ({ ...previous, forecastLoading: true, forecastError: "" }));
  try {
    const prediction = await api<Forecast>(`${base}/forecast`, abort.signal, "no-store");
    if (disposed || prediction.ward_id !== wardId) return;
    update((previous) => ({ ...previous, forecast: prediction, forecastError: "" }));
  } catch (error) {
    if (!disposed) update((previous) => ({
      ...previous, forecast: null,
      forecastError: error instanceof Error ? error.message : "Không tải được dự báo.",
    }));
  } finally {
    forecastRefreshing = false;
    if (!disposed) update((previous) => ({ ...previous, forecastLoading: false }));
  }
};
// Run when the Ward preview is viewed; never from timers or socket callbacks.
void refreshForecast();
```

Trong hook, giữ một ref `{ wardId, run: refreshForecast }` để cung cấp thao tác requestForecast cho
nút làm mới; chỉ chạy khi ref.wardId khớp wardId hiện tại và chưa disposed. Cleanup xóa ref của
effect cũ. Không dùng thao tác làm mới forecast để reconnect WS hoặc xóa current/history.
Nút làm mới trên card preview — chưa triển khai:

```tsx
<button type="button" disabled={!locations.effectiveWardId || forecastLoading} onClick={requestForecast}>
  {forecastLoading ? "Đang lấy dự báo…" : "Làm mới dự báo"}
</button>
```

`source/client/src/lib/api.ts` bổ sung tùy chọn cache cho fetch; các call current/history giữ
mặc định, forecast truyền "no-store" — chưa triển khai:

```typescript
export async function api<T>(
  path: string, signal?: AbortSignal, cache: RequestCache = "default",
): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { signal, cache });
  const body = await response.json().catch(() => null);
  if (!response.ok || body?.success !== true) {
    throw new ApiError(
      body?.error?.message || `Không tải được dữ liệu (${response.status}).`, response.status,
    );
  }
  return body.data as T;
}
```

Bỏ request forecast khỏi refresh current/history, khỏi callback socket.onmessage, socket reconnect
và khỏi mảng lỗi chung. Current đọc DB theo effectiveWardId; history có effect riêng theo historyKey
và chỉ gọi khi historyEnabled=true. Timer REST 60 giây luôn được phép đọc current của Ward đang
hiển thị, nhưng không được gọi history ở chế độ chỉ chọn tỉnh hoặc tự kích hoạt forecast.

### 5.5. Test code dự kiến

Các test sau là đề xuất chưa viết vào source/chưa chạy.

`source/server/tests/test_forecast_provider.py`:

```python
from datetime import UTC, datetime

import pytest

from app.services.forecast import ForecastUnavailable, next_hour, parse_hourly


@pytest.fixture
def hourly_payload():
    times = [int(datetime(2026, 11, 4, hour, tzinfo=UTC).timestamp()) for hour in (2, 3, 4)]
    return {
        "hourly_units": {
            "time": "unixtime", "temperature_2m": "°C", "relative_humidity_2m": "%",
            "wind_speed_10m": "km/h", "precipitation": "mm",
        },
        "hourly": {
            "time": times, "temperature_2m": [25, 29.1, 30],
            "relative_humidity_2m": [80, 79, 78], "wind_speed_10m": [10, 12.3, 15],
            "precipitation": [0, 0.2, 0.5],
        },
    }


def test_forecast_uses_next_provider_hour_instead_of_copying_current(hourly_payload):
    now = datetime(2026, 11, 4, 2, 20, tzinfo=UTC)  # 09:20 tại Việt Nam
    target = next_hour(now)
    result = parse_hourly("00004", hourly_payload, target, now)
    assert target == datetime(2026, 11, 4, 3, tzinfo=UTC)
    assert result.ward_id == "00004"
    assert result.predicted_temperature == 29.1
    assert result.predicted_humidity == 79
    assert result.precipitation_mm == 0.2
    assert result.interval_seconds == 3600
    assert result.method == "open_meteo_hourly"


def test_missing_target_hour_does_not_fall_back_to_current(hourly_payload):
    target = datetime(2026, 11, 4, 8, tzinfo=UTC)
    with pytest.raises(ForecastUnavailable):
        parse_hourly("00004", hourly_payload, target, datetime(2026, 11, 4, 2, tzinfo=UTC))


@pytest.mark.parametrize("value", [None, True, float("nan"), float("inf")])
def test_invalid_provider_value_is_rejected(hourly_payload, value):
    hourly_payload["hourly"]["temperature_2m"][1] = value
    with pytest.raises(ForecastUnavailable):
        parse_hourly(
            "00004", hourly_payload,
            datetime(2026, 11, 4, 3, tzinfo=UTC), datetime(2026, 11, 4, 2, 20, tzinfo=UTC),
        )
```

Test preview chỉ dùng chung HTTP đang chạy và lần xem mới gọi lại provider, thêm vào
`test_forecast_provider.py` — chưa triển khai:

```python
import asyncio
import httpx
from app.services.forecast import OpenMeteoForecast


def test_concurrent_preview_shares_inflight_but_later_preview_fetches_again(hourly_payload):
    calls = []
    now = datetime(2026, 11, 4, 2, 20, tzinfo=UTC)

    async def handler(request):
        calls.append(request)
        await asyncio.sleep(0.01)
        return httpx.Response(200, json=hourly_payload)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = OpenMeteoForecast(client, clock=lambda: now)
            try:
                assert calls == []  # Starting the service must not prefetch forecasts.
                values = await asyncio.gather(*[
                    service.get("00004", 21.04, 105.84) for _ in range(5)
                ])
                assert all(value.predicted_temperature == 29.1 for value in values)
                assert len(calls) == 1
                assert calls[0].url.params["latitude"] == "21.04"
                assert calls[0].url.params["longitude"] == "105.84"
                await service.get("00004", 21.04, 105.84)
                assert len(calls) == 2  # A later preview must fetch fresh provider data.
            finally:
                await service.aclose()

    asyncio.run(scenario())
```

Test API preview không ghi Observation — thêm vào test API Ward, chưa triển khai. Fixture
public_data sau refactor có Ward 003 hoạt động/có tọa độ nhưng chưa có observation:

```python
import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy import select

from app.db import Observation
from app.db.session import Session, engine
from app.main import app
from app.schemas.weather import ForecastOut


def test_forecast_preview_does_not_change_observations(public_data, client, monkeypatch):
    async def records():
        async with Session() as session:
            rows = (await session.execute(select(
                Observation.id, Observation.ward_id, Observation.temperature,
                Observation.humidity, Observation.wind_speed, Observation.rainfall,
                Observation.source, Observation.observed_at,
                Observation.created_at, Observation.updated_at,
            ).order_by(Observation.id))).all()
        await engine.dispose()
        return [tuple(row) for row in rows]

    before = asyncio.run(records())
    preview = ForecastOut(
        ward_id="003", target_at=datetime(2026, 11, 4, 3, tzinfo=UTC),
        fetched_at=datetime(2026, 11, 4, 2, 20, tzinfo=UTC),
        predicted_temperature=29.1, predicted_humidity=79,
        predicted_wind_speed=12.3, precipitation_mm=0.2,
    )
    service = SimpleNamespace(get=AsyncMock(return_value=preview))
    monkeypatch.setattr(app.state, "forecast_service", service)
    assert client.get("/api/v1/wards/003/weather/current").status_code == 404
    result = client.get("/api/v1/wards/003/weather/forecast")
    assert result.status_code == 200
    assert result.headers["Cache-Control"] == "no-store"
    assert result.json()["data"]["predicted_temperature"] == 29.1
    service.get.assert_awaited_once_with("003", 21.0, 105.0)
    assert asyncio.run(records()) == before
    assert client.get("/api/v1/wards/003/weather/history").json()["data"]["results"] == []
    assert client.get("/api/v1/wards/003/weather/current").status_code == 404
```

Bổ sung biến thể service.get ném ForecastUnavailable: HTTP 503 và snapshot rows trước/sau vẫn
bằng nhau. Test API current/history patch HTTP provider để fail nếu bị gọi, chứng minh hai API
này chỉ đọc DB. Test collector kiểm tra request có `current`, không có `hourly`, và payload gửi
TCP không chứa target_at/predicted_temperature. Các biến thể này bổ sung cho kiểm thử ở mục 6.

`source/server/tests/test_geographic_migration.py` — thêm test reset có giới hạn, dùng helper migrate
hiện có. Không dùng DB thật:

```python
def test_reset_only_observations_and_add_required_ward_fk(tmp_path):
    database = tmp_path / "ward-reset.db"
    migrate(database, "upgrade", "0003")
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "INSERT INTO provinces (id, name, dataset_version, is_active) "
            "VALUES ('01', 'Tỉnh A', 'test', 1)"
        )
        connection.execute(
            "INSERT INTO wards (id, province_id, name, dataset_version, is_active) "
            "VALUES ('001', '01', 'Phường A', 'test', 1)"
        )
        connection.execute(
            "INSERT INTO users (id, name, email, password_hash) "
            "VALUES (?, 'Test', 'test@example.com', 'test-only')", (str(uuid4()),)
        )
        connection.execute(
            "INSERT INTO observations "
            "(id, city, temperature, humidity, wind_speed, rainfall, source, observed_at) "
            "VALUES (?, 'hanoi', 25, 70, 10, 0, 'provider', '2026-11-04 00:00:00')", (str(uuid4()),)
        )
        before = {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
            for table in ("users", "provinces", "wards")
        }
    migrate(database, "upgrade", "head")
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        assert connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0
        for table, rows in before.items():
            assert connection.execute(f"SELECT * FROM {table} ORDER BY id").fetchall() == rows
        columns = {row[1]: row for row in connection.execute("PRAGMA table_info(observations)")}
        assert "city" not in columns
        assert columns["ward_id"][3] == 1
        assert any(
            row[2] == "wards" and row[3] == "ward_id" and row[4] == "id"
            for row in connection.execute("PRAGMA foreign_key_list(observations)")
        )
        statement = (
            "INSERT INTO observations "
            "(id, ward_id, temperature, humidity, wind_speed, rainfall, source, observed_at) "
            "VALUES (?, ?, 25, 70, 10, 0, 'provider', '2026-11-04 01:00:00')"
        )
        for ward_id in (None, "missing"):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(statement, (str(uuid4()), ward_id))
        connection.execute(statement, (str(uuid4()), "001"))
        assert connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1
```

Test lịch current bổ sung vào test collector — chưa triển khai, chỉ dùng clock giả, không đợi
15 phút thật và không gọi provider:

```python
import pytest


@pytest.mark.parametrize("duration", [20, 200])
def test_current_runs_every_900_seconds_independent_of_job_duration(duration):
    class Clock:
        now = 0.0

        def read(self):
            return self.now

    class Stop:
        stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, seconds):
            clock.now += seconds
            return self.stopped

    clock, stop = Clock(), Stop()
    starts = []

    def collect_cycle(*, cycle_start, deadline):
        starts.append(clock.now)
        assert deadline - cycle_start == 900
        clock.now += duration
        if len(starts) == 3:
            stop.stopped = True

    collector.run_current_schedule(collect_cycle, stop, clock=clock.read)
    assert starts == [0, 900, 1800]


def test_current_skips_old_ticks_without_catchup_burst():
    assert collector.next_current_due(0, 20) == 900
    assert collector.next_current_due(0, 200) == 900
    assert collector.next_current_due(0, 905) == 900
    assert collector.next_current_due(0, 1905) == 1800
```

`collector` trong test trên là biến module đã được nạp bằng importlib trong tests/test_provider.py
hiện có; thêm các test vào cùng file để dùng object đó, không tạo/import package production mới. Thêm regression test TCP còn pending/ACK sai: chỉ sender retry, số lần
provider fetch của các Ward khỏe không tăng tại giây 30/60; lần lấy tiếp theo ở chu kỳ 900 giây.

Các test single-flight/bounded concurrency, HTTP timeout/429 và end-to-end Ward stream sẽ dùng
httpx.MockTransport và fixture TCP/SQLite hiện có; không gọi provider/Neon trong unit tests.

## 6. Kế hoạch kiểm thử

Sau khi duyệt mới triển khai và chạy:

1. **Migration/reset:** seed observations city + users/provinces/wards trên DB tạm, chạy migration;
   observations cũ hết, các bảng còn lại giữ nguyên; schema khớp ORM, FK/not-null/index đúng.
   Test downgrade có Ward data phải dừng, không tự xóa. PostgreSQL staging dùng DB riêng khi cần.
2. **Current/history:** hai Ward cùng tên vẫn tách theo ID; source filter, thứ tự UTC, pagination,
   valid Ward rỗng và unknown/inactive Ward trả đúng contract. History chỉ đọc các mẫu từng lấy
   từ provider.current đã lưu. GET current/history không gọi provider và không làm thay đổi DB.
   Chuyển mốc giờ không tự INSERT forecast hoặc tạo bản ghi history mới. Các API công khai không cần JWT.
3. **Forecast:** fixture có nhiệt độ giờ kế tiếp khác current để tái hiện lỗi baseline trước sửa;
   chọn đúng giờ/tọa độ/đơn vị, qua ngày/qua giờ khi HTTP chậm; thiếu giờ, sai units, null/NaN,
   timeout/429/5xx trả 503; không fallback số liệu current. Chụp toàn bộ rows Observation trước/sau
   GET forecast (thành công và lỗi) phải giống nhau; không ghi forecast vào outbox hoặc localStorage.
4. **Preview theo yêu cầu/tải forecast:** không có request preview thì không gọi provider; các request
   đồng thời cùng key chỉ dùng chung HTTP đang chạy. Lần preview mới sau khi xong phải gọi provider
   lại, không dùng cache đã hoàn tất; response no-store. Ward khác không lẫn; tác vụ có giới hạn,
   tối đa 2 HTTP đồng thời; client hủy không làm hỏng request dùng chung; shutdown đóng client/tasks.
5. **Collector:** clock giả xác nhận chu kỳ lấy current 0 → 900 → 1800 giây, không cộng thời gian
   chạy job vào chu kỳ, không có fetch mới ở giây 30/60 khi TCP còn pending. Không chạy chồng job;
   quá tải/bỏ lỡ tick không chạy bù dồn. Hàng đợi đầy hoặc provider lỗi thì đợi kỳ tiếp theo, không
   làm process/sender chết. Query chỉ Ward/Province active có tọa độ; chọn --ward-id; batch đúng
   mapping; chỉ request/chuẩn hóa provider.current, không gửi hourly/forecast qua TCP. Response
   thiếu phần tử bị từ chối; UUID ổn định; outbox chỉ giữ current, sống qua restart.
6. **TCP/DB/WS:** split/coalesced frames, accepted/duplicate/conflict, ACK sai ID/EOF không xóa
   event; một kết nối gửi nhiều Ward; socket chỉ nhận Ward/source đã chọn. Lỗi một Ward không
   làm dừng toàn collector; lịch HTTP current mỗi 15 phút và retry TCP độc lập.
7. **Backend khi stream:** producer chạy trong process riêng, sender có rate limit, health/REST
   tiếp tục phản hồi khi nhiều TCP producer hoạt động; shutdown không chờ client mở vô hạn.
   Chỉ báo p50/p95 khi đã đo, không suy từ số test pass.
8. **Dashboard/browser:** kiểm tra thủ công trong trình duyệt với API/WS giả lập:
   - Chọn Province có từ hai Ward trở lên: current/cảnh báo/preview hiển thị Ward đầu tiên; không
     có DOM section history, không có tiêu đề/counter/placeholder và không phát request history.
   - Timer recovery/reconnect/event WS của Ward mặc định vẫn không gọi hoặc hiển thị history.
   - Chọn thủ công chính Ward đầu tiên: history xuất hiện và gọi đúng ID; current/WS/preview cùng
     Ward không bị reset hoặc gọi lại chỉ vì bật cờ history.
   - Chọn Ward thứ hai: current/preview/history/WS đúng Ward đó, bỏ response muộn Ward trước.
   - Đổi Province: history ẩn ngay, selection thủ công bị xóa; sau khi tải danh sách mới dùng Ward
     đầu tiên của Province mới, không dùng dữ liệu tỉnh cũ. Ward rỗng thì không gọi weather API.
   - Bỏ chọn Ward về mặc định: history biến mất và dừng request/recovery, kể cả đang có request
     history trả về muộn; current/preview quay về Ward đầu tiên.
   - Danh mục dài hơn một trang giữ đúng thứ tự; Ward đầu tiên thiếu current/tọa độ thì hiện lỗi/
     trạng thái trống của chính Ward đó, không chọn Ward kế tiếp để né lỗi.
   - Ward chưa có current nhưng có forecast; forecast 503 không xóa current/history đã bật;
     forecast chỉ gọi khi xem/làm mới, không do timer, qua giờ đích, reconnect hoặc event current.
   - Card ghi đúng target/fetched_at Asia/Ho_Chi_Minh; labels không còn baseline provider;
     dropdown và history có điều kiện hoạt động trên desktop/mobile.
9. **Checks bắt buộc:** `ruff check .`, `pytest -q` tại source/server; `npm run build` tại source/client.
10. **Smoke thật sau duyệt:** dùng tập Ward nhỏ, chạy một chu kỳ collector, kiểm chứng cùng event_id
    qua HTTP provider → outbox → TCP ACK → Observation → REST/WS → dashboard; không coi mock tests
    là bằng chứng provider thật/DB deployment đã chạy.

**Điểm bàn giao:** chờ duyệt plan này. Chưa reset observations, chưa thêm migration hoặc đổi
forecast/collector/backend theo tài liệu. Những thay đổi frontend đã có trước yêu cầu plan được
review cùng đợt triển khai, không tự ghi đè hay rollback chúng trong lượt lập plan.
