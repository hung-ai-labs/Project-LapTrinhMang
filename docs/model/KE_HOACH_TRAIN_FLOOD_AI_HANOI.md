# KẾ HOẠCH TRAINING FLOOD AI HÀ NỘI
## Dự báo nguy cơ ngập do mưa trước 1–7 ngày từ Open-Meteo, phục vụ cảnh báo theo phường và đoạn đường

**Phiên bản:** 1.0 — 12/11/2026  
**Phạm vi:** Hà Nội; chỉ Model A — ngập đô thị do mưa. **Không triển khai Model B dự báo lũ sông**.  
**Hiện trạng đầu vào:** Đã có pipeline lấy thời tiết Open-Meteo cho **7 ngày tương lai, độ phân giải 1 giờ**. Kế hoạch này **không yêu cầu viết lại** pipeline đó; bổ sung lưu bản dự báo theo lần phát hành, dữ liệu lịch sử, nhãn, GIS và training.

> **Kết luận thiết kế:** Train **LightGBM** cho nguy cơ **ngập theo phường/ngày** trước; dự báo riêng 7 khung 24 giờ từ thời điểm phát hành. Muốn trả lời chính xác “đoạn đường trước mặt có ngập không?”, phải có **nhãn quan trắc ở cấp đoạn đường** (mực nước, camera, điểm ngập được kiểm chứng) và dữ liệu địa hình/thoát nước đủ chi tiết. Không được dùng ảnh ngập NASA ~250 m hoặc lượng mưa Open-Meteo ~km để khẳng định một tuyến phố cụ thể chắc chắn khô hay ngập.

---

# 1. Mục tiêu sản phẩm và phạm vi chính xác

## 1.1. Luồng người dùng

1. Người dùng cho phép định vị GPS hoặc nhập tên đường/địa chỉ ở Hà Nội.
2. Backend chuẩn hóa tọa độ (WGS84), truy vấn **phường/xã hiện hành** và **đoạn đường gần vị trí đó**.
3. Hệ thống lấy bản dự báo thời tiết Open-Meteo mới nhất: 168 giờ sắp tới.
4. AI tính **nguy cơ có ngập do mưa** cho từng khoảng 24 giờ: `D+1` ... `D+7`.
5. Web trả về bản đồ rủi ro, lý do (ví dụ mưa cực lớn và vùng trũng), mức độ tin cậy, thời điểm dự kiến, bản tin chính thức và tình trạng quan trắc hiện tại **nếu có**.
6. Với điểm không có nhãn hoặc mô hình chưa được kiểm định ở cấp đường, hiển thị **“Chưa đủ dữ liệu để kết luận ở cấp đoạn đường”**, không hiển thị “Không ngập”.

## 1.2. Chia thành 3 cấp độ dự báo

| Cấp | Đơn vị không gian | Có thể làm ở phiên bản nào? | Output hợp lệ |
|---|---|---|---|
| **A0 – Nền rủi ro** | Điểm trũng/đoạn đường | V0, từ điểm ngập lịch sử + GIS | *Dễ ngập khi mưa lớn*, **không phải** xác suất đã hiệu chỉnh |
| **A1 – Dự báo phường** | 126 xã/phường Hà Nội sau sắp xếp 2025 | V1, **nếu đủ nhãn theo ngày** | `P(ít nhất 1 điểm ngập trong phường trong ngày D+k)` |
| **A2 – Dự báo đoạn đường** | Đoạn đường 50–200 m; ngắn/dài tùy dữ liệu | V2, **chỉ khi có nhãn tại đoạn đường** | `P(đoạn đường có ngập vào ngày D+k)` |
| **A3 – Hiện trạng** | Điểm trạm/camera | V1–V2 nếu có API hợp lệ | `Đang ngập / đang khô tại điểm đo`; **khác** dự báo |

Hà Nội có **126 đơn vị cấp xã (51 phường, 75 xã)** theo hệ thống hành chính sau 2025. Cần giữ `admin_version=2025` và mã đơn vị, không join lịch sử bằng tên phường cũ. Tên “phường” trong giao diện có thể dùng tự nhiên; trong schema phải hỗ trợ cả xã.

## 1.3. Định nghĩa thời gian dự báo

- Thời điểm dự báo: `issue_time` (ISO 8601, lưu UTC; hiển thị `Asia/Ho_Chi_Minh`).
- `D1 = [issue_time, issue_time + 24 giờ)`, `D2 = [issue_time + 24, +48 giờ)`, …, `D7 = [+144, +168 giờ)`.
- Đây là **7 cửa sổ 24 giờ liên tiếp**, không mặc nhiên là 7 ngày lịch tính từ 00:00.
- **Mục tiêu chính:** nhãn `is_flooded_in_window` = có ít nhất một lần ngập được xác minh **trong cửa sổ**.
- **Mục tiêu phụ:** số giờ ngập, độ sâu cao nhất, giờ bắt đầu (chỉ train nếu nguồn ghi nhận đủ chính xác).
- Chỉ có nhãn “ngập ngày 15/09” mà **không có giờ**: nên training theo **ngày lịch địa phương** hoặc chỉ dùng mẫu có cửa sổ hoàn toàn trùng ngày đó; không gán chính xác giờ ngập cho các cửa sổ cắt qua hai ngày.
- Đối với 7 ngày, lưu xác suất cho từng ngày và một xác suất “có ngập bất kỳ ngày nào trong 7 ngày” **nếu được huấn luyện/hiệu chỉnh riêng**; không cộng các xác suất ngày lại.

> Với nhãn thực tế theo **ngày lịch**, chọn **chế độ `target_local_date`** làm V1 để tận dụng nguồn nhãn, và chọn `issue_time` cố định (ví dụ mỗi ngày 07:00 giờ Việt Nam). Các cửa sổ 24 giờ trượt dùng sau khi có quan trắc theo giờ.

---

# 2. Lựa chọn model và lý do

## 2.1. Phương án khuyến nghị

### Model 0 — Baseline, bắt buộc trước AI

Dùng luật theo mưa dự báo và các điểm dễ ngập:

- `rain_24h`, `max_rain_1h`, `max_rain_3h`, mưa tích lũy 72 giờ và điểm ngập lịch sử.
- Tham chiếu các **kịch bản mưa/ngập trong Quyết định 2280/QĐ-UBND 2026 Hà Nội**; đây là **kịch bản/điểm nguy cơ**, không phải nhãn những ngày đã ngập.
- Có thể thêm baseline “chỉ dự báo ngập tại các điểm thường ngập khi mưa vượt ngưỡng”.
- Baseline phải được đo Recall, Precision và cảnh báo sai như AI.

### Model 1 — **LightGBM Binary Classifier** (chọn trước)

- Input là các **features dạng bảng** từ 168 giá trị mưa dự báo theo giờ, mưa trước đó, địa hình và lịch sử ngập của khu vực.
- Target `y_ward_day ∈ {0,1}`. Chỉ train khi nhãn đủ tin cậy; `NULL` bị loại khỏi loss.
- Hai lựa chọn:
  1. **Một model theo từng lead day (7 models)**: dễ diễn giải; chỉ dùng khi có đủ số mẫu cho từng ngày.
  2. **Một model gộp**, thêm `lead_day ∈ [1..7]`, mỗi hàng là `(issue_time, ward_id, lead_day)`; tốt khi dữ liệu ban đầu ít, nhưng phải kiểm định riêng D1..D7.
- **Đề xuất V1:** một LightGBM gộp theo lead-day + các baseline; chỉ tách 7 model nếu cải thiện test độc lập.
- Hiệu chỉnh xác suất bằng **Isotonic Regression** hoặc **Platt scaling**, fit trên validation theo thời gian, không fit lại trên test.
- Không tự ý gán `probability=0.9` thành “chắc chắn ngập”; mô hình phải chứng minh được calibration và độ phủ nhãn.

### Model 2 — Road-level LightGBM (chỉ mở sau khi đủ nhãn đường)

- Đơn vị: `road_segment_id`; target `y_segment_day`.
- Input: mưa của ô khí tượng chứa đoạn đường + địa hình tương đối + tuyến thoát nước + lịch sử chính đoạn đường + tình trạng cảm biến.
- Điều kiện **bắt buộc**: có mẫu dương **và âm được xác minh** tại cùng vùng quan sát; có nhãn theo thời gian; đủ sự kiện độc lập để đánh giá.
- Nếu không đủ: chỉ trả **rủi ro khu vực/phường** và **điểm hay ngập**; không sinh xác suất chính xác giả tạo cho một đoạn đường.

### Model 3 — TCN / LSTM, thử nghiệm sau

- Input `X_seq` có shape dự kiến `[N, 168, F_weather]` cho dự báo 168 giờ, cộng features tĩnh của vị trí.
- Dùng khi dataset có **nhiều trận mưa/ngập độc lập**, tương đối đủ nhãn theo thời gian.
- Chỉ giữ mô hình sâu nếu **vượt LightGBM trên tập test theo thời gian và trận mưa**. Không cần Transformer lớn cho MVP.

## 2.2. Không chọn ở V1

- **CNN/SegFormer trên ảnh vệ tinh:** học *đang có nước ở đâu* từ ảnh; không trực tiếp học *ngày mai đường phố ngập hay không* từ Open-Meteo.
- **LSTM/Transformer ngay từ đầu:** dễ overfit khi thiếu nhãn âm theo ngày; dữ liệu ngập Hà Nội chính xác mới là nút thắt.
- **Mô hình lũ sông/GloFAS:** ngoài phạm vi của dự án đã thống nhất.

---

# 3. Nguồn dữ liệu — đã xác minh điều gì, còn thiếu gì?

