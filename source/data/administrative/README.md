# Danh mục tỉnh và phường/xã

Snapshot dùng cho model `Province`/`Ward` và tìm khu vực thời tiết gần nhất.

- Nguồn: [Open Admin Data — Vietnam Administrative Divisions](https://github.com/open-admin-data/vietnam-administrative-divisions).
- Tác giả nguồn: jakkrapongt / Open Admin Data.
- Giấy phép: [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/), bản thông báo của nguồn nằm trong `LICENSE`.
- Commit nguồn: `54cdb052284b02e75dfaa44089ca383aa12c57db`.
- Quy mô snapshot: 34 tỉnh/thành, 3.321 đơn vị cấp xã; có đủ cặp tọa độ trong snapshot này.

`snapshot.json` là bản chuyển đổi từ `data/all-province.json` và `data/all-ward.json` của nguồn: giữ mã, tên tiếng Việt, mã tỉnh cha và tọa độ; bỏ các trường song ngữ, slug, ancestors và metadata không dùng. `administrative_type` để `null` vì nguồn không xác định riêng xã/phường/đặc khu trong trường cấp đơn vị. Không suy loại đơn vị từ tên.

`manifest.json` ghi URL và SHA-256 của từng file nguồn, commit, ngày tải và SHA-256 của snapshot đã chuyển đổi. Importer kiểm tra hash, phiên bản, số lượng, mã trùng, quan hệ tỉnh/xã và miền tọa độ trước khi ghi. Việc kiểm tra này không chứng minh độ chính xác thực địa của từng điểm.

Từ `source/server`, dùng môi trường Python của backend:

```bash
# Chỉ đọc và kiểm tra; không kết nối database:
python ../scripts/import_administrative_units.py

# Tạo schema trên DATABASE_URL bạn đã cấu hình, rồi nhập toàn bộ danh mục:
alembic upgrade head
python ../scripts/import_administrative_units.py --apply
```

Nhập lại cùng snapshot không nhân bản dữ liệu. Snapshot là **danh mục đầy đủ**: mã không còn xuất hiện sẽ được đánh dấu `is_active=false`, không xóa record đang được user hoặc thời tiết tham chiếu. Không dùng importer này để nhập một danh mục con.

Để cập nhật dữ liệu, tải các file từ cùng một commit nguồn, tạo lại snapshot/manifest và giữ ghi nhận nguồn cùng giấy phép. Kiểm tra các thay đổi mã và quan hệ hành chính trước khi áp dụng. Không đưa token, URL database hay thông tin tài khoản vào snapshot.
