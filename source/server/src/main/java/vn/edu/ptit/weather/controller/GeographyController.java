package vn.edu.ptit.weather.controller;

import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import java.util.Locale;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import vn.edu.ptit.weather.dto.*;
import vn.edu.ptit.weather.dto.GeographyDto.*;
import vn.edu.ptit.weather.service.GeographyService;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class GeographyController {
  private final GeographyService service;

  @GetMapping("/provinces")
  public ApiResponse<?> provinces(
      @RequestParam(defaultValue = "") String q,
      @RequestParam(defaultValue = "1") int page,
      @RequestParam(name = "page_size", defaultValue = "25") int size,
      HttpServletResponse response) {
    PageResponse.validate(page, size);
    if (q.length() > 150)
      throw new vn.edu.ptit.weather.exception.ApiException(422, "Từ khóa quá dài.");
    var catalog = service.provinces();
    if (catalog.stale()) response.setHeader("X-Data-Stale", "true");
    var rows =
        catalog.rows().stream()
            .filter(p -> p.getName().toLowerCase(Locale.ROOT).contains(q.toLowerCase(Locale.ROOT)))
            .map(ProvinceResponse::from)
            .toList();
    return ApiResponse.ok(PageResponse.of(rows, page, size));
  }

  @GetMapping("/provinces/{id}")
  public ApiResponse<?> province(@PathVariable String id) {
    return ApiResponse.ok(ProvinceResponse.from(service.province(id)));
  }

  @GetMapping("/wards")
  public ApiResponse<?> wards(
      @RequestParam(name = "province_id", required = false) String provinceId,
      @RequestParam(defaultValue = "") String q,
      @RequestParam(defaultValue = "1") int page,
      @RequestParam(name = "page_size", defaultValue = "25") int size,
      HttpServletResponse response) {
    PageResponse.validate(page, size);
    if (q.length() > 150
        || (provinceId != null && (provinceId.isEmpty() || provinceId.length() > 20)))
      throw new vn.edu.ptit.weather.exception.ApiException(422, "Bộ lọc không hợp lệ.");
    var catalog = service.wards(provinceId);
    if (catalog.stale()) response.setHeader("X-Data-Stale", "true");
    var rows =
        catalog.rows().stream()
            .filter(w -> w.getName().toLowerCase(Locale.ROOT).contains(q.toLowerCase(Locale.ROOT)))
            .map(WardResponse::from)
            .toList();
    return ApiResponse.ok(PageResponse.of(rows, page, size));
  }

  @GetMapping("/wards/{id}")
  public ApiResponse<?> ward(@PathVariable String id) {
    return ApiResponse.ok(WardResponse.from(service.ward(id)));
  }

  @PostMapping("/geography/nearest-ward")
  public ApiResponse<?> nearest(@Valid @RequestBody NearestRequest request) {
    return ApiResponse.ok(service.nearest(request));
  }
}
