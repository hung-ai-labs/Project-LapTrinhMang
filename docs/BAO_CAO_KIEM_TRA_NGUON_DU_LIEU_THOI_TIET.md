# Báo cáo kiểm tra nguồn dữ liệu thời tiết current — Phường Ba Đình, Hà Nội

- **Thời điểm kiểm tra:** 2026-11-09 21:54 (Asia/Ho_Chi_Minh) / 14:54 UTC
- **Cập nhật gần nhất:** 2026-11-09 23:31 (Asia/Ho_Chi_Minh) / 16:31 UTC
- **Phạm vi:** stack Docker đang chạy trên máy (server `:8000`, client `:8081`, PostgreSQL `:5433`)
- **Địa điểm kiểm tra:** phường Ba Đình, Hà Nội — mã Ward `00004`
- **Kết luận ngắn:** dữ liệu **current** đang hiển thị cho Ba Đình là **dữ liệu giả lập (simulator)**, không phải dữ liệu thực tế và cũng không phải dữ liệu Open-Meteo. Riêng khối **dự báo** đang lấy dữ liệu thật từ Open-Meteo (mô hình dự báo).

## 1. Kết luận chi tiết

| Hạng mục | Trạng thái thực tế | Kết luận |
|---|---|---|
| Current tại Ba Đình (`00004`) | `source = "simulator"` | Dữ liệu bịa theo công thức sin, phát mỗi 3 giây |
| Database local Docker (`db:5432/weather`) | `27.237` simulator, `0` provider | Đây là database UI đang đọc |
| Database Neon (`.env` hiện tại) | `10.027` provider, `0` simulator | Collector/provider đã ghi vào đây, không phải DB UI đang đọc |
| Bản ghi provider của Ba Đình trên Neon | `213` bản ghi, mới nhất `2026-11-06T20:15Z` | Dữ liệu thật nhưng đã cũ khoảng 3 ngày |
| Container `simulator` | Đang chạy 29 giờ | Phát dữ liệu cho đúng Ward `00004` (Ba Đình) |
| Container `collector` | Không chạy | Không có collector nào đang cập nhật DB ở thời điểm kiểm tra |
| Biến `WEATHER_SOURCE` trong container server | `simulator` | API current đang chọn nguồn giả lập |
| Biến `WEATHER_SOURCE` trong `.env` root | `provider` | Cấu hình không được áp dụng vì container chưa được tạo lại |
| `DATABASE_URL` trong container server | `db:5432/weather` (local) | Container đang dùng DB local |
| `DATABASE_URL` trong `.env` và `source/server/.env` | Neon endpoint `/neondb` | Cấu hình trên đĩa đã trỏ sang Neon |
| Khối dự báo (forecast) | Gọi trực tiếp Open-Meteo | Là dữ liệu mô hình thật, không phải simulator |

**Tóm tắt:** lỗi không nằm ở frontend tự sinh số. Backend đang có một tiến trình simulator phát dữ liệu giả vào TCP ingestion; server đang cấu hình `WEATHER_SOURCE=simulator` và đọc database local nên API trả bản ghi simulator mới nhất. Frontend chỉ hiển thị dữ liệu nhận từ API.

**Phát hiện bổ sung (kiểm tra lúc 2026-11-09 22:40 giờ Việt Nam):** tồn tại **hai database tách biệt**. UI đang đọc PostgreSQL local chỉ có dữ liệu simulator; còn Neon (theo `.env` hiện tại) có `10.027` bản ghi `provider`, trong đó Ba Đình có `213` bản ghi nhưng mới nhất đã từ `2026-11-06T20:15Z`. Container server đang chạy vẫn dùng DB local vì chưa được recreate sau khi `.env` đổi sang Neon.

**Phát hiện bổ sung 2 (đối chiếu lịch sử chạy):** log phiên Codex ngày 04/11 có nguyên văn output terminal của tài khoản `ducva` khi chạy collector cho Ba Đình lúc 20:46 ngày 04/11; bản ghi provider đầu tiên trên Neon (`observed_at=13:45Z`, `created_at=13:50Z`) khớp với lần chạy này. Đợt ghi bulk `9.818` bản ghi lúc 20:50–22:15 cùng ngày rất nhiều khả năng do user chạy từ `source/server`. Tuy nhiên chuỗi `209` bản ghi Ba Đình mỗi 15 phút từ 23:18 ngày 04/11 đến 03:18 ngày 07/11 (giờ Việt Nam) không khớp outbox/lịch sử shell, nên chưa thể khẳng định do ai. Chi tiết ở mục 3.5.

