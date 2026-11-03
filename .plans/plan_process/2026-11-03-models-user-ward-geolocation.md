# Plan model: tỉnh/phường xã, user và khu vực thời tiết gần nhất

**Schema hiện tại:** tám model kế thừa Base với created_at/updated_at; danh mục Province/Ward có tọa độ; User lưu default_ward_id; các bảng thời tiết/cảnh báo và forecast baseline. Migration `0002_wards_users_domain.py` chứa toàn bộ thay đổi từ `0001` lên schema này.

**Phạm vi đã triển khai:** models/exports, migration, snapshot/importer, helper Haversine, API danh mục và nearest-ward, cùng các kiểm thử backend. Auth và /me, FE định vị và provider/streaming theo ward là các bước tích hợp tiếp theo. Chỉ kiểm chứng migration trên SQLite tạm, chưa áp dụng database thật.

**API danh sách:** cities, provinces, wards và weather history dùng `count/next/previous/results` cùng `limit`/`offset`; liên kết giữ nguyên bộ lọc. API docs nhóm theo model/chức năng. Frontend đọc history qua results và smoke test CI dùng cùng hợp đồng.

**Kiểm chứng:** `alembic history` chỉ có `0001 → 0002`; Ruff pass; `pytest -q` pass 62 tests; frontend `npm run build` pass. Test migration đối chiếu schema với toàn bộ model, giữ dữ liệu từ revision 0001 và xác nhận timestamp có trên mọi bảng. Tests API kiểm tra pagination và OpenAPI.

**Quy ước:** lấy vị trí user một lần, chọn tọa độ Ward gần nhất, dùng làm khu vực thời tiết mặc định; không lưu tọa độ user và chưa cần GIS. Giải thích Session, AlertRule và WeatherAlert nằm ở `docs/MODEL_VA_LUONG_DU_LIEU.md`.

## 1. Vấn đề

Người dùng muốn lưu danh mục tỉnh và xã hợp lý, dùng thông tin của địa phương đã lưu để lấy dữ liệu thời tiết, và khi quay lại FE thì xem ngay nơi đã chọn. Hệ thống không cần lưu một điểm GPS riêng cho mỗi người dùng.

Code thực tế hiện chỉ có `Observation.city`, enum ba thành phố và publisher simulator. Chưa có model Province/Ward/User, chưa có adapter gọi weather provider theo tọa độ. Vì vậy “dùng số liệu ở đó” trong thiết kế mới được cụ thể hóa thành: **đọc latitude/longitude từ Ward để lấy thời tiết; lưu kết quả theo ward_id; FE đọc lại dữ liệu mới nhất từ DB**.

## 2. Vì sao cần giải quyết

- Dữ liệu địa lý chỉ nhập/xác minh một lần, không bắt user nhập tọa độ mỗi lần xem.
- Phường/xã thuộc đúng tỉnh, dùng mã làm khóa để xử lý tên trùng nhau.
- Tất cả user xem cùng một phường/xã dùng chung thời tiết; không gọi provider riêng cho từng người.
- Tọa độ địa lý là dữ liệu tham chiếu; nhiệt độ/độ ẩm/mưa/gió là chuỗi bản tin thay đổi theo thời gian, không lưu đè lên bảng Ward.
- Định vị chỉ dùng một lần để chọn phường/xã có tọa độ đại diện gần nhất. Đây là địa điểm thời tiết gần đúng mà user chấp nhận sử dụng, không phải kết luận phường/xã chứa chính xác tọa độ GPS.

## 3. Hướng giải quyết

### 3.1. Cấu trúc dữ liệu chính

| Model | Trường chính | Vai trò |
|---|---|---|
| `Province` | `id`, `name`, `dataset_version`, `is_active` | Danh mục tỉnh/thành |
| `Ward` | `id`, `province_id`, `name`, `administrative_type`, `latitude`, `longitude`, `dataset_version`, `is_active` | Danh mục phường/xã và tọa độ đại diện để lấy thời tiết |
| `User` | `id`, `email`, `password_hash`, `full_name`, `default_ward_id`, `address_text` | Lưu phường/xã mặc định và ghi chú địa chỉ riêng |
| `WeatherObservation` | `id`, `ward_id`, 4 chỉ số thời tiết, `source`, `observed_at` | Lưu các bản tin thời tiết của phường/xã |
| `UserSession` | Hash token, `user_id`, thời điểm hết hạn/thu hồi | Khôi phục đăng nhập khi user quay lại |

Các model `AlertRule`, `WeatherAlert` và `Forecast` tham chiếu địa lý qua `ward_id`. Tổng cộng tám model nghiệp vụ/hỗ trợ, không tính Base. Forecast hiện chỉ hỗ trợ persistence baseline. Không có `Location`, `location_id`, `DataSource` hoặc `source_id` trong schema mới.

```text
Province 1 ── N Ward 1 ── N WeatherObservation
                 │               ├── Forecast
                 │               └── WeatherAlert ── AlertRule
                 └── N User 1 ── N UserSession
```

Province không cần tọa độ riêng cho luồng tỉnh → phường/xã. Nếu sau này muốn xem riêng toàn tỉnh thì cần quyết định cách đại diện/tổng hợp; không tự dùng một ward rồi gọi đó là thời tiết toàn tỉnh.

Ward lưu cặp tọa độ đại diện từ snapshot có nguồn, được kiểm tra miền giá trị khi import; độ chính xác địa lý cần đối chiếu với nguồn. Cho phép cặp NULL trong danh mục nếu chưa có dữ liệu địa lý, nhưng ward đó chưa thể lấy thời tiết qua provider; API/FE báo rõ thay vì tự đoán tọa độ. Không lưu tên tỉnh lặp lại trong Ward; không lưu tỉnh/phường lặp lại trong User khi đã có default_ward_id.

`Ward.administrative_type` nullable nếu nguồn chưa phân biệt xã/phường/đặc khu. Dùng tên có sẵn và tỉnh cha để hiển thị; không tự bịa loại đơn vị. Hai ward có thể có tọa độ đại diện trùng nhau, nên không đặt unique cho cặp latitude/longitude. Không thêm tọa độ hoặc trường địa chỉ GPS vào User; `address_text` chỉ là ghi chú user tự nhập, không tự điền từ kết quả định vị gần nhất.

