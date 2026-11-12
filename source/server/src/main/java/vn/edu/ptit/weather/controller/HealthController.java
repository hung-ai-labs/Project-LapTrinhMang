package vn.edu.ptit.weather.controller;

import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import vn.edu.ptit.weather.dto.ApiResponse;

@RestController
@RequiredArgsConstructor
public class HealthController {
  private final JdbcTemplate database;

  @GetMapping("/api/v1/health")
  public ApiResponse<?> health() {
    database.queryForObject("SELECT 1", Integer.class);
    return ApiResponse.ok(Map.of("status", "ok", "database", "ok"));
  }
}