## 2. Bằng chứng runtime

### 2.1. API current trả về nguồn simulator

```http
GET http://localhost:8000/api/v1/wards/00004/weather/current
```

```json
{
  "success": true,
  "data": {
    "type": "weather.update",
    "observation": {
      "id": "422f1ad9-7bc9-4458-b5de-aa42b00cb1c1",
      "ward_id": "00004",
      "temperature": 32.6,
      "humidity": 51.5,
      "wind_speed": 50.7,
      "rainfall": 0.0,
      "source": "simulator",
      "observed_at": "2026-11-09T14:51:50.692212Z"
    },
    "alerts": [
      {
        "code": "wind",
        "severity": "warning",
        "message": "Gió mạnh từ 50 km/giờ."
      }
    ]
  }
}
```

Trường `source` là `simulator`, không phải `provider`.

### 2.2. Database local chỉ có dữ liệu simulator

```sql
SELECT source, count(*) FROM observations GROUP BY source;
```

```text
  source   | count
-----------+-------
 simulator | 26333
```

```text
provider_rows | simulator_rows | total
---------------+----------------+-------
             0 |          26333 | 26333
```

Bản ghi Ba Đình `00004` chiếm gần như toàn bộ dữ liệu simulator. Ngoài ra chỉ có một đợt ngắn ở Ward `00070`.

Con số trên là tại thời điểm 21:54. Đến 22:40, simulator vẫn chạy nên database local đã tăng lên `27.237` bản ghi, tất cả vẫn là `simulator`.

### 2.2b. Database Neon có dữ liệu provider

Kiểm tra trực tiếp database Neon được cấu hình trong `source/server/.env` và `.env` root:

```sql
SELECT source, count(*) FROM observations GROUP BY source;
```

```text
  source  | count
----------+-------
 provider | 10027
```

Bản ghi provider của Ba Đình trên Neon:

```text
ward_id | temperature | humidity | wind_speed | rainfall | source   | observed_at
--------+-------------+----------+------------+----------+----------+------------------------
00004   |        23.7 |     98.0 |        3.8 |      0.4 | provider | 2026-11-06T20:15:00Z
00004   |        23.8 |     98.0 |        3.5 |      0.4 | provider | 2026-11-06T20:00:00Z
00004   |        23.8 |     98.0 |        3.1 |      0.4 | provider | 2026-11-06T19:45:00Z
```

- Neon có `10.027` bản ghi, toàn bộ là `provider`.
- Ba Đình có `213` bản ghi provider trên Neon.
- Bản ghi mới nhất là `2026-11-06T20:15Z` (03:15 ngày 07/11 giờ Việt Nam), đã cũ khoảng 3 ngày so với thời điểm kiểm tra.
- Đây **không phải** database đang phục vụ UI: container server hiện kết nối `db:5432/weather` (local), không kết nối Neon.

### 2.3. Container simulator đang chạy và nhắm đúng Ba Đình

```text
SERVICE     STATUS                  PORTS
client      Up 29 hours             127.0.0.1:8081->80/tcp
db          Up 29 hours (healthy)   127.0.0.1:5433->5432/tcp
server      Up 29 hours (healthy)   127.0.0.1:8000->8000/tcp, 127.0.0.1:9000->9000/tcp
simulator   Up 29 hours
```

`compose.yaml:61-69` định nghĩa service `simulator` chạy:

```text
publish_weather.py --host server --ward-id 00004
```

Ward `00004` chính là phường Ba Đình, Hà Nội (`source/data/administrative/snapshot.json:143-150`).

Log simulator liên tục xác nhận server nhận bản tin:

```text
simulator-1  | 00004: {'status': 'accepted', 'event_id': '422f1ad9-7bc9-4458-b5de-aa42b00cb1c1'}
simulator-1  | 00004: {'status': 'accepted', 'event_id': 'c9e76896-16a9-4141-a4a1-a1c391951aae'}
```