### 3.2. Lấy dữ liệu từ thông tin Ward đã lưu

1. User chọn tỉnh → chọn phường/xã; FE gửi mã ward. Backend kiểm tra ward còn hiệu lực, thuộc tỉnh tương ứng và có tọa độ.
2. Producer đọc Ward từ API nội bộ, lấy trực tiếp `Ward.latitude`/`Ward.longitude` để gọi weather provider. Không dùng tên địa phương để đoán vị trí mỗi lần gọi.
3. Chuẩn hóa dữ liệu provider thành payload gồm `event_id`, `ward_id`, `temperature`, `humidity`, `wind_speed`, `rainfall`, `source=provider`, `observed_at` UTC.
4. Gửi payload qua TCP NDJSON như pipeline hiện tại. Ingestion validate ward, commit DB rồi ACK/broadcast WebSocket theo ward_id.
5. REST lấy bản tin mới nhất bằng filter `ward_id` và loại nguồn, order theo observed_at; history/forecast dùng cùng ward. FE không gọi weather provider trực tiếp.
6. Chọn tay rồi bấm lưu, hoặc bấm “Dùng vị trí hiện tại làm mặc định”, sẽ cập nhật `default_ward_id` của user đã đăng nhập. Lần sau `/me` trả ward đó để FE tự tải REST và mở WS mà không xin lại định vị. Xem thử nơi khác không tự ghi đè mặc định.

