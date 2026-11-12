package vn.edu.ptit.weather.controller;

import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.*;
import vn.edu.ptit.weather.dto.ApiResponse;
import vn.edu.ptit.weather.service.*;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class WeatherController {
  private final CurrentWeatherService current;
  private final ForecastService forecasts;
  private final ObservationService observations;

  @Value("${weather.source}")
  private String source;

  @GetMapping("/wards/{id}/weather/current")
  public ApiResponse<?> current(@PathVariable String id, HttpServletResponse response) {
    response.setHeader("Cache-Control", "no-store");
    return ApiResponse.ok(current.current(id));
  }

  @GetMapping("/wards/{id}/weather/history")
  public ApiResponse<?> history(
      @PathVariable String id,
      @RequestParam(defaultValue = "1") int page,
      @RequestParam(name = "page_size", defaultValue = "25") int size) {
    return ApiResponse.ok(observations.history(id, source, page, size));
  }

  @GetMapping("/wards/{id}/weather/forecast")
  public ApiResponse<?> preview(@PathVariable String id, HttpServletResponse response) {
    response.setHeader("Cache-Control", "no-store");
    return ApiResponse.ok(forecasts.preview(id));
  }

  @GetMapping("/wards/{id}/weather/future")
  public ApiResponse<?> future(@PathVariable String id, HttpServletResponse response) {
    response.setHeader("Cache-Control", "no-store");
    return ApiResponse.ok(forecasts.future(id));
  }

  @GetMapping("/weather/{city}/provider-forecast")
  public ApiResponse<?> city(
      @PathVariable String city, @RequestParam(defaultValue = "7") int days) {
    try {
      return ApiResponse.ok(forecasts.city(city, days));
    } catch (vn.edu.ptit.weather.exception.ApiException e) {
      if (e.getStatus() == 503)
        throw new vn.edu.ptit.weather.exception.ApiException(
            502, "Không lấy được dự báo Open-Meteo. Vui lòng thử lại sau.");
      throw e;
    }
  }
}