### 2.4. Dữ liệu khớp chính xác công thức giả lập

`source/scripts/publish_weather.py:29-38` sinh dữ liệu bằng công thức:

```python
"temperature": round(30 + 7 * math.sin(tick / 5), 1),
"humidity": round(70 + 20 * math.cos(tick / 5), 1),
"wind_speed": round(20 + 35 * abs(math.sin(tick / 7)), 1),
"rainfall": 25 if tick % 10 == 0 else 0,
```

Hệ quả kiểm tra được:

- Nhiệt độ và độ ẩm luôn thỏa phương trình elip:
  `((temperature - 30) / 7)^2 + ((humidity - 70) / 20)^2 ≈ 1`.
- Lượng mưa chỉ có đúng hai giá trị `0` hoặc `25`.
- Khoảng cách giữa các bản ghi là 3 giây, không phải chu kỳ 15 phút của collector thật.

Kết quả 5 bản ghi mới nhất:

| observed_at (UTC) | Nhiệt độ | Độ ẩm | Gió | Mưa | Giá trị elip |
|---|---:|---:|---:|---:|---:|
| 2026-11-09T14:52:53Z | 34.4 | 85.6 | 48.0 | 25.0 | 1.004 |
| 2026-11-09T14:52:50Z | 33.2 | 87.8 | 44.8 | 0.0 | 1.001 |
| 2026-11-09T14:52:47Z | 31.9 | 89.3 | 41.0 | 0.0 | 1.005 |
| 2026-11-09T14:52:44Z | 30.5 | 89.9 | 36.8 | 0.0 | 0.995 |
| 2026-11-09T14:52:41Z | 29.1 | 89.8 | 32.3 | 0.0 | 0.997 |

Thống kê lượng mưa của Ward `00004`:

```text
 rainfall | count
----------+-------
        0 | 23561
       25 |  2619
```

Đây là dấu hiệu không thể trùng hợp của dữ liệu sinh tự động.

### 2.5. Mâu thuẫn giữa current giả lập và dự báo thật

Cùng thời điểm, endpoint dự báo gọi Open-Meteo thật (`source/server/app/services/forecast.py:85-109`) trả về:

```json
{
  "ward_id": "00004",
  "provider": "open_meteo",
  "method": "open_meteo_hourly",
  "data_kind": "model_forecast",
  "target_at": "2026-11-09T15:00:00Z",
  "predicted_temperature": 16.3,
  "predicted_humidity": 78.0,
  "predicted_wind_speed": 15.8,
  "precipitation_mm": 0.1
}
```

Current hiển thị `32.6–34.4°C` trong khi dự báo Open-Meteo cho Hà Nội là `16.3°C`. Chênh lệch này xác nhận current không đến từ cùng nguồn với dự báo.

## 3. Luồng dữ liệu và nguyên nhân gốc

### 3.1. Luồng hiện tại

```text
publish_weather.py (simulator)
        │  TCP NDJSON, mỗi 3 giây, Ward 00004
        ▼
FastAPI TCP listener (:9000)
        │
        ▼
PostgreSQL bảng observations (source='simulator')
        │
        ▼
GET /api/v1/wards/00004/weather/current
  (lọc source = WEATHER_SOURCE = 'simulator')
        │
        ▼
React frontend hiển thị
```

### 3.2. Nguyên nhân

1. **Simulator được bật và đang chạy.** Service `simulator` trong `compose.yaml:61-69` được tạo với profile `demo`, phát dữ liệu cho Ward `00004` — đúng phường Ba Đình.
2. **Server đang lọc theo nguồn `simulator`.** Biến môi trường thực tế trong container là `WEATHER_SOURCE=simulator`. API current và history lọc `Observation.source == get_settings().weather_source` (`source/server/app/api/routes.py:64,76`).
3. **`.env` hiện tại không được áp dụng vào container đã chạy.** File `.env` root ghi `WEATHER_SOURCE=provider`, nhưng container server được tạo lúc `2026-11-08T09:36:06Z`. Docker không tự cập nhật biến môi trường của container đã tồn tại; phải recreate container thì giá trị mới có hiệu lực.
4. **Collector thật không chạy.** Service `collector` (`compose.yaml:47-60`) thuộc profile `live`, hiện không có trong danh sách container đang chạy. Vì vậy database local không có bất kỳ bản ghi `source='provider'` nào. Collector đã từng chạy và ghi `10.027` bản ghi provider vào Neon, nhưng đó là database khác với database UI đang đọc.
5. **Chỉ Ward `00004` có dữ liệu.** Simulator chỉ phát cho Ba Đình, nên khi chọn đúng phường này sẽ thấy số liệu; các phường khác của Hà Nội không có current.
6. **Cấu hình trên đĩa và container đang chạy lệch nhau.** `.env` hiện trỏ Neon, nhưng container server được tạo trước đó vẫn trỏ PostgreSQL local. Vì vậy dữ liệu provider trên Neon không xuất hiện trên UI.