Đề xuất provider Open-Meteo vì API nhận latitude/longitude; ví dụ code ở mục 5 dùng tọa độ Ward đã lưu làm params. Theo tài liệu, tọa độ phản hồi có thể là tâm ô lưới cách tọa độ yêu cầu vài km; do đó ghi nhãn thời tiết khu vực, không mô tả là đo tại từng nhà. [Open-Meteo API](https://open-meteo.com/en/docs).

Cache theo ward/source/time và TTL ở backend/producer; nhiều người xem một ward chỉ tạo một lịch thu thập. Không poll toàn bộ danh mục hành chính vô điều kiện. Producer đọc danh sách ward có người xem, vừa được yêu cầu trong TTL, hoặc được theo dõi theo tài khoản qua API nội bộ có token riêng; chỉ trả mã/tọa độ, không trả địa chỉ/email của user. Không tạo request HTTP tồn tại lâu để chờ provider: FE hiện trạng thái chờ và nhận bản tin đầu qua WS.

### 3.3. Định vị một lần → Ward gần nhất

1. Chọn tay vẫn theo tỉnh → ward và mã định danh; đổi tỉnh xóa ward cũ trên FE.
2. User bấm “Dùng vị trí hiện tại làm mặc định”; FE gọi `getCurrentPosition()` một lần. Không dùng `watchPosition()`. Từ chối quyền, timeout hoặc không hỗ trợ thì giữ lựa chọn cũ và cho chọn tay. Trình duyệt yêu cầu quyền định vị và secure context; kiểm tra HTTPS/localhost khi triển khai. [MDN Geolocation](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/getCurrentPosition).
3. FE gửi latitude/longitude vào `POST /geography/nearest-ward`. Backend kiểm tra số hữu hạn và miền tọa độ; chỉ xét ward có tọa độ, ward và province đang active.
4. Tính khoảng cách Haversine tới tọa độ đại diện của các ward, lấy khoảng cách nhỏ nhất. Không giới hạn vào một tỉnh đoán trước; tỉnh của kết quả lấy qua `Ward.province_id`. Nếu đồng hạng, chọn mã ward nhỏ nhất để có kết quả ổn định. Bản đầu quét danh sách ứng viên, chưa cần PostGIS hoặc thư viện GIS.
5. Endpoint trả `ward_id`, tên ward, tỉnh cha, `distance_km` và `match_type=nearest`; không tự sửa tài khoản. Khoảng cách trả về là tới điểm đại diện của ward. Không có ứng viên thì trả 404 kèm thông báo chọn tay; không dùng bản ghi thiếu tọa độ hoặc tỉnh/ward inactive.
6. Với user đã đăng nhập, FE hoàn tất thao tác nút ở bước 2 bằng `PATCH /me/ward` để lưu ward vừa chọn. Không yêu cầu xác nhận thêm cho nút đã nói rõ mục đích lưu; nếu lưu lỗi thì báo rõ, không hiển thị là đã lưu. Với khách, chỉ đổi khu vực đang xem, sau đăng nhập mới lưu được.
7. UI hiển thị “Khu vực gần bạn: <tên ward>, <tỉnh>”, cho đổi bằng tay. User chấp nhận ward gần nhất làm địa điểm mặc định; không tự điền địa chỉ số nhà hoặc khẳng định đúng địa giới. Nếu kết quả ở xa hoặc thiết bị định vị lệch, có thể đổi lại bằng chọn tỉnh/ward.
8. Chỉ lưu `User.default_ward_id`; tọa độ và khoảng cách của user không ghi vào DB hay event WS. Tọa độ request không được đưa vào application log. Khi xem thời tiết, producer luôn dùng tọa độ Ward đã lưu, không dùng tọa độ user.

### 3.4. Tài khoản và API dự kiến

Auth dùng password hash Argon2 và opaque token cookie HttpOnly; DB chỉ lưu hash token ngẫu nhiên, session có hạn/thu hồi. API lấy user từ session, không nhận user_id do client tự chọn để sửa địa chỉ. API công khai và WS không chứa address_text/email/password hash. Giữ một địa điểm mặc định cho mỗi user trong bản đầu.

| Endpoint `/api/v1` | Mục đích |
|---|---|
| `GET /provinces?q=...` | Tìm tỉnh/thành đang hiệu lực |
| `GET /provinces/{province_id}/wards?q=...&limit=...` | Tìm ward trong đúng tỉnh; phân trang/giới hạn |
| `POST /geography/nearest-ward` | Tọa độ một lần → ward gần nhất, tỉnh cha, distance_km và match_type=nearest; không ghi DB |
| `GET /wards/{ward_id}/weather/current` | Bản tin mới nhất cùng ward/source |
| `GET /wards/{ward_id}/weather/history` | Lịch sử cùng ward/source |
| `GET /wards/{ward_id}/weather/forecast` | Dự báo cùng ward/source |
| `WS /ws/wards/{ward_id}/weather` | Cập nhật theo ward, không có địa chỉ riêng |
| `POST /auth/register`, `POST /auth/login`, `POST /auth/logout` | Tài khoản và session |
| `GET /me` | Profile và default_ward, kèm thông tin tỉnh |
| `PATCH /me/ward` | Body `{ward_id, address_text}`; chỉ lưu cho user hiện tại |
| `DELETE /me/ward` | Bỏ mặc định/địa chỉ, không xóa thời tiết chung |
| `GET /internal/collection-wards` | Producer đã xác thực lấy mã và tọa độ ward cần thu thập |

FE khôi phục `/me` trước khi mở dữ liệu mặc định; không mở Hà Nội trước rồi đổi sang ward của user. Khách vẫn xem được bằng chọn địa chỉ/GPS; cần đăng nhập để lưu. Khi logout/đổi user/đổi ward, hủy request và socket cũ.

Nguồn mặc định của route mới là provider; không có dữ liệu thật thì báo chờ/trống/lỗi/stale, không tự thay bằng simulator. Demo mô phỏng chọn source rõ ràng. Bỏ model DataSource nhưng giữ source=simulator/provider trên observations, alerts và forecasts để không trộn hai loại dữ liệu.

### 3.5. Nhập dữ liệu tỉnh/xã và migration

- Nguồn khởi đầu đề xuất: [Open Admin Data Vietnam](https://github.com/open-admin-data/vietnam-administrative-divisions), dùng `data/all-province.json` và `data/all-ward.json`. Bản đã kiểm tra trong cuộc trao đổi có 34 tỉnh/thành và 3.321 đơn vị cấp xã, đủ cặp tọa độ về mặt dữ liệu; đây không phải kiểm chứng thực địa. Trước khi import, tải và pin cùng một commit cho cả hai file, lưu SHA-256, URL nguồn, ngày tải và license CC BY 4.0 trong manifest đi kèm snapshot. Dùng `dataset_version=open-admin-data@<commit>` với SHA thực tế được lấy lúc triển khai; không tự ghi SHA chưa xác minh.
- Mapping tỉnh: `id → Province.id`, `name.local → Province.name`. Mapping ward: `id → Ward.id`, `parent.id → Ward.province_id`, `name.local → Ward.name`, `geo.lat/lon → latitude/longitude`. Nếu nguồn chỉ ghi chung “Xã/Phường”, để administrative_type NULL; chỉ điền khi có loại đơn vị được xác minh. Không bắt buộc nhập GIS từ thanglequoc trong bản đầu; không ghép hai snapshot khác phiên bản rồi coi mã hành chính luôn khớp.
- Snapshot danh mục có nguồn, license, phiên bản và thời điểm cập nhật; dùng mã chuỗi giữ số 0 đầu. Không tự điền mã hành chính giả cho dữ liệu thật. Tọa độ đại diện cần nguồn địa lý được kiểm tra riêng nếu snapshot chỉ có tên/mã.
- Import có dry-run, kiểm tra ward thuộc đúng province, mã trùng, tọa độ thiếu/ngoài miền. Tên ward không unique toàn quốc. Inactive record vẫn được giữ nếu còn tham chiếu; không đoán mã mới chỉ dựa vào tên khi sáp nhập.
- Migration không tải mạng; importer chạy riêng sau migration. Alembic dùng DDL cố định, không import model runtime.
- Dữ liệu lịch sử hiện tại ở cấp thành phố, không đủ căn cứ gán cho một ward cụ thể. Giữ cột vật lý city cũ dưới thuộc tính `legacy_city`, thêm ward_id nullable. Constraint đảm bảo một row có đúng một trong ward_id hoặc legacy city. Mọi bản tin ward mới phải có ward_id và city NULL; row legacy giữ city và ward_id NULL.
- Route/TCP city cũ được duy trì tạm trong namespace legacy, không hiển thị dữ liệu city là dữ liệu ward. Hub phân biệt key city:<slug> và ward:<code>. Không xóa hoặc tự backfill thành một phường ngẫu nhiên. Khi bỏ hẳn compatibility, cần quyết định archive/migrate legacy riêng.
- Migration 0002 tạo danh mục/tài khoản/các bảng còn lại, thêm FK/index/check, giữ nguyên event ID, chỉ số, source và observed_at của dữ liệu cũ. SQLite dùng batch migration và bật FK trong test; PostgreSQL test thực thi constraints.
- Downgrade chỉ cho phép khi không có dữ liệu ward/user/forecast/alert cần giữ; nếu không thì chặn và dùng restore backup theo version. Không tự drop dữ liệu người dùng.

### 3.6. Thứ tự triển khai sau khi duyệt

1. Model và migration; import danh mục Province/Ward có tọa độ; giữ tương thích lịch sử city.
2. REST/TCP/WS theo ward và query dữ liệu mới nhất từ DB; kiểm tra cách ly các ward.
3. Provider producer đọc tọa độ Ward đã lưu, lấy dữ liệu thật, chuẩn hóa, gửi TCP; cache/TTL/retry.
4. User/session và lưu default_ward_id; FE tự mở ward mặc định sau đăng nhập.
5. FE chọn tỉnh/phường xã, định vị một lần → Haversine → ward gần nhất → lưu mặc định; trạng thái loading/lỗi/chờ dữ liệu; đồng bộ README/UML/phân công và chạy kiểm thử.

**Ranh giới triển khai:** bước 1 gồm schema, exports, migration, importer và kiểm thử model/dữ liệu. Bước 2–5 là các đầu việc tích hợp cần thiết để có chức năng người dùng hoàn chỉnh, không được báo đã hoàn thành chỉ vì tạo xong bảng. Tất cả các bước vẫn đang là đề xuất, chờ duyệt source riêng.

## 4. Code nền tại revision 0001

`source/server/app/db/models.py:1-22`:

```python
from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (Index("ix_observations_city_time", "city", "observed_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    city: Mapped[str] = mapped_column(String(64))
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    wind_speed: Mapped[float] = mapped_column(Float)
    rainfall: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

`source/server/app/schemas/weather.py:7-19`:

```python
City = Literal["hanoi", "danang", "hcm"]


class ObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    event_id: UUID
    city: City
    temperature: float = Field(ge=-60, le=65)
    humidity: float = Field(ge=0, le=100)
    wind_speed: float = Field(ge=0, le=500, description="km/h")
    rainfall: float = Field(ge=0, le=1000, description="mm/h")
    source: Literal["simulator", "provider"] = "simulator"
    observed_at: AwareDatetime
```

`source/server/app/services/ingestion.py:12-29`:

```python
async def ingest(value: ObservationInput) -> bool:
    async with Session() as session:
        record = Observation(
            id=str(value.event_id),
            **value.model_dump(exclude={"event_id", "observed_at"}),
            observed_at=value.observed_at.astimezone(UTC),
        )
        session.add(record)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            if await session.get(Observation, str(value.event_id)) is not None:
                return False
            raise
        observation = ObservationOut.model_validate(record)
    event = WeatherEvent(observation=observation, alerts=evaluate_alerts(observation))
    hub.publish(value.city, event.model_dump(mode="json"))
```

## 5. Code sau khi sửa

Các block model/helper/test có source tương ứng phản ánh code hiện tại. Các block còn ghi CHƯA TRIỂN KHAI mô tả bước tích hợp tiếp theo; hợp đồng API/FE/provider tại mục 3 cần hoàn thiện theo phạm vi đó. Mỗi model vẫn ở một file trực tiếp trong `source/server/app/db/`; export qua `__init__.py`. Không tạo `location.py` hoặc `data_source.py`.

Giữ tên chỉ số và UUID event hiện có, không đổi Float sang Numeric cho dữ liệu thời tiết trong phạm vi này. Tọa độ Ward dùng Numeric để có độ chính xác lưu ổn định. FK lịch sử dùng RESTRICT; xóa user chỉ cascade session, không xóa Ward hay thời tiết. Mô hình không cấu hình ORM cascade lịch sử.

`source/server/app/db/base.py` — **Code hiện tại**:

```python
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
```

`source/server/app/db/province.py` — **Code hiện tại**:

```python
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Province(Base):
    __tablename__ = "provinces"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

`source/server/app/db/ward.py` — **Code hiện tại**:

```python
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Ward(Base):
    __tablename__ = "wards"
    __table_args__ = (
        Index("ix_wards_province_name", "province_id", "name"),
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_wards_coordinate_pair",
        ),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_wards_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_wards_longitude"),
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    province_id: Mapped[str] = mapped_column(
        ForeignKey("provinces.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    administrative_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(8, 5), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(8, 5), nullable=True)
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

`source/server/app/db/user.py` — **Code hiện tại**:

```python
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(trim(email))", name="ck_users_normalized_email"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    address_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    default_ward_id: Mapped[str | None] = mapped_column(
        String(20),
        ForeignKey("wards.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
```

`source/server/app/db/user_session.py` — **Code hiện tại**:

```python
from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="ck_user_sessions_expiry"),
        Index("ix_user_sessions_user_expiry", "user_id", "expires_at"),
    )

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

`source/server/app/db/weather_observation.py` — **Code hiện tại**:

```python
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WeatherObservation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        CheckConstraint(
            "(ward_id IS NOT NULL AND city IS NULL) OR (ward_id IS NULL AND city IS NOT NULL)",
            name="ck_observations_geography",
        ),
        Index("ix_observations_city_time", "city", "observed_at"),
        UniqueConstraint("id", "ward_id", "source", name="uq_observations_context"),
        CheckConstraint("source IN ('simulator', 'provider')", name="ck_observations_source"),
        CheckConstraint("temperature BETWEEN -60 AND 65", name="ck_observations_temperature"),
        CheckConstraint("humidity BETWEEN 0 AND 100", name="ck_observations_humidity"),
        CheckConstraint("wind_speed BETWEEN 0 AND 500", name="ck_observations_wind"),
        CheckConstraint("rainfall BETWEEN 0 AND 1000", name="ck_observations_rainfall"),
        Index("ix_observations_ward_time", "ward_id", "observed_at"),
        Index("ix_observations_ward_source_time", "ward_id", "source", "observed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ward_id: Mapped[str | None] = mapped_column(
        String(20),
        ForeignKey("wards.id", ondelete="RESTRICT", name="fk_observations_ward"),
        nullable=True,
    )
    legacy_city: Mapped[str | None] = mapped_column("city", String(64), nullable=True)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[float] = mapped_column(Float, nullable=False)
    wind_speed: Mapped[float] = mapped_column(Float, nullable=False)
    rainfall: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

`source/server/app/db/alert_rule.py` — **Code hiện tại**:

```python
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class AlertRule(Base):
    __tablename__ = "alert_rules"
    __table_args__ = (
        UniqueConstraint("rule_key", "version", name="uq_alert_rules_version"),
        CheckConstraint("version > 0", name="ck_alert_rules_version"),
        CheckConstraint("operator IN ('gte', 'lte')", name="ck_alert_rules_operator"),
        CheckConstraint(
            "metric IN ('temperature', 'humidity', 'wind_speed', 'rainfall')",
            name="ck_alert_rules_metric",
        ),
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')", name="ck_alert_rules_severity"
        ),
        CheckConstraint("cooldown_seconds >= 0", name="ck_alert_rules_cooldown"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    rule_key: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    operator: Mapped[str] = mapped_column(String(8), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

`source/server/app/db/weather_alert.py` — **Code hiện tại**:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class WeatherAlert(Base):
    __tablename__ = "weather_alerts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["started_by_observation_id", "ward_id", "source"],
            ["observations.id", "observations.ward_id", "observations.source"],
            ondelete="RESTRICT",
            name="fk_weather_alerts_started_context",
        ),
        ForeignKeyConstraint(
            ["last_observation_id", "ward_id", "source"],
            ["observations.id", "observations.ward_id", "observations.source"],
            ondelete="RESTRICT",
            name="fk_weather_alerts_last_context",
        ),
        CheckConstraint("source IN ('simulator', 'provider')", name="ck_weather_alerts_source"),
        CheckConstraint(
            "(status = 'active' AND resolved_at IS NULL) OR "
            "(status = 'resolved' AND resolved_at IS NOT NULL)",
            name="ck_weather_alerts_resolution",
        ),
        CheckConstraint(
            "last_evaluated_at >= started_at AND "
            "(resolved_at IS NULL OR resolved_at >= started_at)",
            name="ck_weather_alerts_times",
        ),
        Index(
            "uq_weather_alerts_active",
            "ward_id",
            "source",
            "rule_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
        Index("ix_weather_alerts_status_started", "status", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    ward_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("wards.id", ondelete="RESTRICT"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("alert_rules.id", ondelete="RESTRICT"), nullable=False
    )
    started_by_observation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    last_observation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rule_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

`source/server/app/db/forecast.py` — **Code hiện tại**:

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class Forecast(Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["last_input_observation_id", "ward_id", "source"],
            ["observations.id", "observations.ward_id", "observations.source"],
            ondelete="RESTRICT",
            name="fk_forecasts_input_context",
        ),
        CheckConstraint("source IN ('simulator', 'provider')", name="ck_forecasts_source"),
        CheckConstraint(
            "method = 'persistence_baseline' AND is_ai = false",
            name="ck_forecasts_baseline",
        ),
        CheckConstraint(
            "input_from <= input_to AND target_at > input_to", name="ck_forecasts_window"
        ),
        Index("ix_forecasts_ward_source_target", "ward_id", "source", "target_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    ward_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("wards.id", ondelete="RESTRICT"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    last_input_observation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    target_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    predicted_temperature: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    is_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

`source/server/app/db/__init__.py` — **Code hiện tại**:

```python
from app.db.alert_rule import AlertRule
from app.db.base import Base
from app.db.forecast import Forecast
from app.db.province import Province
from app.db.user import User
from app.db.user_session import UserSession
from app.db.ward import Ward
from app.db.weather_alert import WeatherAlert
from app.db.weather_observation import WeatherObservation

__all__ = [
    "AlertRule",
    "Base",
    "Forecast",
    "Province",
    "User",
    "UserSession",
    "Ward",
    "WeatherAlert",
    "WeatherObservation",
]
```

Với WeatherObservation, chỉ dữ liệu legacy được phép ward_id NULL. Payload ward mới phải validate ward_id bắt buộc trước khi insert. Composite FK của Forecast/WeatherAlert dùng `(observation_id, ward_id, source)` với ward_id NOT NULL; nhờ đó không tham chiếu nhầm observation legacy hoặc ward/source khác. UUID vẫn là khóa idempotency; provider dùng UUID ổn định cho cùng ward/provider time, không tạo UUID mới khi retry.

`source/scripts/provider_weather.py` — **CHƯA TRIỂN KHAI**, helper dùng tọa độ đã nhận từ danh mục Ward, không phải request provider hoàn chỉnh:

```python
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class MonitoredWard:
    id: str
    latitude: Decimal
    longitude: Decimal


def build_current_weather_params(ward: MonitoredWard) -> dict[str, str]:
    return {
        "latitude": str(ward.latitude),
        "longitude": str(ward.longitude),
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,rain,showers",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "timeformat": "unixtime",
        "timezone": "GMT",
    }
```

Helper trên dùng cho endpoint forecast/current của provider đã cấu hình. Không dùng tọa độ GPS trực tiếp trong helper vì phạm vi mới là weather theo Ward. Adapter phải xác minh hợp đồng rain/showers và interval, chuyển lượng tích lũy mm thành mm/h nếu cần, không gán mm là mm/h. Timestamp Unix chuyển sang datetime UTC. Thiếu trường/unit không hợp lệ thì reject, không tự điền số 0. ID của MonitoredWard phải được gắn lại vào payload chuẩn hóa, không suy ID từ tọa độ ô lưới provider trả về.

`source/server/app/services/weather_queries.py` — **CHƯA TRIỂN KHAI**, đọc thẳng bản tin của ward đã lưu:

```python
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import WeatherObservation


async def latest_for_ward(
    session: AsyncSession,
    ward_id: str,
    source: Literal["provider", "simulator"] = "provider",
) -> WeatherObservation | None:
    return await session.scalar(
        select(WeatherObservation)
        .where(WeatherObservation.ward_id == ward_id, WeatherObservation.source == source)
        .order_by(WeatherObservation.observed_at.desc(), WeatherObservation.id.desc())
        .limit(1)
    )
```

`source/server/app/schemas/geography.py` — **Code hiện tại**:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NearestWardInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class NearestWardOutput(BaseModel):
    ward_id: str
    ward_name: str
    province_id: str
    province_name: str
    distance_km: float = Field(ge=0)
    match_type: Literal["nearest"] = "nearest"
```

`source/server/app/services/geography.py` — **Code hiện tại**:

```python
from collections.abc import Iterable
from dataclasses import dataclass
from math import asin, cos, isfinite, radians, sin, sqrt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Province, Ward

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class WardPoint:
    ward_id: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class WardMatch:
    ward_id: str
    distance_km: float


def validate_coordinates(latitude: float, longitude: float) -> None:
    if not isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("Invalid latitude")
    if not isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Invalid longitude")


def haversine_km(
    latitude: float,
    longitude: float,
    candidate_latitude: float,
    candidate_longitude: float,
) -> float:
    validate_coordinates(latitude, longitude)
    validate_coordinates(candidate_latitude, candidate_longitude)
    lat1, lat2 = radians(latitude), radians(candidate_latitude)
    delta_lat = lat2 - lat1
    delta_lon = radians(candidate_longitude - longitude)
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(min(1.0, max(0.0, value))))


def nearest_ward(
    latitude: float, longitude: float, candidates: Iterable[WardPoint]
) -> WardMatch | None:
    validate_coordinates(latitude, longitude)
    matches = (
        WardMatch(
            ward_id=point.ward_id,
            distance_km=haversine_km(latitude, longitude, point.latitude, point.longitude),
        )
        for point in candidates
    )
    return min(matches, key=lambda match: (match.distance_km, match.ward_id), default=None)


async def nearest_active_ward(
    session: AsyncSession, latitude: float, longitude: float
) -> WardMatch | None:
    validate_coordinates(latitude, longitude)
    rows = await session.scalars(
        select(Ward)
        .join(Province, Province.id == Ward.province_id)
        .where(
            Ward.is_active.is_(True),
            Province.is_active.is_(True),
            Ward.latitude.is_not(None),
            Ward.longitude.is_not(None),
        )
    )
    return nearest_ward(
        latitude,
        longitude,
        (WardPoint(ward.id, float(ward.latitude), float(ward.longitude)) for ward in rows),
    )
```

Route `POST /geography/nearest-ward` validate bằng NearestWardInput, gọi nearest_active_ward, đọc Ward/Province tương ứng để dựng NearestWardOutput. Match None trả 404. Route không gọi session.add/commit và không ghi user location; bước lưu riêng dùng PATCH /me/ward với user từ session. Raw GPS chỉ tồn tại trong request và biến tạm. Khi distance bằng nhau, quy tắc chọn mã nhỏ nhất áp dụng nhất quán cả khi snapshot có nhiều ward dùng chung tọa độ.

### Các file dự kiến triển khai — CHƯA TRIỂN KHAI

- Models: các module code ở trên trong `source/server/app/db/`; chỉ xóa `models.py` sau khi chuyển hết consumers. Giữ `session.py`; bật SQLite FK trên mọi connection dùng test constraints.
- Migration: `source/server/alembic/env.py`, file mới `alembic/versions/0002_wards_users_domain.py`; không sửa revision 0001.
- Danh mục: file mới `source/scripts/import_administrative_units.py`, snapshot có version trong `source/data/administrative/`; dữ liệu test phải ghi rõ là fixture, không giả mã thật.
- Backend: sửa `source/server/app/api/routes.py`, `app/main.py`, `core/config.py`, `schemas/weather.py`, `services/ingestion.py`, `services/alerts.py`, `services/forecast.py`, `network/hub.py`, `network/tcp.py`; thêm `api/geography.py`, `api/users.py`, `api/auth.py`, `schemas/geography.py`, `schemas/user.py`, `services/geography.py`, `services/weather_queries.py`, `core/security.py`.
- Producer: file mới `source/scripts/provider_weather.py`, `source/scripts/publish_provider_weather.py`; sửa `source/scripts/publish_weather.py` để có mode ward demo; mode city tạm giữ cho legacy.
- FE: sửa `source/client/src/App.tsx`, `src/lib/api.ts`, `src/hooks/useWeather.ts`, `src/styles.css`; thêm `src/hooks/useAuth.ts`, `src/hooks/useGeolocation.ts`, `src/components/WardPicker.tsx`, `src/components/AuthForm.tsx`.
- Tests: sửa `source/server/tests/conftest.py`, `tests/test_stream.py`; thêm `tests/test_domain_models.py`, `tests/test_geography.py`, `tests/test_wards.py`, `tests/test_auth.py`, `tests/test_migrations.py`, `tests/test_provider_adapter.py`; unit test helper publisher trong `source/scripts/tests/test_provider_weather.py`.
- Cấu hình khi cần: `source/server/requirements.txt`, `source/server/.env.example`, `.env.example`, `compose.yaml` cho HTTP client/hash password/session/provider process. Không sửa `.env` thật và không đặt token thật trong tài liệu.
- Tài liệu: `README.md`, `docs/01_PHAN_TICH_NGHIEP_VU.md`, `docs/02_THIET_KE_UML.md`, `docs/uml/source/02-domain-class.puml` và sơ đồ luồng/ảnh bị ảnh hưởng, `docs/KE_HOACH_VA_PHAN_CONG.md`. Giữ nguyên `INSTRUCTION.md`.

### Test model đề xuất — CHƯA TRIỂN KHAI

`source/server/tests/test_domain_models.py` — **Code hiện tại**:

```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import (
    AlertRule,
    Base,
    Forecast,
    Province,
    User,
    UserSession,
    Ward,
    WeatherAlert,
    WeatherObservation,
)
from app.schemas.weather import ObservationOut


@pytest.fixture
def schema_engine():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def add_ward(session, code="test-w1", name="Phường kiểm thử"):
    if session.get(Province, "test-p") is None:
        session.add(Province(id="test-p", name="Tỉnh kiểm thử", dataset_version="test-v1"))
        session.flush()
    ward = Ward(
        id=code,
        name=name,
        province_id="test-p",
        administrative_type="ward",
        latitude=Decimal("21.00000"),
        longitude=Decimal("105.00000"),
        dataset_version="test-v1",
    )
    session.add(ward)
    session.flush()
    return ward


def test_metadata_excludes_location_and_data_source():
    assert set(Base.metadata.tables) == {
        "provinces",
        "wards",
        "users",
        "user_sessions",
        "observations",
        "alert_rules",
        "weather_alerts",
        "forecasts",
    }
    for table in Base.metadata.tables.values():
        assert "location_id" not in table.c
        assert "source_id" not in table.c
        assert "model_version_id" not in table.c


def test_every_model_inherits_both_timestamps_from_base():
    for mapper in Base.registry.mappers:
        assert issubclass(mapper.class_, Base)
        assert "created_at" not in mapper.class_.__annotations__
        assert "updated_at" not in mapper.class_.__annotations__
        table = mapper.local_table
        assert table.c.created_at.nullable is False
        assert table.c.updated_at.nullable is False
        assert table.c.created_at.server_default is not None
        assert table.c.updated_at.server_default is not None
        assert table.c.updated_at.onupdate is not None


def test_timestamp_defaults_and_orm_updates(schema_engine):
    with Session(schema_engine) as session:
        ward = add_ward(session)
        session.commit()
        session.refresh(ward)
        assert ward.created_at is not None
        assert ward.updated_at is not None
        old_time = datetime(2000, 1, 1)
        ward.created_at = old_time
        ward.updated_at = old_time
        session.commit()
        ward.name = "Tên được cập nhật"
        session.commit()
        session.refresh(ward)
        assert ward.created_at == old_time
        assert ward.updated_at > old_time


def test_default_ward_and_coordinates_survive_reload(schema_engine):
    with Session(schema_engine) as session:
        ward = add_ward(session)
        user = User(
            email="person@example.test",
            full_name="Kiểm thử",
            password_hash="test-only",
            default_ward_id=ward.id,
            address_text="Địa chỉ riêng kiểm thử",
        )
        session.add(user)
        session.commit()
        user_id = user.id
    with Session(schema_engine) as session:
        restored = session.get(User, user_id)
        ward = session.get(Ward, restored.default_ward_id)
        assert ward.id == "test-w1"
        assert ward.latitude == Decimal("21.00000")
        assert ward.province_id == "test-p"
        assert restored.address_text == "Địa chỉ riêng kiểm thử"


def test_ward_requires_existing_province(schema_engine):
    with Session(schema_engine) as session:
        session.add(
            Ward(
                id="test-w",
                province_id="missing",
                name="Kiểm thử",
                administrative_type="ward",
                dataset_version="test-v1",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_weather_remains_after_deleting_user(schema_engine):
    now = datetime.now(UTC)
    with Session(schema_engine) as session:
        ward = add_ward(session)
        user = User(
            email="person@example.test",
            full_name="Kiểm thử",
            password_hash="test-only",
            default_ward_id=ward.id,
        )
        session.add(user)
        session.flush()
        observation = WeatherObservation(
            id=str(uuid4()),
            ward_id=ward.id,
            legacy_city=None,
            temperature=30,
            humidity=70,
            wind_speed=10,
            rainfall=0,
            source="simulator",
            observed_at=now,
        )
        session.add(observation)
        session.add(
            UserSession(
                token_hash="a" * 64,
                user_id=user.id,
                created_at=now,
                expires_at=now + timedelta(days=7),
            )
        )
        session.commit()
        observation_id = observation.id
        session.delete(user)
        session.commit()
        session.expire_all()
        assert session.get(UserSession, "a" * 64) is None
        assert session.get(WeatherObservation, observation_id).ward_id == "test-w1"
        session.delete(session.get(Ward, "test-w1"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_legacy_city_data_is_not_assigned_to_a_ward(schema_engine):
    with Session(schema_engine) as session:
        observation = WeatherObservation(
            id=str(uuid4()),
            ward_id=None,
            legacy_city="hanoi",
            temperature=30,
            humidity=70,
            wind_speed=10,
            rainfall=0,
            source="simulator",
            observed_at=datetime.now(UTC),
        )
        session.add(observation)
        session.commit()
        assert session.get(WeatherObservation, observation.id).ward_id is None
        assert (
            session.scalars(
                select(WeatherObservation).where(WeatherObservation.ward_id == "test-w1")
            ).all()
            == []
        )
        output = ObservationOut.model_validate(observation)
        assert output.city == "hanoi"
        assert ObservationOut.model_validate(output.model_dump()).city == "hanoi"


def add_observation(session):
    ward = add_ward(session)
    now = datetime.now(UTC)
    record = WeatherObservation(
        id=str(uuid4()),
        ward_id=ward.id,
        source="simulator",
        observed_at=now,
        temperature=30,
        humidity=70,
        wind_speed=10,
        rainfall=0,
    )
    session.add(record)
    session.flush()
    return record


@pytest.mark.parametrize("wrong_context", ["ward", "source"])
def test_forecast_rejects_input_from_a_different_ward_or_source(schema_engine, wrong_context):
    with Session(schema_engine) as session:
        observation = add_observation(session)
        another = add_ward(session, code="test-w2")
        session.add(
            Forecast(
                ward_id=another.id if wrong_context == "ward" else observation.ward_id,
                source="provider" if wrong_context == "source" else observation.source,
                last_input_observation_id=observation.id,
                input_from=observation.observed_at,
                input_to=observation.observed_at,
                target_at=observation.observed_at + timedelta(hours=1),
                predicted_temperature=30,
                method="persistence_baseline",
                is_ai=False,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_forecast_supports_only_the_current_baseline(schema_engine):
    with Session(schema_engine) as session:
        observation = add_observation(session)
        values = {
            "ward_id": observation.ward_id,
            "source": observation.source,
            "last_input_observation_id": observation.id,
            "input_from": observation.observed_at,
            "input_to": observation.observed_at,
            "target_at": observation.observed_at + timedelta(hours=1),
            "predicted_temperature": 30,
        }
        session.add(Forecast(**values, method="persistence_baseline", is_ai=False))
        session.commit()
        session.add(Forecast(**values, method="model", is_ai=True))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_only_one_active_alert_episode_per_ward_source_and_rule(schema_engine):
    with Session(schema_engine) as session:
        observation = add_observation(session)
        rule = AlertRule(
            rule_key="heat",
            version=1,
            metric="temperature",
            operator="gte",
            threshold=35,
            severity="warning",
        )
        session.add(rule)
        session.flush()
        values = {
            "ward_id": observation.ward_id,
            "source": observation.source,
            "rule_id": rule.id,
            "started_by_observation_id": observation.id,
            "started_at": observation.observed_at,
            "last_evaluated_at": observation.observed_at,
            "rule_snapshot": {"threshold": 35},
        }
        session.add(WeatherAlert(**values, status="active"))
        session.commit()
        session.add(WeatherAlert(**values, status="active"))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
```

`source/scripts/tests/test_provider_weather.py` — **CHƯA TRIỂN KHAI**; kiểm tra đúng tọa độ lưu trong Ward được dùng, helper import theo file để không phụ thuộc PYTHONPATH server:

```python
import importlib.util
import sys
from decimal import Decimal
from pathlib import Path


def test_request_uses_stored_ward_coordinates():
    path = Path(__file__).resolve().parents[1] / "provider_weather.py"
    spec = importlib.util.spec_from_file_location("provider_weather_for_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        ward = module.MonitoredWard(
            id="test-w", latitude=Decimal("21.01234"), longitude=Decimal("105.12345")
        )
        params = module.build_current_weather_params(ward)
        assert params["latitude"] == "21.01234"
        assert params["longitude"] == "105.12345"
        assert params["timezone"] == "GMT"
    finally:
        sys.modules.pop(spec.name, None)
```

`source/server/tests/test_geography.py` — **Code hiện tại**:

```python
import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, Province, Ward
from app.schemas.geography import NearestWardInput
from app.services.geography import (
    WardPoint,
    haversine_km,
    nearest_active_ward,
    nearest_ward,
)


def test_nearest_ward_selects_shortest_distance():
    result = nearest_ward(
        21.0,
        105.0,
        [
            WardPoint("far", 22.0, 105.0),
            WardPoint("near", 21.001, 105.0),
        ],
    )
    assert result.ward_id == "near"
    assert result.distance_km == pytest.approx(0.111195, abs=0.00001)


def test_equal_coordinates_have_stable_tie_break():
    result = nearest_ward(
        21.0,
        105.0,
        [
            WardPoint("test-w2", 21.0, 105.0),
            WardPoint("test-w1", 21.0, 105.0),
        ],
    )
    assert result.ward_id == "test-w1"
    assert result.distance_km == 0


def test_empty_candidates_and_valid_zero_coordinates():
    assert nearest_ward(21.0, 105.0, []) is None
    assert haversine_km(0.0, 0.0, 0.0, 1.0) == pytest.approx(111.19508, abs=0.0001)


@pytest.mark.parametrize(
    "latitude,longitude",
    [
        (91.0, 105.0),
        (-91.0, 105.0),
        (21.0, 181.0),
        (21.0, -181.0),
        (float("nan"), 105.0),
        (21.0, float("inf")),
    ],
)
def test_invalid_coordinates_rejected(latitude, longitude):
    with pytest.raises(ValidationError):
        NearestWardInput(latitude=latitude, longitude=longitude)
    with pytest.raises(ValueError):
        nearest_ward(latitude, longitude, [])


def test_only_active_wards_with_coordinates_are_candidates(tmp_path):
    async def scenario():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'geography.db'}")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add_all(
                    [
                        Province(id="active-p", name="Tỉnh kiểm thử", dataset_version="test"),
                        Province(
                            id="inactive-p", name="Tỉnh cũ", dataset_version="test", is_active=False
                        ),
                    ]
                )
                await session.flush()
                for code, province_id, active, latitude, longitude in [
                    ("eligible", "active-p", True, "21.001", "105"),
                    ("inactive-ward", "active-p", False, "21", "105"),
                    ("inactive-province", "inactive-p", True, "21", "105"),
                    ("missing-coordinates", "active-p", True, None, None),
                ]:
                    session.add(
                        Ward(
                            id=code,
                            province_id=province_id,
                            name=code,
                            administrative_type=None,
                            dataset_version="test",
                            is_active=active,
                            latitude=Decimal(latitude) if latitude is not None else None,
                            longitude=Decimal(longitude) if longitude is not None else None,
                        )
                    )
                await session.commit()
                result = await nearest_active_ward(session, 21.0, 105.0)
                assert result.ward_id == "eligible"
        finally:
            await engine.dispose()

    asyncio.run(scenario())
```

## 6. Kế hoạch kiểm thử

Các mục dưới đây là kế hoạch kiểm thử cho toàn bộ thiết kế. Kết quả thực thi nằm ở đầu tài liệu: Ruff pass, 62 tests pass, frontend build pass; migration kiểm chứng trên SQLite tạm. Các luồng auth/provider/ward streaming và FE định vị chưa thuộc phần đã triển khai.

1. Chạy test model/helper ở mục 5: không có bảng Location/DataSource; Ward thuộc đúng Province; user khôi phục đúng ward; tọa độ đã lưu đi vào provider params; xóa user không mất thời tiết.
2. Kiểm tra REST current/history/forecast theo ward/source: dữ liệu mới nhất đúng observed_at, không lẫn ward; chưa có provider thì báo trạng thái phù hợp, không tự thay số simulator. Composite FK chặn observation khác ward/source, active episode/AI baseline constraints đúng.
3. Import snapshot: tên trùng khác mã vẫn được, mã trùng bị phát hiện, tọa độ thiếu chỉ lưu danh mục, sai tọa độ bị reject, inactive ward không chọn mới. Giữ record cũ khi cập nhật danh mục.
4. Định vị: Haversine chọn tọa độ ward gần nhất, đồng hạng xử lý ổn định; chỉ xét province/ward active có tọa độ. Input thiếu, NaN, infinity hoặc ngoài miền bị reject. Danh mục rỗng/không có ứng viên trả 404 và cho chọn tay. Tọa độ trùng giữa các ward được phép. Không cần reverse geocoding/boundary lookup; không lưu tọa độ user.
5. Migration trên SQLite/PostgreSQL test: 0001 có city → head giữ nguyên UUID/chỉ số/source/time/row count; ward_id NULL cho legacy, city không bị mất; không hiển thị legacy thành ward. Kiểm tra đường downgrade được phép và chặn đường có nguy cơ mất dữ liệu.
6. Stream: TCP split/coalesced frames, duplicate UUID không insert/broadcast lại, ACK sau commit, subscriber chỉ nhận ward đang xem, city legacy không trộn namespace. Unknown ward trả lỗi validation phù hợp trước khi chạm FK.
7. Provider adapter: mock timeout/retry/units/UTC, interval mưa, UUID ổn định, mỗi ward chỉ một request trong TTL; không poll toàn bộ danh mục. Không coi weather mô hình provider là đo tại từng nhà; nhãn simulator/provider và AI baseline đúng.
8. Auth/FE: đăng nhập → bấm dùng vị trí làm mặc định → lấy vị trí một lần → chọn ward gần nhất → lưu ward A → mở lại FE tự vào A mà không gọi lại định vị. User B không xem/sửa địa chỉ A. Session sai/hết hạn/thu hồi; cookie và Origin policy cho mutations; response không lộ hash. Đổi tỉnh xóa ward cũ; xem thử B không ghi đè A; GPS từ chối quyền hoặc lưu thất bại giữ mặc định cũ. Khách chỉ xem và được nhắc đăng nhập nếu muốn lưu. Hủy request/socket khi đổi ward/user.

Lệnh sau khi triển khai backend, tại source/server:

```bash
ruff check .
pytest -q
# Chỉ cấu hình DB test riêng khi kiểm chứng migration:
alembic upgrade head
# Chạy thêm test helper producer nằm ngoài server testpaths:
pytest -q ../scripts/tests/test_provider_weather.py
```

Lệnh sau khi triển khai frontend, tại source/client:

```bash
npm run build
```

**Bàn giao phần model/dữ liệu nền:** đã có Province/Ward, User.default_ward_id và các model còn lại, migration, snapshot/importer cùng API chọn ward gần nhất bằng Haversine. Luồng city cũ được giữ tương thích. Các bước auth, FE và provider/streaming theo ward tiếp tục theo thứ tự ở mục 3.6; chưa áp dụng migration/import lên database thật.
