package vn.edu.ptit.weather.dto;

import java.util.List;
import org.springframework.web.servlet.support.ServletUriComponentsBuilder;
import vn.edu.ptit.weather.exception.ApiException;

public record PageResponse<T>(long count, String next, String previous, List<T> results) {
  public static void validate(int page, int size) {
    if (page < 1 || size < 1 || size > 100)
      throw new ApiException(422, "page/page_size không hợp lệ.");
  }

  public static <T> PageResponse<T> of(List<T> all, int page, int size) {
    validate(page, size);
    long offset = (page - 1L) * size;
    if (page > Math.max(1, (all.size() + size - 1) / size))
      throw new ApiException(404, "Trang không tồn tại.");
    return window(
        all.size(),
        all.subList((int) offset, (int) Math.min(offset + size, all.size())),
        page,
        size);
  }

  public static <T> PageResponse<T> window(long count, List<T> rows, int page, int size) {
    if (page > Math.max(1, (count + size - 1) / size))
      throw new ApiException(404, "Trang không tồn tại.");
    return new PageResponse<>(
        count,
        page * (long) size < count ? link(page + 1, size) : null,
        page > 1 ? link(page - 1, size) : null,
        rows);
  }

  private static String link(int page, int size) {
    return ServletUriComponentsBuilder.fromCurrentRequest()
        .replaceQueryParam("page", page)
        .replaceQueryParam("page_size", size)
        .build()
        .toUriString();
  }
}