### 3.3. Giá trị `WEATHER_SOURCE=simulator` đến từ đâu?

Giá trị này **không nằm trong source code hiện tại** và **không nằm trong file `.env` nào của repo**:

| Vị trí | Giá trị | Ghi chú |
|---|---|---|
| `compose.yaml:28` | `${WEATHER_SOURCE:-provider}` | Mặc định `provider` |
| `source/server/app/core/config.py:16` | `provider` | Mặc định của ứng dụng |
| `.env` (root) | `provider` | Cấu hình đang lưu trên đĩa |
| `source/server/.env` | `provider` | Cấu hình backend khi chạy host |
| `.env.example`, `source/server/.env.example` | `provider` | Mẫu cấu hình |
| `source/server/tests/conftest.py:11` | `simulator` | Chỉ dùng trong test |
| `.github/workflows/ci.yml:37` | `simulator` | Chỉ dùng trong CI |
| `README.md:366` | `simulator` | Hướng dẫn chạy demo thủ công |

Không có commit nào trong git đặt `WEATHER_SOURCE` mặc định thành `simulator` trong `compose.yaml`. Giá trị `simulator` chỉ tồn tại trong **môi trường runtime của container server đang chạy**.

Bằng chứng:

- Container server được tạo lúc `2026-11-08T09:36:06Z` (16:36 giờ Việt Nam).
- `docker inspect` của container ghi nhận `WEATHER_SOURCE=simulator`.
- Render `compose.yaml` hiện tại cho ra `WEATHER_SOURCE=provider`; config hash hiện tại (`0dc963e2…`) khác config hash của container (`b572f37d…`), phù hợp với việc cấu hình đã thay đổi sau khi container được tạo.
- Reflog cho thấy `compose.yaml` được ghi lại lúc `2026-11-08 17:39:49 +07` bởi thao tác `git reset` sau thời điểm container được tạo. Điều này cho thấy có khả năng đã có chỉnh sửa cục bộ (không commit) trước đó, hoặc cấu hình được truyền trực tiếp khi chạy `docker compose`.
- Không tìm thấy lệnh `docker compose` tương ứng trong `~/.bash_history`, nên không đủ căn cứ xác định ai đã chạy lệnh.

**Kết luận:** đây là giá trị được truyền vào lúc khởi tạo container (ví dụ `WEATHER_SOURCE=simulator docker compose --profile demo up ...`), không phải thay đổi lâu dài trong code. Không thể xác định chắc chắn người thêm từ dữ liệu hiện có; chỉ có thể khẳng định nó không có trong commit, không có trong `.env` hiện tại, và sẽ mất sau khi recreate container với cấu hình hiện tại.

### 3.4. Hai database và hai cấu hình đang tách nhau

| Thành phần | Đang trỏ tới | Dữ liệu | Có phục vụ UI? |
|---|---|---|---|
| Container server đang chạy | PostgreSQL local `db:5432/weather` | `27.237` simulator | **Có** |
| Container `simulator` | Ghi qua TCP vào server → DB local | Simulator cho Ward `00004` | **Có** |
| `.env` root hiện tại | Neon `/neondb` | `10.027` provider | Không, vì server chưa recreate |
| `source/server/.env` | Neon `/neondb` | `10.027` provider | Không, chỉ dùng khi chạy backend host |
| Render `compose.yaml` hiện tại | Neon `/neondb` | Sẽ dùng Neon nếu recreate server | Chưa áp dụng |