| ID | Nguồn | Cấu trúc / thời gian | Vai trò | Tình trạng truy cập / hạn chế |
|---|---|---|---|---|
| **W1** | [Open-Meteo Forecast API](https://open-meteo.com/en/docs) | JSON `hourly`, 7 ngày × 1 giờ | **Inference** | **Bạn đã lấy được 168 giờ**; kiểm tra mô hình và metadata |
| **W2** | [Open-Meteo Single Runs API](https://open-meteo.com/en/docs/single-runs-api) | Bản dự báo quá khứ nguyên một `run`; ECMWF IFS HRES từ **14/03/2024**, model khác chủ yếu từ **02/04/2026** | **Input train đúng thời điểm phát hành** | Cần lấy các run lịch sử + lưu `run_init_utc`; không dùng dữ liệu thực tế tương lai làm feature |
| **W3** | [Open-Meteo Previous Runs](https://open-meteo.com/en/docs/previous-runs-api) | Dự báo tại lead +1…+7 ngày, đa số từ 2024 | Benchmark sai số dự báo theo lead | Không thay thế hoàn toàn chuỗi dự báo đầy đủ của một lần phát hành |
| **W4** | [Open-Meteo Historical Weather](https://open-meteo.com/en/docs/historical-weather-api) | ERA5/ERA5-Land reanalysis | Mưa quá khứ / nghiên cứu khí hậu | Chỉ được dùng nếu giá trị thật sự đã có tại `issue_time`; reanalysis không phải quan trắc realtime mặc định |
| **L1** | **Hà Nội – Quyết định 5695/QĐ-UBND ngày 12/10/2026**, Phụ lục 01, mục 129 và 130: [văn bản](https://thuvienphapluat.vn/van-ban/Cong-nghe-thong-tin/Quyet-dinh-5695-QD-UBND-2026-du-lieu-mo-va-du-lieu-dung-chung-Ha-Noi-729327.aspx) | Danh mục **dữ liệu mở** điểm ngập: tên đường/khu vực, vị trí, thời gian xuất hiện, mức độ, trạng thái; dữ liệu thoát nước | **Nguồn nhãn cấp đường ưu tiên số 1** | **Đã kiểm chứng danh mục**, **chưa xác minh endpoint tải lịch sử và quyền truy cập tự động**; “API/JSON” là định dạng dự kiến/công bố |
| **L2** | [iHanoi – Bản đồ mưa ngập (09/2026)](https://thanglong.baochinhphu.vn/chinh-thuc-ra-mat-mini-app-ban-do-mua-ngap-tren-ihanoi-103260903160946604.htm), nguồn trạm HSDC | Mưa, độ sâu nước, tọa độ điểm đo, cập nhật gần thời gian thực | **Nhãn dương/âm khi cảm biến hoạt động** | Có API tích hợp với iHanoi theo tin chính thức, **không đồng nghĩa API cho bên thứ ba đã mở công khai**; cần thỏa thuận dùng dữ liệu/lưu lịch sử |
| **L3** | [Quyết định 2280/QĐ-UBND 2026](https://xaydungchinhsach.chinhphu.vn/ke-hoach-chong-ngap-ung-noi-thanh-ha-noi-nam-2026-119260504105822803.htm) | Kịch bản mưa 50–70, 70–100, >100 mm/h; **11/71/220 điểm có nguy cơ** tương ứng | Danh sách vị trí ưu tiên, baseline và feature `historic_hotspot` | **Không phải nhãn theo ngày**; các con số là kịch bản, không gán tất cả các điểm là ngập thực tế |
| **L4** | [Nghiên cứu Hà Nội 2012–2018](https://www.mdpi.com/2073-4441/12/3/879) | 21 trận mưa gây ngập, ~148 điểm ngập từ báo cáo | Nhãn dương lịch sử, kiểm tra vị trí | Không có negative đầy đủ; khoảng thời gian chưa chồng lên Single Runs ECMWF 2024+ |
| **L5** | [Nghiên cứu Hà Nội 2025 về ảnh Sentinel-1](https://www.mdpi.com/2071-1050/17/23/10763) | Ảnh radar 2015–2024, điểm ngập tham chiếu | Thiết kế bản đồ ngập và kiểm tra hotspots | Các lớp GIS xử lý có thể phải liên hệ tác giả; không giả định file train đã mở tải |
| **L6** | [NASA MODIS MCDWD_L3](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/MCDWD_L3) | Raster ngập hằng ngày **2003–2025**, ~250 m | **Nhãn phụ diện rộng, quality mask** | Không thể làm ground truth đoạn đường; cloud/shadow; NASA Earthdata |
| **L7** | [Copernicus Global Flood Monitoring](https://catalogue.services.eodc.eu/collections/GFM) | Radar Sentinel-1 ~20 m, thời điểm vệ tinh đi qua (không phải mỗi ngày) | Nhãn phụ diện rộng và xác minh các trận ngập lớn | Không phải xác minh mọi đường đô thị; phụ thuộc mask loại trừ/quality |
| **G1** | [Danh sách 126 xã/phường Hà Nội](https://xaydungchinhsach.chinhphu.vn/sap-xep-dvhc-danh-sach-126-xa-phuong-moi-cua-ha-noi-119250622193659228.htm) | Tên/mã chính thức của 126 đơn vị | Mapping GPS → xã/phường | Cần **polygon GeoJSON/GPKG chuẩn**, không chỉ tên hoặc ảnh bản đồ |
| **G2** | [OpenStreetMap](https://www.openstreetmap.org/) | Đường và hình học đường (`highway`, `name`, `geometry`) | Mapping GPS → `road_segment_id` | Không đồng nghĩa dữ liệu ngập, cao độ mặt đường hoặc cống chính xác |
| **G3** | [Copernicus DEM GLO-30](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM), [ESA WorldCover 10 m](https://esa-worldcover.org/en/data-access) | DSM ~30 m; bản đồ lớp phủ 10 m | Feature tĩnh về địa hình, xây dựng | DSM không phải cao độ chuẩn của mặt đường; vùng trũng đô thị cần khảo sát/cao độ chi tiết |

**Mức độ xác minh hiện tại (12/11/2026):**
- Đã kiểm tra **tài liệu công bố và danh mục** của nguồn L1/L2/L3.
- **Chưa tải được/không xác minh được API công khai** xuất lịch sử theo ngày/giờ cho 126 xã/phường; chưa có bằng chứng dataset “dry/flood daily for every street” tải ngay.
- NASA/Sentinel có thể **trích nhãn quan sát hợp lệ** theo pixel nhưng **không đủ** để tạo `dry_verified` cho từng đường phố.
- **Bước quan trọng nhất trước training:** xin/khai thác hợp lệ lịch sử điểm ngập và cảm biến từ HSDC hoặc nguồn dữ liệu mở được cung cấp thực tế.

---

# 4. Cấu trúc dữ liệu thô và các bảng cần xây dựng

Thiết kế **7 bảng nguồn** + **2 bảng nhãn** + **2 bảng training**. Dùng `Parquet` cho dữ liệu lớn, `PostgreSQL + PostGIS` cho GIS và truy vấn thời gian; JSON gốc luôn giữ để kiểm tra lại.

## 4.1. Bảng `weather_forecast_hourly` — INPUT TỪ OPEN-METEO

**Một hàng = một điểm lưới thời tiết, một lần phát hành, một giờ mục tiêu.**  
Với 7 ngày, một run tại một điểm đại diện có khoảng **168 hàng/điểm** (kiểm tra phạm vi trả về và timestamp thực tế).

| Cột chuẩn hóa | Kiểu | Đơn vị | Nguồn | Ghi chú |
|---|---|---|---|---|
| `weather_run_id` | string | — | Sinh nội bộ | ID duy nhất của lần lấy |
| `weather_model` | string | — | Open-Meteo | Cố định model khi backtest; **không để “best_match” không kiểm soát** |
| `run_init_utc` | timestamp | UTC | Single Runs | Giờ khởi tạo, **chưa phải giờ công bố** |
| `forecast_available_at_utc` | timestamp | UTC | Metadata/log | Giờ dự báo thật sự có thể được xem tại thời điểm đó |
| `issue_time_utc` | timestamp | UTC | Pipeline | Lúc hệ thống ra quyết định; `available_at <= issue_time` |
| `weather_point_id` | string | — | GIS | Điểm lưới/điểm truy vấn thời tiết |
| `latitude`, `longitude` | float | độ | Open-Meteo | Tọa độ ô dữ liệu được trả về (khác điểm GPS có thể) |
| `valid_time_utc` | timestamp | UTC | Open-Meteo | Giờ mà dự báo áp dụng |
| `lead_hours` | int | giờ | Tính | Từ `issue_time` đến `valid_time` |
| `precipitation` | float | mm/giờ | Open-Meteo `hourly.precipitation` | Mưa + phần nước tương đương khác theo biến nguồn |
| `rain` | float | mm/giờ | `hourly.rain` | Mưa, không tính hai lần `rain` và `precipitation` |
| `showers` | float? | mm/giờ | `hourly.showers` | Tùy model hỗ trợ |
| `precipitation_probability` | float? | % | Forecast nếu có | **Không giả định mọi model có trường này** |
| `temperature_2m` | float | °C | Open-Meteo | Bổ sung |
| `relative_humidity_2m` | float | % | Open-Meteo | Bổ sung |
| `pressure_msl` | float? | hPa | Open-Meteo | Áp suất mực nước biển |
| `wind_speed_10m` | float? | km/h hoặc m/s | Open-Meteo | Ghi rõ unit lấy từ API |
| `cloud_cover` | float? | % | Open-Meteo | Feature phụ |
| `soil_moisture_*` | float? | m³/m³ | Open-Meteo | **Tên độ sâu thay đổi theo model/API**; chuẩn hóa sau khi kiểm tra response |
| `et0_fao_evapotranspiration` | float? | mm | Open-Meteo | Chỉ nếu endpoint/model hỗ trợ |
| `raw_api_version` | string | — | Pipeline | Version, URL query/hash để tái tạo |

**Quan trọng:** Dùng `forecast_hours=168` hoặc lọc 168 giờ kể từ `issue_time` nếu API/model hỗ trợ; `forecast_days=7` có thể trả 7 **ngày lịch từ 00:00**, không nhất thiết là đúng 168 giờ tiếp theo kể từ lúc request.

**Ví dụ schema JSON sau normalize (GIẢ LẬP):**

```json
{
  "weather_run_id": "ifs_2026-09-20T00Z",
  "weather_model": "ecmwf_ifs",
  "run_init_utc": "2026-09-20T00:00:00Z",
  "forecast_available_at_utc": "2026-09-20T06:00:00Z",
  "issue_time_utc": "2026-09-20T07:00:00Z",
  "weather_point_id": "wx_001",
  "valid_time_utc": "2026-09-21T07:00:00Z",
  "lead_hours": 24,
  "rain": 5.2,
  "relative_humidity_2m": 89.0
}
```

`forecast_available_at_utc` trong ví dụ là giá trị minh họa; phải lấy từ log vận hành/điều kiện phát hành thực tế chứ không mặc định cộng 6 giờ cho mọi run.

## 4.2. Bảng `weather_observations_hourly` — MƯA QUÁ KHỨ ĐÃ BIẾT TẠI T

| Cột | Ví dụ kiểu | Nguồn ưu tiên |
|---|---|---|
| `station_id`, `latitude`, `longitude` | string, float | Trạm quan trắc địa phương |
| `observed_at_utc` | timestamp | Thời điểm đo |
| `available_at_utc` | timestamp | **Thời điểm dữ liệu có thể dùng** |
| `rain_mm` | float | Lượng mưa đo, mm/giờ |
| `water_depth_cm` | float?, nếu trạm đo ngập | HSDC/sensor |
| `qc_flag` | enum | OK, SUSPECT, MISSING |
| `source` | string | Nhà cung cấp |

- Nếu dùng dữ liệu reanalysis/historical từ Open-Meteo thay cho mưa đo: phải gắn `source=REANALYSIS` và tránh sử dụng các giá trị được xử lý lại **sau issue_time** trong backtest “như thực tế”.
- `available_at_utc <= issue_time_utc` mới được dùng làm feature tại thời điểm đó.
- Không ghép `water_depth_cm` của tương lai vào input. Nó sẽ trở thành **nhãn**.

## 4.3. Bảng `admin_wards` — RANH GIỚI HÀ NỘI

| Cột | Nội dung |
|---|---|
| `ward_id` | Mã địa giới hành chính chính thức |
| `ward_name` | Tên xã/phường |
| `admin_type` | `phuong` / `xa` |
| `admin_version` | `2025` |
| `geometry` | Polygon/MultiPolygon WGS84 hoặc CRS nhất quán |
| `valid_from`, `valid_to` | Khoảng hiệu lực của ranh giới |
| `area_km2`, `centroid` | Tính GIS |

**Không dùng centroid để quyết định xã/phường của GPS**: dùng phép `Point-In-Polygon`. Centroid chỉ để chọn điểm khí tượng đại diện ban đầu.

## 4.4. Bảng `road_segments` — VỊ TRÍ NGƯỜI DÙNG ĐANG ĐỨNG

Đề nghị cắt graph OSM thành những **đoạn 50–200 m**, chia thêm tại giao lộ, đổi dốc, thay đổi thoát nước. Đây là thông số khởi tạo, phải điều chỉnh theo độ chi tiết nhãn.

| Cột | Nội dung |
|---|---|
| `road_segment_id` | ID nội bộ ổn định, liên kết OSM gốc |
| `osm_way_id`, `road_name`, `road_type` | ID và phân loại đường |
| `ward_id` | Xã/phường chứa phần lớn đoạn; đường băng qua biên giới có mapping nhiều ward |
| `geometry` | LineString |
| `length_m`, `road_width_m?` | Dài và rộng, nếu có |
| `road_elevation_m?`, `local_rel_elevation_m?` | Cao độ/độ trũng tương đối; ghi chất lượng nguồn |
| `distance_to_drain_m?`, `drain_capacity?` | Khi có dữ liệu cống |
| `historical_flood_count_asof` | Chỉ tính từ **sự kiện trước issue_time**, chống leakage |
| `feature_quality` | `high/medium/low` |

## 4.5. Bảng `flood_events` — GỐC NHÃN TỪ BÁO CÁO/HIỆN TRƯỜNG

**Một hàng = một sự kiện ngập đã ghi nhận tại một vị trí**, không tự sinh hàng không ngập.

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `event_id` | string | ID duy nhất |
| `source` | enum | `HANOI_OPEN_DATA`, `HSDC`, `FIELD`, `VERIFIED_REPORT`, `NEWS`, `SATELLITE` |
| `source_record_id`, `source_url` | string | Truy vết bản gốc |
| `lat`, `lon`, `geometry` | float, geometry | Vị trí |
| `location_text`, `road_segment_id?`, `ward_id?` | string | Gắn GIS; có thể chưa xác định |
| `start_at_utc`, `end_at_utc` | timestamp? | Giờ đầu/cuối ngập; **nullable** |
| `event_local_date` | date? | Nếu báo cáo chỉ có ngày |
| `depth_cm_min`, `depth_cm_max` | float? | Độ sâu, nếu được đo hoặc báo cáo |
| `cause` | enum | `rain`, `river`, `tidal`, `drain_failure`, `mixed`, `unknown` |
| `event_status` | enum | `confirmed`, `possible`, `rejected` |
| `time_precision` | enum | `minute`, `hour`, `day`, `unknown` |
| `geo_precision_m` | float? | Độ bất định vị trí |
| `reviewer`, `verified_at` | string, timestamp? | Ai kiểm chứng, khi nào |

**Lọc dự án:** `cause=rain` hoặc `mixed` có bằng chứng mưa; sự kiện sông tràn bờ thuần túy **không** là nhãn mục tiêu *urban rain-induced flood*. Với `cause=unknown`, tạm giữ vào kho nguồn nhưng chưa tự đưa vào nhãn chính.

## 4.6. Bảng `sensor_waterlevel_hourly` — NHÃN DƯƠNG/ÂM CHẤT LƯỢNG CAO

| Cột | Mô tả |
|---|---|
| `sensor_id`, `geometry`, `road_segment_id?` | Định danh + vị trí quan trắc |
| `observed_at_utc` | Giờ đo |
| `water_depth_cm` | Độ sâu trên mặt đường/điểm đo; chuẩn zero/reference |
| `sensor_status`, `quality_flag` | OK, OFFLINE, CALIBRATION, SUSPECT |
| `rain_mm?` | Lượng mưa cùng thời điểm nếu có |
| `available_at_utc`, `source` | Thời điểm xuất bản, nguồn |
| `is_flooded_at_sensor` | Nhãn suy ra **sau khi đã thống nhất ngưỡng sản phẩm** |

**Ngưỡng nghiên cứu gợi ý, không phải quy định pháp lý hay ngưỡng an toàn giao thông:**
- `<5 cm`: chưa xem là ngập đáng cảnh báo đối với điểm đo đang hoạt động **nếu chuẩn zero đúng**.
- `>=10 cm` liên tục ít nhất 2 lần đo hợp lệ: có ngập có ý nghĩa tại điểm đo.
- Khoảng `5–10 cm`: **không chắc / cần đánh giá**, không cưỡng ép thành `0`.
- Có thể thay đổi ngưỡng dựa trên cảm biến thực, báo cáo hiện trường, loại phương tiện. **Không tự tuyên bố một mức nước nào là an toàn cho người dùng**.
- Các ngưỡng trên chỉ là cấu hình pilot, cần kiểm định với chuyên gia địa phương. Phân loại “đang ngập” được phép tách khỏi ngưỡng đóng đường.

Điểm đo khô chỉ xác nhận **vùng đại diện của trạm**, không chứng minh cả phường hay mọi nhánh đường đều khô.

## 4.7. Bảng `satellite_flood_observations` — NHÃN PHỤ NASA/GFM

### NASA `MCDWD_L3` (2003–2025; ~250 m; daily)

Sử dụng **lớp 1 ngày** `FloodCS_1Day_250m` (có cloud-shadow mask) hoặc `Flood_1Day_250m`; đồng thời đọc `ValidCounts...` và các lớp chất lượng. **Không lấy lớp 2–3 ngày làm nhãn độc lập của đúng một ngày** vì đó là ảnh tổ hợp nhiều ngày.

Mã pixel NASA:

| Mã | Ý nghĩa | Xử lý làm nhãn |
|---|---|---|
| `0` | Không thấy nước | **Quan sát âm tính yếu ở pixel hợp lệ**, không phải `road_dry_verified` |
| `1` | Nước mặt thường xuyên | `permanent_water`, **loại khỏi nhãn ngập mới** |
| `2` | Ngập tái diễn | Dương tính **chỉ nếu sản phẩm/phiên bản có dùng mã này**, phân biệt seasonal flood |
| `3` | Ngập bất thường | Dương tính của *flood extent*, **không khẳng định đường phố ngập** |
| `255` | Không đủ quan sát | `NULL`, loại khỏi label loss |

Cần đọc `valid_counts`, loại pixel mây và chỗ không quan sát; tính `observable_ratio`, `flood_pixel_count`, `flood_area_ha_observed` **trong polygon xã/phường**, không tạo `dry=0` từ ảnh không có quan sát.

### Copernicus GFM (Sentinel-1 SAR, ~20 m)

Các lớp: `observed flood extent`, `observed water extent`, `reference water mask`, `exclusion mask`, `likelihood`. Ảnh theo **lượt vệ tinh**, không phải mọi ngày/giờ; radar có thể bỏ sót ngập giữa nhà cao tầng, nước dưới tán cây.

### Schema nhãn phụ gợi ý

```text
satellite_obs_id,source,acquired_at_utc,ward_id,
valid_pixel_count,total_pixel_count,observable_ratio,
flood_pixel_count,permanent_water_pixel_count,
flood_fraction_of_valid,quality_grade,
weak_flood_label,spatial_resolution_m
```

**Quy tắc:** `weak_flood_label` của vệ tinh **không được trộn làm `is_road_flooded`**. Có thể dùng làm:
- feature **độ dễ ngập lịch sử**, tính từ ảnh **trước ngày phát dự báo**;
- mục tiêu phụ của mô hình **ngập diện rộng**;
- tập kiểm tra/đối chiếu những sự kiện lớn.

---

# 5. Thiết kế nhãn training — phần quyết định thành công

## 5.1. Ba trạng thái bắt buộc

```text
1    = FLOODED_VERIFIED (có ngập, bằng chứng đủ tin cậy)
0    = DRY_VERIFIED     (không ngập ở phạm vi đã quan trắc hợp lệ)
NULL = UNKNOWN          (thiếu/không đủ bằng chứng)
```

**Không có báo cáo ngập ≠ đã được xác nhận không ngập.**  
**Không có pixel nước ≠ mọi con đường không ngập.**  
**Không có cảm biến ở đoạn đường ≠ đoạn đường đó khô.**

Nên lưu thêm:
- `label_scope` = `SENSOR_POINT` | `ROAD_SEGMENT` | `WARD_ANY_FLOOD` | `SATELLITE_AREA`.
- `label_source`, `label_quality` = `A/B/C/REJECT`, `positive_evidence_count`, `negative_coverage_ratio`.
- `is_observed`, `unknown_reason`, `cause`, `label_policy_version`.
- Nếu một số nguồn mâu thuẫn: `CONFLICT` → review hoặc `NULL`, **không bỏ qua dấu hiệu ngập đáng tin**.

## 5.2. Nhãn cấp đường: `road_segment_day_labels`

**Một hàng = một đoạn đường và một ngày mục tiêu hoặc cửa sổ 24 giờ.**

| Trường | Ví dụ (giả lập) | Ý nghĩa |
|---|---|---|
| `road_segment_id` | `road_000318` | ID đoạn |
| `target_local_date` | `2026-09-21` | Ngày cần dự báo |
| `label` | `1` | Đã xác nhận có ngập |
| `max_depth_cm` | `23` | Nếu có đo |
| `onset_at_utc` | `2026-09-21T02:15Z` | Giờ bắt đầu |
| `duration_minutes` | `90` | Nếu có ghi |
| `source` | `HSDC_SENSOR` | Ground truth gốc |
| `label_quality` | `A` | Độ tin cậy |
| `observation_coverage_ratio` | `0.98` | Tỷ lệ thời gian hợp lệ |
| `cause` | `rain` | Đúng bài toán |
| `label_policy_version` | `v1` | Phiên bản luật |

### Gán `label=1` cho đường khi:

- Có cảm biến đo ngập đã QC, xác định chính xác vị trí/độ sâu và thời gian; **hoặc**
- Có báo cáo chính thức/vị trí GPS/camera **được xác minh** đoạn đường, ngày, nguyên nhân ngập; **hoặc**
- Nhiều nguồn độc lập nhất quán sau review thủ công.

### Gán `label=0` cho đường khi:

- **Chính đoạn đường / vùng đo đại diện** được quan sát bằng cảm biến/camera hoặc khảo sát đã QC;
- Có độ phủ thời gian đủ tốt trong cửa sổ mục tiêu (khuyến nghị thử `>=90%`, nhưng phải đánh giá nguy cơ bỏ qua các đợt ngập ngắn);
- Không xuất hiện ngập theo ngưỡng đo đã thống nhất;
- Không mâu thuẫn với bản ghi dương cùng đoạn/vị trí.

### Gán `NULL` khi:

- Trạm mất kết nối, báo cáo chỉ có tên đường nhưng không xác định đoạn, không rõ thời điểm, hoặc ảnh vệ tinh bị che;
- Không có dữ liệu âm tính kiểm chứng;
- Chỉ có **dấu hiệu vệ tinh hoặc vị trí “hay ngập”** mà không có quan trắc cấp đoạn đường.

**Điểm kỹ thuật:** Không thể suy từ `một camera khô` thành `toàn bộ đoạn dài 200 m khô` nếu camera chỉ quan sát một điểm thấp. Hãy định nghĩa *vùng đại diện của cảm biến* bằng GIS/khảo sát, hoặc giữ `label_scope=SENSOR_POINT`.

## 5.3. Nhãn cấp phường: `ward_day_labels`

**Định nghĩa output rõ ràng:**

> `ward_any_flood=1` khi trong ngày/cửa sổ mục tiêu có **ít nhất một vị trí ngập do mưa được xác minh nằm trong phường**.

| Nhãn | Điều kiện |
|---|---|
| `1` | Có ít nhất một event cấp đường/điểm rõ thời gian + vị trí thuộc phường |
| `0` | Có **hệ thống giám sát đủ đại diện** đối với vùng dân cư/giao thông mục tiêu, không phát hiện ngập; yêu cầu độ phủ đã kiểm chứng |
| `NULL` | Không có event, nhưng cũng **không có quan trắc phủ đủ để xác nhận không ngập** |

**Rất quan trọng:** Nếu chỉ có một hoặc vài trạm ở một phường, thông thường **không đủ để gán `ward_any_flood=0`**, vì một điểm khác có thể ngập. Có thể thay đổi mục tiêu hẹp hơn thành `ward_monitored_sites_any_flood`: “ít nhất một điểm trong tập các điểm được giám sát ngập”. Khi đó nhãn âm có thể xác lập nếu **tất cả điểm được giám sát** có đủ dữ liệu. Không được gọi nhãn hẹp này là “cả phường không ngập”.

### Hai target nên lưu riêng để tránh đánh tráo bài toán

```text
y_monitored_hotspot_flood_day  # Có điểm ngập trong DANH SÁCH điểm giám sát
y_ward_any_flood_day          # Có ít nhất một nơi ngập trong toàn phường
```

- V1 có thể train target đầu nếu dữ liệu trạm đủ; giao diện phải nói rõ “nguy cơ tại các điểm giám sát”.
- Target thứ hai chỉ đủ điều kiện khi độ phủ nhãn và kiểm chứng không gian cho phép.

## 5.4. Phân biệt nhãn “mức độ ngập” và nhãn nhị phân

Có độ sâu đo thì tạo các mục tiêu riêng:

| Target | Định nghĩa |
|---|---|
| `y_flood_binary` | `0/1/NULL` theo chính sách nhãn |
| `y_max_water_depth_cm` | Hồi quy độ sâu lớn nhất trong ngày ở **điểm đo**; không suy ra độ sâu cả phường |
| `y_severity` | 0/1/2/3 theo **ngưỡng đã được nhóm và đơn vị quản lý phê duyệt** |
| `y_duration_min` | Thời gian ngập; chỉ dùng khi có thời gian bắt đầu/kết thúc |

Không tự tạo `depth_cm` từ lượng mưa hoặc diện tích pixel NASA. Lượng mưa 100 mm **không đồng nghĩa** độ sâu ngập đường 100 mm.

## 5.5. Hợp nhất và trọng số nhãn

| Cấp bằng chứng | Ví dụ | Training |
|---|---|---|
| **A — Confirmed direct** | Cảm biến nước hoạt động chuẩn, camera/biên bản hiện trường xác minh | Cho vào tập supervised chính |
| **B — Verified report** | Báo cáo cơ quan, ảnh video địa điểm/giờ được xác minh | Cho vào train tùy độ tin cậy; ghi rõ nguồn |
| **C — Weak proxy** | MODIS, GFM, điểm nóng lịch sử | Để **weak/pseudo label riêng**, không trộn vào nhãn trực tiếp cấp đường |
| **Unknown** | Không được báo cáo, mất cảm biến, mây | Không cho vào binary supervised loss |

Bắt buộc lưu **provenance** (nguồn chứng cứ) từng nhãn; không “gộp nhãn rồi xóa nguồn”.

---

# 6. Bảng training cuối cùng: chính xác X và y là gì?

## 6.1. `train_ward_day.parquet` — V1

**Một hàng = `(issue_time_utc, ward_id, lead_day)`**. Nếu một ngày mục tiêu được dự báo từ nhiều issue_time khác nhau thì có nhiều hàng, nhưng toàn bộ thuộc **cùng sự kiện/ngày đích** phải được nhóm khi split.

| Trường | Kiểu | Input/Target | Cách tạo |
|---|---|---|---|
| `issue_time_utc` | timestamp | ID | Thời điểm dự báo |
| `ward_id` | string | ID | GIS phường |
| `lead_day` | int 1..7 | Input | Ngày xa bao nhiêu |
| `target_date` | date | ID | Ngày mục tiêu |
| `weather_run_id`, `weather_model` | string | Audit/metadata | Run có sẵn tại issue_time |
| `rain_pred_target_24h` | float mm | **X** | Tổng mưa dự báo trong ngày mục tiêu |
| `rain_pred_target_max_1h` | float mm/h | **X** | Mưa lớn nhất của 1 giờ dự báo trong ngày |
| `rain_pred_target_max_3h` | float mm | **X** | Mưa 3 giờ lớn nhất trong ngày |
| `rain_pred_before_target_72h` | float mm | **X** | Mưa **dự báo** 72 giờ trước ngày mục tiêu (chỉ thời gian sau issue_time) |
| `rain_pred_hours_over_10mm` | int | **X** | Số giờ dự báo trên ngưỡng nghiên cứu |
| `rain_pred_next_7d_total` | float mm | **X tùy chọn** | Có sẵn lúc issue; nên thử ablation, nhưng không được dựa chủ yếu vào mưa **sau** ngày mục tiêu |
| `rain_observed_past_6h` | float? mm | **X** | Mưa đã có trước issue_time |
| `rain_observed_past_24h` | float? mm | **X** | Tổng mưa đã có |
| `rain_observed_past_72h` | float? mm | **X** | Mưa tích lũy trước đó |
| `soil_moisture_asof` | float? | **X** | Giá trị đã có tại issue; tùy model |
| `mean_relative_humidity_target` | float | **X** | Trung bình dự báo ngày mục tiêu |
| `ward_lowland_share` | float 0..1 | **X** | Diện tích tương đối trũng trong xã/phường |
| `ward_builtup_share` | float 0..1 | **X** | Tỷ lệ đất xây dựng |
| `historical_hotspot_count_asof` | int | **X** | Chỉ từ dữ liệu **trước issue_time** |
| `monitored_site_count_asof` | int | **X/QA** | Số điểm giám sát đang có |
| `label_observation_coverage` | float | **QA, không đưa vào model** | Mức phủ khi gán nhãn |
| `y_monitored_hotspot_flood_day` | 0/1/NULL | **y** | Từ điểm giám sát |
| `y_ward_any_flood_day` | 0/1/NULL | **y thay thế** | Chỉ khi đạt điều kiện vùng phủ |
| `label_quality`, `label_source` | enum | **QA, không đưa vào model** | Truy vết chứng cứ |
| `storm_event_group` | string | **Split only** | Nhóm sự kiện mưa/ngập |

**Không đưa `label_quality`, `source`, `future_observed_rain`, `measured_future_depth`, `target_date_report_count` vào input model.** Những cột đó có thể tiết lộ sự kiện tương lai.

## 6.2. `train_road_day.parquet` — V2

Ngoài features thời tiết, thêm:

```text
road_segment_id, ward_id, local_road_elevation,
relative_height_vs_neighborhood, road_slope,
upstream_catchment_area, distance_to_drain,
drain_capacity, road_builtup_density,
historical_road_flood_count_asof, camera_sensor_density_asof,
issue_time_utc, target_date, lead_day,
y_segment_flood_day, label_quality, label_source
```

Nếu `road_elevation` hoặc `drain_capacity` không tồn tại thì lưu `NULL`, thêm `quality_flag`, **không tự đoán giá trị**. DEM 30 m có thể dùng cho nguy cơ tương đối khu vực nhưng chưa đủ làm địa hình vi mô của vỉa hè và nắp cống.

## 6.3. Ba hàng ví dụ (hoàn toàn GIẢ LẬP)

| issue (VN) | ward | lead | mưa dự báo đích | mưa max 1h | nhãn | nguồn |
|---|---|---:|---:|---:|---|---|
| 20/09/2026 07:00 | `ward_demo_01` | 1 | 86 mm | 24 mm | `1` | Trạm A + camera đã QC |
| 20/09/2026 07:00 | `ward_demo_02` | 1 | 13 mm | 4 mm | `0`* | Tất cả điểm giám sát hợp lệ đều khô |
| 20/09/2026 07:00 | `ward_demo_03` | 1 | 45 mm | 13 mm | `NULL` | Không có trạm/báo cáo xác minh |

`0*` chỉ hợp lệ cho target **các điểm được giám sát**; **không thể nâng thành “toàn phường khô”** nếu chưa đủ quan trắc đại diện.

---

# 7. Cách dùng 7 ngày × 1 giờ Open-Meteo mà bạn đã lấy

## 7.1. Input lúc inference

Hệ thống hiện có `hourly.time[168]` và các mảng `hourly.precipitation`, `rain`, ... độ dài tương ứng (nếu lấy đúng 168 giờ tương lai). Giữ nguyên raw JSON, bổ sung:

```text
model / weather_model
retrieved_at_utc
forecast_available_at_utc (nếu biết)
issue_time_utc
latitude/longitude returned by Open-Meteo
hourly.time timezone -> UTC
hourly_units
source_model_version / run ID (nếu có)
```

Không sử dụng nhiều truy vấn GPS cách nhau 100 m để giả vờ thu được mưa 100 m: Open-Meteo dùng **ô mô hình khí tượng** lớn hơn đáng kể. Nhiều địa chỉ gần nhau có thể dùng chung một điểm lưới.

## 7.2. Input lúc train: quan trọng hơn inference

**Tuyệt đối không gọi Forecast API hôm nay để “lấy dự báo của ngày 15/09/2025”**. Dùng:

`https://single-runs-api.open-meteo.com/v1/forecast`

với `run=YYYY-MM-DDThh:mm` cho run ECMWF đã lưu và chọn thời điểm dự báo sau khi run **thực sự có thể được truy cập**. `run_init_utc` KHÔNG phải `issue_time`.

**Ví dụ endpoint minh họa (kiểm tra các biến được model hỗ trợ trước khi chạy):**

```text
https://single-runs-api.open-meteo.com/v1/forecast
  ?latitude=21.03
  &longitude=105.85
  &run=2025-09-01T00:00
  &models=ecmwf_ifs
  &hourly=precipitation,rain,relative_humidity_2m,temperature_2m,pressure_msl
  &timezone=Asia/Ho_Chi_Minh
  &forecast_days=7
```

- **Đây là mẫu cấu hình để triển khai**, không cam kết mọi tổ hợp tham số/biến đều tồn tại; test 1 request và lưu response.
- ECMWF IFS HRES Single Runs có archive từ 14/03/2024; phần lớn model khác trong Single Runs từ 02/04/2026.
- Giai đoạn lịch sử có thể ghép **NASA 2024–2025** với ECMWF Single Runs 2024–2025, nhưng nhãn NASA chỉ là **weak labels** cho ngập diện rộng, **không cấp đường**.
- Để train trên nhãn thực đường Hà Nội 2026, cần lịch sử các run tương ứng trong 2026 và thời gian ngập thật.
- Single Runs IFS có thể có thay đổi chu kỳ/model; lưu version để kiểm tra distribution shift.

## 7.3. Feature engineering theo giờ → ngày

Với ngày mục tiêu `target_date` hoặc khung `lead_day`:

```python
rain_target_sum_24h = sum(rain_at_valid_hours_in_target_window)
rain_target_max_1h  = max(rain_at_valid_hours_in_target_window)
rain_target_max_3h  = max(rolling_sum(rain, 3) within target_window)
rain_target_max_6h  = max(rolling_sum(rain, 6) within target_window)
rain_target_hours_gt_10 = count(hourly_rain > 10 mm)
rain_prev_24h_asof  = sum(observed_rain before issue_time within 24h)
```

**Các đặc trưng ưu tiên:**

| Mức | Đặc trưng | Vì sao |
|---|---|---|
| P0 | `rain_target_sum_24h`, `max_rain_1h`, `max_rain_3h`, `max_rain_6h` | Mưa lớn, mưa dồn cục bộ |
| P0 | `rain_past_24h`, `rain_past_72h` **đã biết** | Nền bão hòa trước trận |
| P0 | `lead_day`, `day_of_year_sin/cos`, `time_of_day` | Khác biệt theo mùa/thời hạn |
| P0 | `ward_id` hoặc features GIS, `lowland_share`, `builtup_share`, hotspot trước issue | Khác biệt khu vực |
| P1 | `soil_moisture` thực sự có sẵn, `et0`, độ ẩm, áp suất | Mô hình thủy văn đơn giản |
| P1 | mưa **từ issue đến trước target** theo dự báo | Mức tích nước trong vài ngày sắp tới |
| P2 | lượng mưa trạm, radar mưa địa phương, độ sâu thời gian thực | Tăng độ chính xác tại đường |
| P2 | cống/bơm/hồ điều hòa theo trạng thái hiện hành | Giải thích thoát nước đô thị |

**Chú ý thời gian:** Đối với dự báo D5, bạn có thể dùng lượng mưa *dự báo* ở D1–D4 trong cùng run; đây không phải leakage vì đều đã biết dưới dạng **dự báo** tại `issue_time`. Nhưng không được thay bằng lượng mưa **thực tế** đã xảy ra ở D1–D4 khi mô phỏng dự báo từ D0.

**Chú ý đặc biệt cho dữ liệu “1 giờ × 7 ngày”:** Đối với **ECMWF IFS HRES 9 km**, dữ liệu dự báo gốc là **1 giờ trong 90 giờ đầu**, sau đó **3 giờ**, rồi **6 giờ sau mốc 144 giờ**. Open-Meteo có thể **nội suy** thành mảng hourly nhất quán. Vì vậy D5–D7 có thể có 168 phần tử nhưng **không chứa 168 phép dự báo giờ độc lập có độ chính xác tương đương ngày 1**. Khi training, nên:
- ưu tiên đặc trưng tổng mưa 24 giờ, tối đa 6 giờ, mưa tích lũy nhiều ngày;
- so sánh D1–D3 với D4–D7 như các mức bất định khác nhau;
- đánh dấu `native_temporal_resolution_hours` và `interpolated_hourly=true/false` nếu biết, đặc biệt khi tính `max_rain_1h` cho ngày 5–7;
- không diễn giải mưa nội suy từng giờ ở ngày 7 thành dự báo chính xác thời điểm đường ngập.

Nguồn: [ECMWF/Open-Meteo model documentation](https://open-meteo.com/en/docs/ecmwf-api).


---

# 8. Xây dựng dataset từ nguồn thật: ETL & QA

## Bước 8.1 — Lấy bản đồ địa giới và đường

1. Lấy danh mục mã + **đa giác** 126 xã/phường; kiểm tra hình học, hệ tọa độ, độ phủ và không chồng lấp sai.
2. Tải road network OSM cho địa giới Hà Nội; gán `road_segment_id`, lưu `osm_way_id` để cập nhật sau.
3. Điểm ngập cũ (2012–2024): **spatial join theo tọa độ** sang ranh giới hiện tại; không join bằng tên huyện/phường cũ.
4. Lưu ranh giới/đường dưới dạng `GeoPackage`/`GeoParquet` và PostGIS.

## Bước 8.2 — Thu thập nhãn địa phương

**Đầu việc ưu tiên cao nhất:** xác định API/nguồn tải mục 129, 130 trong danh mục dữ liệu mở Hà Nội; xác định điều kiện truy cập lịch sử trạm HSDC được tích hợp vào iHanoi.

Cần **yêu cầu tối thiểu**:
- Danh sách trạm/điểm ngập: `id`, `lat`, `lon`, `road_name`, `ward_code`.
- Dữ liệu **lịch sử** theo giờ/5–15 phút nếu có: `timestamp`, `depth_cm`, `quality`, `sensor_status`.
- Danh sách sự kiện: giờ bắt đầu/kết thúc, mức độ, nguyên nhân, mô tả.
- Danh sách vị trí cố định + đoạn đường đại diện.
- Ghi rõ thời gian lưu, quyền sử dụng, hạn chế khai thác/dữ liệu cá nhân.

**Nếu chỉ có feed realtime, bắt đầu lưu dữ liệu hợp lệ từ khi được cấp quyền; không giả định có quá khứ.** Một mùa mưa/đợt quan trắc mới giúp đánh giá hệ thống chứ chưa bảo đảm đủ train 7-day model.

## Bước 8.3 — Điểm ngập lịch sử không phải ground truth âm

- Dùng nghiên cứu 148 điểm 2012–2018, Quyết định 2280/2026 để làm **hotspot priors** và chọn khu vực thí điểm.
- Không coi 11/71/220 điểm **trong kịch bản dự báo ngập** là những ngày đã ngập.
- Không dùng các địa chỉ “không xuất hiện trong danh sách” làm nhãn `0`.

## Bước 8.4 — NASA/GFM để bổ sung QC và nhãn yếu

- Chọn đúng tile/scene **chứa Hà Nội**, kiểm tra footprint thực, CRS, thời gian ảnh.
- NASA: `FloodCS_1Day_250m`, `ValidCountsCS_1Day_250m`, loại `255` và mây; tính `observed_flood_fraction` cho polygon.
- GFM: dùng `observed_flood_extent`, `reference_water_mask`, `exclusion_mask`, `likelihood`.
- **Không ép mask 250 m thành đường rộng vài mét**; chỉ tính trên vùng lớn, phục vụ kiểm tra.
- Lưu nhãn quan trắc theo đúng ngày chụp; không sao chép nhãn qua các ngày không có ảnh.

## Bước 8.5 — QC bắt buộc

- Trùng event (cùng đường + giờ, nhiều bài báo) → hợp nhất, giữ tất cả nguồn.
- Vị trí mơ hồ “phường X ngập” → `ward_event`, **không** tự gán mọi `road_segment`.
- Độ sâu nước âm / cực lớn không hợp lý → `SUSPECT`.
- Thời gian local/UTC: lưu UTC, ghi múi giờ nguồn và độ chính xác.
- Phân biệt nước trên đường và nước sông/hồ; lọc nước thường trực và ngập do lũ sông ngoài phạm vi.
- Sensor `OFFLINE` không được biến thành `0`.
- `label_coverage_report.csv` cần báo cáo **số mẫu 1, số mẫu 0, số NULL theo phường và từng tháng**.

---

# 9. Ghép nhãn lịch sử với forecast lịch sử (không leakage)

## 9.1. Quy tắc một mẫu

Giả sử muốn dự báo một đợt ngập vào **21/09/2026** từ bản phát hành **20/09/2026 07:00 VN**:

1. Chọn bản Open-Meteo **đã có sẵn** trước `issue_time`.
2. Lấy `rain_pred_*` **do chính run đó dự báo** cho ngày 21/09.
3. Lấy `rain_observed_past_*` chỉ đến trước 20/09 07:00.
4. Lấy GIS/hotspot lịch sử đã tồn tại trước ngày 20/09.
5. Từ HSDC/sự kiện thực tế sau ngày 21/09, tạo `label=1/0/NULL`.
6. Ghép `(ward_id, issue_time, target_date, lead_day)` vào một hàng training.

**Sai nghiêm trọng cần tránh:**

```text
X = Mưa THỰC TẾ ngày 21/09/2026
y = Ngập ngày 21/09/2026
→ Không phải bài toán “dự báo ngày 20/09”, bị rò rỉ tương lai.
```

**Đúng:**

```text
X = Mưa DỰ BÁO CHO ngày 21/09, phát hành trước 20/09 07:00
  + mưa quan trắc <= 20/09 07:00
  + thông tin GIS đã biết
y = Ngập ngày 21/09 do quan trắc thật xác minh
```

## 9.2. Pseudo-code builder

```python
for issue_time in scheduled_issue_times:
    run = select_forecast_run(
        model="ecmwf_ifs",
        available_before=issue_time,
    )

    for ward in wards:
        wx = get_forecast_for_ward(run, ward)
        past = get_observed_past_asof(ward, issue_time)
        geo = get_static_features_asof(ward, issue_time)

        for lead_day in range(1, 8):
            target_window = build_target_window(issue_time, lead_day)
            X = features(wx, past, geo, target_window)
            y, quality = lookup_verified_label(ward, target_window)

            save_training_row(
                issue_time=issue_time,
                ward_id=ward.id,
                lead_day=lead_day,
                features=X,
                target=y,
                label_quality=quality,
            )
```

Trước khi train, chỉ lấy `quality in A/B` và `y in {0,1}`; target `MONITORED_SITES` và `WARD_ANY_FLOOD` phải được train/đánh giá **riêng**.

---

# 10. Chia tập train/validation/test

**Không random split theo từng hàng.** Cùng một trận mưa/ngập sẽ tạo ra nhiều issue-times và nhiều lead-days nên chia ngẫu nhiên làm leakage.

## 10.1. Kế hoạch split

- **Theo thời gian trước tiên**: train các năm cũ, validation giai đoạn tiếp theo, test các trận mưa mới nhất sau cùng.
- **Theo trận mưa (`storm_event_group`)**: không để các bản dự báo D1–D7 cho cùng một trận ở cả train và test.
- **Theo không gian** (kiểm chứng phụ): hold out một vài phường hoặc các trạm chưa thấy để kiểm tra khả năng tổng quát.
- Khi chia, nhóm **event_id + target_date + area_id** đi cùng nhau; tốt nhất có `purge gap` vài ngày quanh biên train/val/test để tránh cùng cơn mưa rò sang hai tập.
- Nếu dữ liệu thực chỉ bắt đầu từ 2026, **không giả định có sẵn train 2024–2025** ở cấp đường. Có thể học nền rủi ro từ dữ liệu cũ, và chỉ train supervised khi lượng nhãn mới đủ.

## 10.2. Chất lượng sample

Báo cáo theo từng `lead_day`:
- `n_positive`, `n_negative_verified`, `n_unknown`.
- Số **trận mưa độc lập**, số phường có nhãn, số điểm đo có lịch sử.
- Tỷ lệ quan trắc hợp lệ và độ lệch địa lý của điểm đo.
- Số nhãn từ HSDC/báo cáo và số nhãn chỉ từ vệ tinh (giữ riêng).
- Kết quả phải có **khoảng tin cậy bootstrap theo sự kiện**, đặc biệt khi ít trận ngập.

**Gate trước training:** Phải có cả nhãn dương và âm đáng tin trong **train và validation/test** và đủ biến thiên theo mùa, mưa, địa hình. Không áp đặt ngưỡng “1000 bản ghi là đủ”: 1000 giờ cùng một trận ngập vẫn chỉ là **một sự kiện** về khả năng tổng quát.

---

# 11. Training và đánh giá cụ thể

## 11.1. Quy trình model

1. **Baseline**: mưa 24h/max 1h + bản đồ điểm ngập.
2. **LightGBM** trên tập nhãn A/B. Giữ schema feature cố định.
3. Tune tham số bằng **Optuna** trên validation; không tune trên test.
4. Hiệu chỉnh xác suất (isotonic/Platt); kiểm tra riêng D1, D2, D3, D4–D7.
5. Chọn ngưỡng cảnh báo dựa trên **chi phí bỏ sót vs cảnh báo sai**, và đánh giá nhiều ngưỡng.
6. **Ablation**: bỏ GIS, bỏ lịch sử mưa, bỏ history hotspot, bỏ đất xây dựng... xem thành phần nào tăng thật.
7. Nếu nhãn đủ lớn, thử TCN/LSTM và so sánh công bằng.
8. Lưu model + feature schema + `training_data_hash` + `label_policy_version` + evaluation report.

## 11.2. Metric bắt buộc

| Metric | Ý nghĩa |
|---|---|
| **Recall** tại ngưỡng cảnh báo | Bao nhiêu sự kiện ngập thật được cảnh báo |
| **Precision** | Trong các cảnh báo ngập, bao nhiêu là thật |
| **PR-AUC** | Quan trọng khi ngập hiếm hơn không ngập |
| **False alarms/ward/month** | Số cảnh báo nhầm theo khu vực/tháng |
| **Brier Score + reliability plot** | `P=70%` có thật sự đáng tin không |
| **Lead-time Recall** | Độ nhạy ở D1, D2, ... D7 |
| **Spatial coverage** | Phần trăm xã/phường/đường có thể dự báo hợp lệ |
| **Event-level missed floods** | Bỏ sót cả một sự kiện ngập nghiêm trọng |
| **Inference latency** | Thời gian dự báo theo vị trí |
| **Unknown/abstain rate** | Tỷ lệ AI trung thực báo thiếu dữ liệu |

**Không dùng Accuracy đơn độc** vì phần lớn ngày không có ngập.

### Tiêu chí nghiệm thu đề xuất (cần chốt theo thực tế)

- `Data`: 100% mẫu training có `issue_time`, `target_window`, `source`, `label_policy_version`.
- `Leakage`: 0 feature có `available_at > issue_time`; kiểm tra tự động.
- `Benchmark`: LightGBM vượt baseline mưa-ngưỡng trên **test thật** về Recall/PR-AUC **mà không làm false alarm tăng quá mức đã thỏa thuận**.
- `Calibration`: xác suất đủ tốt để dùng như xác suất; nếu không, chỉ hiện **mức nguy cơ định tính**.
- `Coverage`: có báo cáo riêng cho D1–D3 và D4–D7, và phường/đường có dữ liệu.
- `Road`: chỉ mở dự báo phân đoạn khi số lượng và độ phủ nhãn **đủ để kiểm tra trên các đoạn đường chưa thấy**.

Không cam kết trước một con số Accuracy/F1 khi chưa kiểm tra số liệu thật.

---

# 12. Kiến trúc triển khai backend và giao diện cảnh báo

```text
GPS hoặc tên đường
   │
   ├── Geocoding → PostGIS → ward_id, road_segment_id
   │
   ├── Open-Meteo 168h (JSON) + mưa quá khứ đã biết
   │
   ├── Static GIS (độ trũng, xây dựng, điểm ngập lịch sử)
   │
   ├── Ward Flood Model (LightGBM + calibrator)
   │       └── P(rủi ro ngập D1..D7) — kèm mức tin cậy
   │
   ├── Road Model (chỉ khi đã đủ nhãn) hoặc hotspot susceptibility
   │       └── không đủ bằng chứng → ROAD_INSUFFICIENT_DATA
   │
   ├── Sensor / iHanoi data (nếu được phép)
   │       └── Hiện trạng hiện tại: sensor wet/dry/unknown
   │
   └── FastAPI → bản đồ phường, đoạn đường, cảnh báo, nguồn, thời gian
```

## 12.1. API đề xuất

`GET /api/v1/flood-risk?lat=21.0&lon=105.8&days=7`

**Response GIẢ LẬP về mặt giá trị; không phải mô hình đã train:**

```json
{
  "model": "hanoi_flood_lgbm_v1",
  "issued_at": "2026-11-12T08:00:00Z",
  "timezone": "Asia/Ho_Chi_Minh",
  "location": {
    "ward_id": "DEMO_WARD_ID",
    "ward_name": "Phường minh họa",
    "road_segment_id": "road_000318"
  },
  "scope": "MONITORED_SITES",
  "forecast_days": [
    {
      "lead_day": 1,
      "risk_probability": 0.18,
      "risk_level": "LOW",
      "status": "MODEL_ESTIMATE",
      "data_quality": "PARTIAL"
    },
    {
      "lead_day": 2,
      "risk_probability": 0.72,
      "risk_level": "HIGH",
      "status": "MODEL_ESTIMATE",
      "data_quality": "PARTIAL"
    }
  ],
  "road_specific": {
    "status": "INSUFFICIENT_DATA",
    "risk_probability": null,
    "message": "Chưa đủ dữ liệu xác minh để dự báo ngập đoạn đường này"
  },
  "nowcast": {
    "sensor_status": "NOT_AVAILABLE",
    "observed_depth_cm": null
  },
  "disclaimer": "Nguy cơ dự báo, không phải quan trắc hay cảnh báo chính thức."
}
```

- Ví dụ trên chỉ hiển thị D1 và D2 để ngắn; response thực tế trả đủ D1–D7.
- **Không tự suy ra “đang khô ráo” từ `risk_probability` thấp.**
- Mọi giá trị khả năng/probability trong ví dụ chỉ là giả lập và phải đánh giá calibration mới được đưa vào sản phẩm.

## 12.2. Gợi ý giao diện

- Lớp bản đồ phường: nguy cơ theo ngày đã chọn.
- Lớp điểm ngập lịch sử: biểu tượng khác với dự báo; không tô cả phố “đang ngập”.
- Lớp trạm: **trạng thái quan trắc hiện tại** riêng với dự báo.
- Bảng 7 ngày: nguy cơ, lượng mưa dự báo, tính sẵn có dữ liệu, thời điểm cập nhật.
- Cảnh báo rõ: “**Nguy cơ ngập theo phường**” so với “**Nguy cơ tại đoạn đường**”.
- Khi vị trí trên đoạn đường không có model đủ tin cậy: dự báo phường + **“Chưa thể kết luận ở vị trí chính xác”**.
- D4–D7: mô tả là **cảnh báo sớm có bất định cao**, không dùng để khẳng định đường sẽ ngập.

---

# 13. Cấu trúc project và file dataset

```text
flood_ai_hanoi/
├── README.md
├── docs/
│   ├── TRAINING_PLAN.md
│   ├── DATA_DICTIONARY.md
│   ├── LABEL_POLICY.md
│   ├── DATA_ACCESS_STATUS.md
│   └── EVALUATION_PROTOCOL.md
├── config/
│   ├── open_meteo.yaml
│   ├── locations.yaml
│   ├── features.yaml
│   └── label_policy.yaml
├── data/
│   ├── raw/
│   │   ├── open_meteo_live/
│   │   ├── open_meteo_single_runs/
│   │   ├── hanoi_flood_events/
│   │   ├── hanoi_sensors/
│   │   ├── nasa_mcdwd/
│   │   ├── copernicus_gfm/
│   │   └── gis/
│   ├── interim/
│   │   ├── weather_forecast_hourly.parquet
│   │   ├── observed_weather_hourly.parquet
│   │   ├── flood_events.parquet
│   │   ├── sensor_waterlevel_hourly.parquet
│   │   ├── admin_wards.geoparquet
│   │   ├── road_segments.geoparquet
│   │   └── satellite_flood_observations.parquet
│   ├── labels/
│   │   ├── ward_day_labels.parquet
│   │   ├── road_segment_day_labels.parquet
│   │   ├── label_provenance.parquet
│   │   └── label_coverage_report.csv
│   └── training/
│       ├── train_ward_day.parquet
│       ├── train_road_day.parquet
│       └── split_manifest.csv
├── src/
│   ├── ingest_open_meteo.py
│   ├── ingest_hanoi_labels.py
│   ├── preprocess_satellite.py
│   ├── prepare_gis.py
│   ├── quality_control.py
│   ├── build_labels.py
│   ├── build_training_dataset.py
│   ├── features.py
│   ├── train_baseline.py
│   ├── train_lgbm.py
│   ├── calibrate.py
│   ├── evaluate.py
│   └── predict.py
├── models/
├── reports/
└── api/
    └── main.py
```

**Công nghệ:** Python, Pandas/Polars, GeoPandas/Rasterio, PostGIS, Scikit-learn, LightGBM, Optuna, MLflow, FastAPI; MapLibre ở frontend. **CPU đủ để bắt đầu LightGBM**.

---

# 14. Lộ trình triển khai có điều kiện “qua cổng”

## Giai đoạn 0 — Chốt bài toán (1–2 ngày)

**Việc làm**
- Chốt `MONITORED_SITES` hay `WARD_ANY_FLOOD` là target đầu tiên dựa trên khả năng lấy nhãn.
- Chốt `label_policy_v1` (ngưỡng độ sâu điểm đo, độ phủ sensor, nguyên nhân do mưa).
- Chọn **một cụm phường/điểm ngập ở Hà Nội** làm pilot; tránh tự hứa “tất cả 126 phường và toàn bộ đường” trước khi có nhãn.

**Đầu ra:** `LABEL_POLICY.md`, `PILOT_AREAS.md`.

## Giai đoạn 1 — Thu thập và kiểm tra nhãn (1–3 tuần hoặc lâu hơn nếu chờ quyền dữ liệu)

**Ưu tiên:**
1. Truy tìm **đường tải/API hợp lệ** theo 5695/QĐ-UBND, kiểm tra lịch sử có từ bao giờ.
2. Kiểm tra iHanoi/HSDC có thể cấp dữ liệu lịch sử sensor/mưa/ngập hay không.
3. Đưa dữ liệu điểm ngập 2026 và điểm lịch sử về schema `flood_events`.
4. Tải polygon địa giới chính xác, mạng đường OSM, lập `road_segment_id`.
5. NASA/GFM dùng kiểm chứng bổ sung; không dồn sức tải toàn bộ Việt Nam.

**Đầu ra:** `data/interim/*`, `DATA_ACCESS_STATUS.md`, bảng coverage.

**Gate:** nếu **không có âm tính quan trắc** thì chưa train binary flood probability; làm nền susceptibility + thu thập dữ liệu tiếp.

## Giai đoạn 2 — Dựng dataset training lịch sử (1–2 tuần)

1. Đọc lại pipeline Open-Meteo 7 ngày của bạn, thống nhất field và model.
2. Tải **Single Runs lịch sử** cho đúng các ngày có nhãn và ngày khô đã xác minh.
3. Tạo features từ forecast 168h + mưa quá khứ + GIS.
4. Gán label và split `event-aware`.
5. Check leakage & duplicate event.

**Đầu ra:** `train_ward_day.parquet`, `split_manifest.csv`, `data_dictionary.md`, report.

**Gate:** Có mẫu dương/âm đủ chất lượng trong train/val/test; nếu chỉ có nhãn từ NASA thì không gọi đó là mô hình dự báo ngập đường.

## Giai đoạn 3 — Train và benchmark (1–2 tuần)

1. Baseline ngưỡng mưa/điểm hay ngập.
2. LightGBM gộp `lead_day`.
3. Optuna + calibration.
4. PR-AUC, Recall, Precision, false alarms, Brier và kiểm tra theo D1–D7.
5. Ablation GIS / mưa quá khứ / nguồn trạm.

**Đầu ra:** `model.pkl`, `calibrator.pkl`, `eval_report.md`, `model_card.md`.

**Gate:** vượt baseline trong test thật ở mức chấp nhận được, và có đủ độ phủ cho tính năng người dùng mong muốn.

## Giai đoạn 4 — App cảnh báo phường (1 tuần)

- Kết nối API dự báo + geocoding + PostGIS.
- Bản đồ nguy cơ **theo phường**, chạm vị trí để xem 7 ngày.
- Hiển thị cảnh báo thiếu dữ liệu, bản tin chính thức, ngày cập nhật.

**Gate:** không hiển thị nhãn “đường chắc chắn không ngập” khi chưa có road model.

## Giai đoạn 5 — Bổ sung road-level (cần thêm dữ liệu, không nên ấn định thời gian)

- Lắp/khai thác sensor, thu thập báo cáo xác minh và đường trũng chi tiết.
- Train `road_segment_day`, test trên các đoạn chưa thấy.
- Chỉ bật hiển thị dự báo đoạn đường ở vùng **được chứng minh**; các khu vực khác để “không đủ dữ liệu”.

## Giai đoạn 6 — Mở rộng Hà Nội

- Đánh giá thêm xã ngoại thành, vùng trũng khác, mật độ trạm thấp.
- Kiểm tra thay đổi thoát nước, cống, bơm mới làm thay đổi rủi ro.
- Kiểm định sau mỗi mùa mưa; cập nhật theo dữ liệu mới, không retrain mù.
- Mở rộng dần từ pilot → các phường có đủ nhãn → 126 xã/phường.

---

# 15. Danh sách kiểm tra cần hoàn thành trước khi code train

### Nhãn / GIS

- [ ] Có nguồn tải hợp lệ của **mục 129/130 QĐ 5695/2026** hay thông tin đầu mối để xin cấp dữ liệu.
- [ ] Xác nhận lịch sử điểm ngập HSDC: có `timestamp`, vị trí, độ sâu, trạng thái cảm biến không?
- [ ] Có nhãn âm đáng tin ở **phạm vi điểm giám sát** không? Có phủ đủ ngày mưa và không mưa?
- [ ] Có polygon 126 xã/phường **dùng được bằng GIS** hay mới có bản đồ hình ảnh?
- [ ] Có OpenStreetMap road segments và map matching GPS ổn định chưa?
- [ ] Đã tách rõ `rain`, `river`, `mixed`, `unknown` cho các sự kiện chưa?
- [ ] Có thống kê từng phường: số `1`, số `0`, số `NULL`, số event độc lập và nguồn nhãn chưa?

### Open-Meteo

- [ ] Đã lưu **raw JSON** của API 7 ngày/1 giờ, timezone, units, model.
- [ ] Xác định đang lấy **168 giờ kể từ issue** hay 7 ngày lịch từ 00:00.
- [ ] Đã thử **Single Runs** với đúng model và các biến của pipeline hiện tại.
- [ ] Có `forecast_available_at <= issue_time` khi backtest không?
- [ ] Không dùng mưa thực tế tương lai làm feature.
- [ ] Không để “best_match” thay model theo lịch sử mà không lưu metadata.
- [ ] Mưa tính bằng mm/giờ đúng quy ước dự báo; không cộng trùng `rain` + `precipitation`.

### Model / Sản phẩm

- [ ] Có baseline và chỉ số test theo từng ngày trước khi tuyên bố cải thiện.
- [ ] Có đánh giá calibration, cảnh báo sai và bỏ sót sự kiện.
- [ ] Đã định nghĩa cách từ chối kết luận ở khu vực không được kiểm chứng.
- [ ] UI tách **đang ngập** (quan trắc) và **nguy cơ ngập tương lai** (AI).
- [ ] Không dùng tọa độ GPS chính xác để quảng cáo độ phân giải dự báo tốt hơn độ phân giải thực của dữ liệu.
- [ ] Có thông báo rằng đây là hệ thống dự báo nghiên cứu, **không thay thế cảnh báo chính thức**.

---

# 16. Quyết định cuối cùng cho MVP

**Chốt kỹ thuật:**

1. **Model**: LightGBM + baseline; dùng một model với `lead_day` để tạo dự báo theo **7 ngày**, kiểm định D1..D7 riêng. Chỉ thử LSTM/TCN sau khi đủ nhãn.
2. **Input**: Giữ pipeline Open-Meteo 168 giờ của bạn; bổ sung Single Runs lịch sử theo cùng model, mưa quan trắc quá khứ có timestamp, GIS phường + điểm dễ ngập.
3. **Dataset cần train**: Mỗi dòng là **một khu vực × một thời điểm phát hành × một ngày mục tiêu**. Label phải là sự kiện **thực xảy ra sau thời điểm dự báo**.
4. **Nhãn thật ưu tiên**: Dữ liệu điểm ngập mở Hà Nội (QĐ 5695), trạm HSDC/iHanoi **nếu được cấp truy cập**, camera/khảo sát có QC. NASA/GFM chỉ phụ trợ.
5. **Nhãn âm**: **chỉ 0 khi có quan trắc hợp lệ chứng minh không ngập ở đúng phạm vi đã định nghĩa**. Tất cả chỗ thiếu bằng chứng là `NULL`.
6. **Output người dùng**: Cấp phường là cảnh báo nguy cơ đã kiểm định; cấp **đường** chỉ khi có road labels và model road-level được kiểm chứng; ngược lại hiện thông tin thiếu dữ liệu và điểm hay ngập, **không nói “không ngập”**.
7. **Rủi ro lớn nhất hiện tại**: Không phải model AI, mà là **chưa xác minh đường truy cập đầy đủ lịch sử nhãn 0/1 theo thời gian và vị trí** cho Hà Nội. Phải giải quyết nút thắt này trước khi hứa độ chính xác.

---

# 17. Nguồn chính thức và tài liệu tham khảo (đã tra cứu 12/11/2026)

1. **Open-Meteo Single Runs** – thời điểm khởi tạo và lịch sử run ECMWF IFS (model ID ví dụ: `ecmwf_ifs`): https://open-meteo.com/en/docs/single-runs-api
2. **Open-Meteo Previous Runs** – dự báo theo lead 1–7 ngày: https://open-meteo.com/en/docs/previous-runs-api
3. **Open-Meteo Historical Forecast** – phân biệt historical forecast stitched và single run: https://open-meteo.com/en/docs/historical-forecast-api
4. **Open-Meteo Historical Weather** – ERA5/ERA5-Land reanalysis: https://open-meteo.com/en/docs/historical-weather-api
5. **Quyết định 5695/QĐ-UBND ngày 12/10/2026**, danh mục dữ liệu mở Hà Nội, **mục 129 (điểm ngập) và 130 (thoát nước)**: https://thuvienphapluat.vn/van-ban/Cong-nghe-thong-tin/Quyet-dinh-5695-QD-UBND-2026-du-lieu-mo-va-du-lieu-dung-chung-Ha-Noi-729327.aspx
6. **Tin chính thức về danh mục dữ liệu mở**: https://thanglong.chinhphu.vn/ha-noi-cong-bo-171-tap-du-lieu-mo-va-95-tap-du-lieu-dung-chung-103261012200943132.htm
7. **iHanoi Bản đồ mưa ngập**, nguồn API từ trạm HSDC, tin Chính phủ 03/09/2026: https://thanglong.baochinhphu.vn/chinh-thuc-ra-mat-mini-app-ban-do-mua-ngap-tren-ihanoi-103260903160946604.htm
8. **Quyết định 2280/QĐ-UBND**, kịch bản chống ngập đô thị Hà Nội mùa mưa 2026: https://xaydungchinhsach.chinhphu.vn/ke-hoach-chong-ngap-ung-noi-thanh-ha-noi-nam-2026-119260504105822803.htm
9. **Quy hoạch địa giới 126 xã/phường**: https://xaydungchinhsach.chinhphu.vn/sap-xep-dvhc-danh-sach-126-xa-phuong-moi-cua-ha-noi-119250622193659228.htm
10. **Hà Nội urban waterlogging 2012–2018, 148 điểm**, *Water* (2020): https://www.mdpi.com/2073-4441/12/3/879
11. **Hanoi urban flood hazard và Sentinel-1**, *Sustainability* (2025): https://www.mdpi.com/2071-1050/17/23/10763
12. **NASA MCDWD_L3 historical product (2003–2025)**: https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/MCDWD_L3 (nếu đường dẫn đổi, dùng trang LAADS ở nguồn 13)
13. **NASA MCDWD product page**: https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/MCDWD_L3
14. **NASA LANCE MODIS/VIIRS flood product user guide (bảng mã 0/1/2/3/255, số lượt quan sát hợp lệ)**: https://www.earthdata.nasa.gov/s3fs-public/2025-04/MCDWD_VCDWD_UserGuide_RevE_04.22.25.pdf
15. **Copernicus GFM collection (Sentinel-1)**: https://catalogue.services.eodc.eu/collections/GFM
16. **Copernicus DEM**: https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
17. **ESA WorldCover**: https://esa-worldcover.org/en/data-access
18. **OpenStreetMap**: https://www.openstreetmap.org/
19. **Open-Meteo data terms**: https://open-meteo.com/en/features
20. **Chi tiết native temporal resolution của ECMWF IFS / cách Open-Meteo nội suy hourly**: https://open-meteo.com/en/docs/ecmwf-api
21. **Ví dụ chính thức tham số `models=ecmwf_ifs` của Single Runs**: https://openmeteo.substack.com/p/single-runs-api

**Điều kiện sử dụng:** Kiểm tra giấy phép dữ liệu và hạn mức Open-Meteo (miễn phí chủ yếu cho phi thương mại), quyền khai thác dữ liệu HSDC/iHanoi, điều khoản OSM (ODbL) và ghi nhận nguồn NASA/Copernicus. Với vị trí GPS của người dùng, giảm lưu trữ tọa độ chính xác không cần thiết và chỉ dùng theo quyền người dùng đã cho phép.

**Tình trạng tài liệu:** Đây là **training plan + data specification**. Chưa phải tuyên bố rằng đã tải toàn bộ dataset Hà Nội, đã tìm thấy endpoint công khai HSDC, hay đã train/đánh giá được một model.
