package vn.edu.ptit.weather.service;

import java.time.Instant;
import java.util.*;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;
import vn.edu.ptit.weather.dto.GeographyDto.*;
import vn.edu.ptit.weather.entity.*;
import vn.edu.ptit.weather.exception.ApiException;
import vn.edu.ptit.weather.repository.*;

@Service
public class GeographyService {
  private final ProvinceRepository provinces;
  private final WardRepository wards;
  private final java.time.Clock clock;
  private Snapshot snapshot;

  private record Snapshot(List<Province> provinces, List<Ward> wards, Instant loadedAt) {}

  @org.springframework.beans.factory.annotation.Autowired
  public GeographyService(ProvinceRepository provinces, WardRepository wards) {
    this(provinces, wards, java.time.Clock.systemUTC());
  }

  public GeographyService(
      ProvinceRepository provinces, WardRepository wards, java.time.Clock clock) {
    this.provinces = provinces;
    this.wards = wards;
    this.clock = clock;
  }

  public record Catalog<T>(List<T> rows, Instant loadedAt, boolean stale) {}

  private synchronized Snapshot snapshot() {
    if (snapshot != null && snapshot.loadedAt().plusSeconds(600).isAfter(clock.instant()))
      return snapshot;
    try {
      var provinceRows = List.copyOf(provinces.findByIsActiveTrueOrderByNameAsc());
      var wardRows = List.copyOf(wards.findByIsActiveTrueOrderByNameAsc());
      snapshot = new Snapshot(provinceRows, wardRows, clock.instant());
    } catch (DataAccessException e) {
      if (snapshot == null)
        throw new ApiException(
            503, "Chưa tải được danh mục tỉnh/thành (mất kết nối cơ sở dữ liệu). Thử lại sau.");
    }
    return snapshot;
  }

  public Catalog<Province> provinces() {
    var data = snapshot();
    return new Catalog<>(
        data.provinces(),
        data.loadedAt(),
        !data.loadedAt().plusSeconds(600).isAfter(clock.instant()));
  }

  public Catalog<Ward> wards(String provinceId) {
    var data = snapshot();
    var selected =
        data.wards().stream()
            .filter(w -> provinceId == null || provinceId.equals(w.getProvinceId()))
            .toList();
    return new Catalog<>(
        selected, data.loadedAt(), !data.loadedAt().plusSeconds(600).isAfter(clock.instant()));
  }

  public Province province(String id) {
    return provinces
        .findById(id)
        .filter(Province::isActive)
        .orElseThrow(() -> new ApiException(404, "Không tìm thấy tỉnh/thành đang hoạt động."));
  }

  public Ward ward(String id) {
    return wards
        .findActiveById(id)
        .orElseThrow(() -> new ApiException(404, "Không tìm thấy phường/xã đang hoạt động."));
  }

  public Ward savedWard(String id) {
    return wards.findById(id).orElse(null);
  }

  public vn.edu.ptit.weather.entity.Province savedProvince(String id) {
    return provinces.findById(id).orElse(null);
  }

  public Ward coordinates(String id) {
    Ward ward = ward(id);
    if (ward.getLatitude() == null || ward.getLongitude() == null)
      throw new ApiException(422, "Phường/xã chưa có tọa độ.");
    return ward;
  }

  public NearestResponse nearest(NearestRequest request) {
    Ward nearest = null;
    double distance = Double.MAX_VALUE;
    for (Ward ward : wards(null).rows()) {
      if (ward.getLatitude() == null || ward.getLongitude() == null) continue;
      double d =
          distance(
              request.latitude(),
              request.longitude(),
              ward.getLatitude().doubleValue(),
              ward.getLongitude().doubleValue());
      if (d < distance) {
        nearest = ward;
        distance = d;
      }
    }
    if (nearest == null) throw new ApiException(404, "Chưa có phường/xã có tọa độ.");
    return new NearestResponse(
        WardResponse.from(nearest),
        ProvinceResponse.from(province(nearest.getProvinceId())),
        distance,
        "nearest");
  }

  static double distance(double lat1, double lon1, double lat2, double lon2) {
    double a =
        Math.pow(Math.sin(Math.toRadians(lat2 - lat1) / 2), 2)
            + Math.cos(Math.toRadians(lat1))
                * Math.cos(Math.toRadians(lat2))
                * Math.pow(Math.sin(Math.toRadians(lon2 - lon1) / 2), 2);
    return 6371.0088 * 2 * Math.asin(Math.sqrt(Math.min(1, a)));
  }
}