Lịch sử shell có lệnh chạy collector từ thư mục `source/server`:

```bash
env -u DATABASE_URL ../../.venv/bin/python ../scripts/collect_open_meteo.py --ward-id 00004 --once
```

Lệnh này bỏ biến `DATABASE_URL` khỏi môi trường shell, nên ứng dụng đọc `source/server/.env` — tức là ghi provider vào **Neon**, không ghi vào database local của Docker. Bản thân lệnh `--once` chỉ tạo một bản ghi; `213` bản ghi Ba Đình trên Neon đến từ nhiều lần chạy khác nhau, được đối chiếu chi tiết ở mục 3.5.

**Kết luận:** đúng là đã có **cấu hình khác và database khác** được dùng cho collector/provider (Neon), trong khi stack Docker đang chạy UI vẫn dùng database local với simulator. Không đủ dữ liệu để khẳng định ai đã đổi cấu hình, nhưng sự tách biệt hai database là có thật và đã được xác minh trực tiếp.

Hệ quả cần lưu ý:

- Nếu chỉ recreate server theo `.env` hiện tại, UI sẽ chuyển sang Neon và thấy current Ba Đình là `23.7°C` lúc `2026-11-06T20:15Z` — dữ liệu provider thật nhưng đã cũ khoảng 3 ngày.
- Frontend chỉ hiển thị giờ, không hiển thị ngày (`source/client/src/App.tsx:8-10`), nên dữ liệu cũ có thể trông giống dữ liệu mới.
- Muốn current thực sự mới, phải chạy lại collector sau khi chọn đúng database.

### 3.5. Đối chiếu bản ghi với lịch sử chạy của tài khoản `ducva`

Mục này trả lời câu hỏi: các bản ghi provider có phải do chính user chạy không?

**Bằng chứng trực tiếp từ phiên Codex ngày 04/11** (`/home/ducva/.codex/sessions/2026/11/04/rollout-2026-11-04T20-41-15-01a1a6ca-de4c-77f3-80a2-dfe913ef2585.jsonl`):

- 20:41 (giờ Việt Nam): user hỏi cách bật lấy dữ liệu current.
- 20:44:42: user dán nguyên output terminal với prompt `ducva@VAD-LAP:~/Project-LapTrinhMang$` khi chạy `../../.venv/bin/python ../scripts/collect_open_meteo.py`; lỗi driver database.
- 20:46:59: user dán output khi chạy `env -u DATABASE_URL ../../.venv/bin/python ../scripts/collect_open_meteo.py --ward-id 00004 --once`, kết quả `Current cycle: 1 wards, 1 batches, pending=0` và lỗi TCP.
- 20:49:34: Codex chạy `alembic upgrade 0004`; migration này `DELETE FROM observations` (xóa toàn bộ quan trắc cũ, backup 4.928 bản ghi tại `/tmp/weather-stream-backups/observations-before-0004-20261104T134834Z.json`).
- 20:50:00: bản ghi đầu tiên của Ba Đình được ghi vào Neon (`observed_at=13:45Z`), nhiều khả năng do outbox của lần chạy `--once` gửi lại sau migration.
- 21:00:14: Codex kiểm tra Neon chỉ có **1** bản ghi provider (Ba Đình, 13:45Z), outbox `source/server` trống, không có tiến trình collector nào; Codex khuyên chạy lệnh đầy đủ (không `--once`) để lấy toàn bộ phường/xã.

**Đối chiếu với dữ liệu Neon:**

| Nhóm bản ghi | Thời gian (UTC) | Số lượng | Khớp với hoạt động nào? | Kết luận |
|---|---|---:|---|---|
| Bản ghi provider đầu tiên của Ba Đình | observed `13:45Z`, created `13:50Z` 04/11 | 1 (nằm trong bulk) | Lần chạy `--once` của user lúc 20:45–20:50 giờ VN | **Do user chạy** |
| Bulk provider toàn bộ ward | created `13:50–15:15Z` 04/11 | 9.818 | Lệnh full collector sau 21:00 giờ VN; khớp 2 dòng bash history `collect_open_meteo.py` không `--once`; outbox `source/server` có mtime cuối `15:46Z` | **Rất nhiều khả năng do user chạy** từ `source/server` |
| Chuỗi Ba Đình mỗi 15 phút | observed `16:15Z` 04/11 → `20:15Z` 06/11 | 209 | Collector dài hạn với `--ward-id 00004`; không thấy lệnh trong bash history/phiên Codex; outbox `source/server` không ghi sau `15:46Z` 04/11 | **Không đủ căn cứ xác định** |
| Simulator local | 08/11 → nay | 27.237+ | Container `simulator`, không phải collector | Không phải user chạy tay |

Chi tiết đáng chú ý:

- 209 bản ghi Ba Đình liên tục cách nhau đúng 900 giây, chỉ có 2 khoảng trống 1 giờ lúc `14:00–15:00Z` và `15:15–16:15Z` ngày 04/11; từ `16:15Z` 04/11 đến `20:15Z` 06/11 không gián đoạn. Đây là dấu hiệu một tiến trình collector chạy dài hạn, không phải nhiều lần chạy `--once`.
- Tiến trình dài hạn này không dùng outbox `source/server/.collector` (mtime không đổi sau `15:46Z` 04/11), nên nó chạy từ thư mục khác, dùng `--outbox` khác, hoặc chạy trên máy khác. Máy hiện tại không còn file outbox nào khác.
- Neon không lưu IP/user/audit cho từng bản ghi; `event_id` là UUID sinh từ nội dung nên không truy ngược được người chạy.
- Bản ghi mới nhất trên Neon (`2026-11-06T20:15Z`, tạo lúc `20:18:37Z`) thuộc chuỗi dài hạn này, không phải lần chạy `--once` ngày 04/11.

**Kết luận mục 3.5:**

- **Có:** chính tài khoản `ducva` đã chạy collector cho Ba Đình trên terminal ngày 04/11; bản ghi provider đầu tiên và đợt bulk gần như chắc chắn từ các lần chạy của user.
- **Không xác định:** chuỗi 209 bản ghi mỗi 15 phút kéo dài đến 07/11 không khớp lịch sử shell/outbox của máy. Nếu user không nhớ đã để collector chạy dài hạn, thì nhiều khả năng có máy/người khác dùng cùng database Neon. Không thể kết luận chắc chắn nếu không có log của Neon hoặc log tiến trình trên máy kia.
- **Không phải do user chạy tay:** toàn bộ dữ liệu simulator đang hiển thị trên UI do container `simulator` sinh; container này được tạo lúc 16:36 ngày 08/11, không có lệnh trong bash history.

## 4. Frontend có tự bịa dữ liệu không?

**Không.** Frontend không sinh số liệu thời tiết. Nó chỉ:

- gọi `GET /api/v1/wards/{ward_id}/weather/current` và WebSocket `/api/v1/ws/wards/{ward_id}/weather` (`source/client/src/hooks/useWeather.ts:58,81,93`);
- hiển thị đúng trường `source` do backend trả về;
- gắn nhãn **“Dữ liệu mô phỏng”** khi `source === "simulator"` (`source/client/src/App.tsx:47`).

Tuy nhiên có hai điểm dễ gây hiểu nhầm:

1. Nhãn nguồn nằm ở góc thẻ current, có thể bị bỏ qua.
2. Footer luôn ghi “Nguồn: Open-Meteo” trong khi current đang là simulator. Dòng này chỉ đúng cho khối dự báo, không đúng cho current khi `WEATHER_SOURCE=simulator`.

## 5. Cách chuyển sang dữ liệu thật từ Open-Meteo

> Lưu ý: “current” của Open-Meteo vẫn là dữ liệu **mô hình**, không phải số đo trạm khí tượng tại Ba Đình. Project hiện không có nguồn trạm đo vật lý.

Trước khi chạy, phải chọn **một** database đích. Hiện `.env` trỏ Neon còn container server đang chạy trỏ local; nếu không recreate server thì collector và UI sẽ tiếp tục dùng hai database khác nhau.

### Lựa chọn A — dùng Neon (theo `.env` hiện tại)

```bash
# 1. Dừng simulator
docker compose stop simulator

# 2. Xác nhận .env đang trỏ Neon và dùng provider
grep -E '^(DATABASE_URL|WEATHER_SOURCE)=' .env

# 3. Tạo lại server để áp dụng DATABASE_URL=Neon, WEATHER_SOURCE=provider
docker compose up -d --no-deps --force-recreate server

# 4. Chạy collector để cập nhật dữ liệu mới vào Neon
docker compose --profile live up -d collector

# 5. Kiểm tra current
curl -s http://localhost:8000/api/v1/wards/00004/weather/current | python3 -m json.tool
```

Kỳ vọng: `"source": "provider"`. Trước khi collector chạy xong, current có thể vẫn là bản ghi Neon cũ nhất `2026-11-06T20:15Z`.

### Lựa chọn B — dùng PostgreSQL local

```bash
# 1. Dừng simulator
docker compose stop simulator

# 2. Đổi DATABASE_URL trong .env về local
# DATABASE_URL=postgresql+psycopg://weather:weather@db:5432/weather

# 3. Đảm bảo WEATHER_SOURCE=provider, recreate server
docker compose up -d --no-deps --force-recreate server

# 4. Chạy collector ghi vào DB local
docker compose --profile live up -d collector

# 5. Kiểm tra
curl -s http://localhost:8000/api/v1/wards/00004/weather/current | python3 -m json.tool
docker compose exec -T db psql -U weather -d weather \
  -c "SELECT source, count(*) FROM observations GROUP BY source;"
```

Với lựa chọn B, database local sẽ có thêm dòng `provider`; dữ liệu simulator cũ vẫn còn nhưng bị lọc khỏi API.

Nếu chỉ muốn xem dữ liệu mô phỏng, giữ nguyên hiện trạng và chấp nhận nhãn “Dữ liệu mô phỏng”. Không nên chạy đồng thời simulator và collector rồi kỳ vọng current là dữ liệu thật: API sẽ chỉ trả đúng một nguồn theo `WEATHER_SOURCE`, nhưng dữ liệu giả vẫn tiếp tục được ghi vào DB.

## 6. Ghi chú kỹ thuật

- `WEATHER_SOURCE` là bộ lọc ở tầng đọc (`current`, `history`), không phải bộ lọc ở tầng ghi. Đổi sang `provider` không xóa dữ liệu simulator đã lưu; dữ liệu này chỉ không còn được trả về.
- Timestamp lưu UTC, frontend hiển thị theo `Asia/Ho_Chi_Minh`.
- Đơn vị: °C, %, km/h, mm/h. Lượng mưa Open-Meteo được collector quy đổi từ mm trong `interval` sang mm/h (`source/scripts/collect_open_meteo.py:88`).
- Cảnh báo hiện tại được tính từ chính bản ghi simulator (`source/server/app/services/ingestion.py:48`), nên cảnh báo “Gió mạnh” cũng là kết quả của dữ liệu giả lập.
- Dự báo là dữ liệu thật từ Open-Meteo nhưng thuộc loại `model_forecast`, không phải quan trắc trạm.

## 7. Checklist xác minh nhanh

| Câu hỏi | Cách kiểm tra | Kết quả hiện tại |
|---|---|---|
| Current lấy từ đâu? | `source` trong response current | `simulator` |
| DB local có dữ liệu thật không? | `SELECT source, count(*) FROM observations GROUP BY source;` trên local | Chỉ `simulator` |
| Neon có dữ liệu thật không? | query trực tiếp Neon | `10.027` bản ghi `provider`, Ba Đình `213` bản ghi |
| UI đang đọc DB nào? | `docker compose exec server env \| grep DATABASE_URL` | `db:5432/weather` (local) |
| `.env` trỏ DB nào? | `grep '^DATABASE_URL=' .env` | Neon `/neondb` |
| Simulator có đang chạy? | `docker compose ps` | Có |
| Collector có đang chạy? | `docker compose ps` | Không |
| Server lọc nguồn nào? | `docker compose exec server env \| grep WEATHER_SOURCE` | `simulator` |
| `.env` khai báo nguồn gì? | `grep '^WEATHER_SOURCE=' .env` | `provider` |
| Dữ liệu Neon mới nhất của Ba Đình? | query `ORDER BY observed_at DESC` | `2026-11-06T20:15Z` — đã cũ |
| Dự báo lấy từ đâu? | response forecast | `open_meteo` / `model_forecast` |
