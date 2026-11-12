package vn.edu.ptit.weather.service;

import com.fasterxml.jackson.databind.JsonNode;
import java.time.*;
import java.time.temporal.ChronoUnit;
import java.util.*;
import org.springframework.stereotype.Service;
import vn.edu.ptit.weather.entity.Ward;
import vn.edu.ptit.weather.exception.ApiException;

@Service
public class ForecastService {
  private final GeographyService geography;
  private final OpenMeteoClient provider;
  private final Clock clock;
  private final SharedRequests previews = new SharedRequests(2, 32);

  @org.springframework.beans.factory.annotation.Autowired
  public ForecastService(GeographyService geography, OpenMeteoClient provider) {
    this(geography, provider, Clock.systemUTC());
  }

  public ForecastService(GeographyService geography, OpenMeteoClient provider, Clock clock) {
    this.geography = geography;
    this.provider = provider;
    this.clock = clock;
  }

  @jakarta.annotation.PreDestroy
  public void close() {
    previews.close();
  }

  private final Map<String, Cached> cache = new LinkedHashMap<>();

  private record Cached(Instant expires, Object value) {}

  private static final Map<String, String> HOURLY_UNITS =
      Map.of(
          "temperature_2m",
          "°C",
          "relative_humidity_2m",
          "%",
          "wind_speed_10m",
          "km/h",
          "precipitation",
          "mm",
          "precipitation_probability",
          "%",
          "rain",
          "mm",
          "showers",
          "mm",
          "weather_code",
          "wmo code");
  private static final Map<String, String> DAILY_UNITS =
      Map.of(
          "temperature_2m_min",
          "°C",
          "temperature_2m_max",
          "°C",
          "precipitation_sum",
          "mm",
          "precipitation_probability_max",
          "%",
          "wind_speed_10m_max",
          "km/h");

  static Map<String, Object> object(Object... values) {
    var map = new LinkedHashMap<String, Object>();
    for (int i = 0; i < values.length; i += 2) map.put((String) values[i], values[i + 1]);
    return map;
  }

  private JsonNode load(Ward ward, int days, boolean daily) {
    return load(ward.getLatitude().doubleValue(), ward.getLongitude().doubleValue(), days, daily);
  }

  private JsonNode load(double lat, double lon, int days, boolean daily) {
    var options = new HashMap<String, String>();
    options.put("hourly", String.join(",", HOURLY_UNITS.keySet()));
    options.put("forecast_days", Integer.toString(days));
    if (daily) options.put("daily", String.join(",", DAILY_UNITS.keySet()));
    var data = provider.fetch(lat, lon, options);
    OpenMeteoClient.units(data, "hourly", HOURLY_UNITS);
    OpenMeteoClient.series(data, "hourly", HOURLY_UNITS.keySet());
    if (daily) {
      OpenMeteoClient.units(data, "daily", DAILY_UNITS);
      OpenMeteoClient.series(data, "daily", DAILY_UNITS.keySet());
    }
    return data;
  }

  private static Double value(JsonNode block, String field, int index, double min, double max) {
    var n = block.path(field).get(index);
    return n == null || n.isNull() ? null : OpenMeteoClient.number(n, min, max);
  }

  private static Map<String, Object> hour(JsonNode block, int i, boolean future) {
    var row =
        object(
            "time",
            Instant.ofEpochSecond(block.path("time").get(i).asLong()),
            "temperature",
            value(block, "temperature_2m", i, -60, 65),
            "humidity",
            value(block, "relative_humidity_2m", i, 0, 100),
            "wind_speed",
            value(block, "wind_speed_10m", i, 0, 500),
            future ? "rainfall" : "precipitation",
            value(block, "precipitation", i, 0, 1000),
            "rain_probability",
            value(block, "precipitation_probability", i, 0, 100));
    if (future) {
      row.put("rain", value(block, "rain", i, 0, 1000));
      row.put("showers", value(block, "showers", i, 0, 1000));
      var code = block.path("weather_code").get(i);
      if (code != null && !code.isNull() && !code.isIntegralNumber())
        throw new ApiException(503, "Mã thời tiết không hợp lệ.");
      row.put("weather_code", value(block, "weather_code", i, 0, 99));
    }
    return row;
  }

  public Object preview(String wardId) {
    Ward ward = geography.coordinates(wardId);
    for (int attempt = 0; attempt < 2; attempt++) {
      Instant target = clock.instant().truncatedTo(ChronoUnit.HOURS).plus(1, ChronoUnit.HOURS);
      String key =
          wardId
              + ":"
              + ward.getLatitude()
              + ":"
              + ward.getLongitude()
              + ":"
              + target.getEpochSecond();
      @SuppressWarnings("unchecked")
      var result = (Map<String, Object>) previews.get(key, () -> previewAt(ward, target));
      if (((Instant) result.get("target_at")).isAfter(clock.instant())) return result;
    }
    throw new ApiException(503, "Mốc dự báo đã hết hạn trong lúc tải.");
  }

  private Object previewAt(Ward ward, Instant target) {
    String wardId = ward.getId();
    var fields =
        Map.of(
            "time",
            "unixtime",
            "temperature_2m",
            "°C",
            "relative_humidity_2m",
            "%",
            "wind_speed_10m",
            "km/h",
            "precipitation",
            "mm");
    var payload =
        provider.fetch(
            ward.getLatitude().doubleValue(),
            ward.getLongitude().doubleValue(),
            Map.of(
                "hourly",
                "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
                "forecast_hours",
                "3",
                "timezone",
                "UTC"));
    OpenMeteoClient.units(payload, "hourly", fields);
    OpenMeteoClient.series(payload, "hourly", fields.keySet());
    var h = payload.path("hourly");
    var now = clock.instant();
    for (int i = 0; i < h.path("time").size(); i++)
      if (h.path("time").get(i).asLong() == target.getEpochSecond()) {
        var row =
            object(
                "temperature",
                value(h, "temperature_2m", i, -60, 65),
                "humidity",
                value(h, "relative_humidity_2m", i, 0, 100),
                "wind_speed",
                value(h, "wind_speed_10m", i, 0, 500),
                "precipitation",
                value(h, "precipitation", i, 0, 1000));
        if (List.of("temperature", "humidity", "wind_speed", "precipitation").stream()
            .anyMatch(key -> row.get(key) == null))
          throw new ApiException(503, "Thiếu dự báo giờ tiếp theo.");
        return object(
            "ward_id",
            wardId,
            "provider",
            "open_meteo",
            "method",
            "open_meteo_hourly",
            "data_kind",
            "model_forecast",
            "target_at",
            target,
            "fetched_at",
            now,
            "predicted_temperature",
            row.get("temperature"),
            "predicted_humidity",
            row.get("humidity"),
            "predicted_wind_speed",
            row.get("wind_speed"),
            "precipitation_mm",
            row.get("precipitation"),
            "interval_seconds",
            3600);
      }
    throw new ApiException(503, "Chưa có dự báo giờ tiếp theo.");
  }

  public synchronized Object future(String wardId) {
    Ward ward = geography.coordinates(wardId);
    String key = "ward:" + wardId;
    var cached = cache.get(key);
    if (cached != null && cached.expires().isAfter(clock.instant())) return cached.value();
    Instant now = clock.instant(),
        start = now.truncatedTo(ChronoUnit.HOURS).plus(1, ChronoUnit.HOURS);
    var h = load(ward, 8, false).path("hourly");
    var rows = new ArrayList<Map<String, Object>>();
    for (int i = 0; i < h.path("time").size() && rows.size() < 168; i++)
      if (h.path("time").get(i).asLong() >= start.getEpochSecond()) rows.add(hour(h, i, true));
    if (rows.isEmpty()) throw new ApiException(503, "Chưa có dự báo tương lai.");
    Object result =
        object(
            "ward_id",
            wardId,
            "ward_name",
            ward.getName(),
            "province_id",
            ward.getProvinceId(),
            "source",
            "open-meteo",
            "data_kind",
            "model_forecast",
            "is_project_ai",
            false,
            "timezone",
            "Asia/Ho_Chi_Minh",
            "retrieved_at",
            now,
            "days",
            7,
            "hours",
            rows.size(),
            "interval_seconds",
            3600,
            "units",
            object(
                "temperature",
                "°C",
                "humidity",
                "%",
                "wind_speed",
                "km/h",
                "rainfall",
                "mm/giờ",
                "rain_probability",
                "%",
                "rain",
                "mm/giờ",
                "showers",
                "mm/giờ"),
            "hourly",
            rows);
    remember(key, result);
    return result;
  }

  public synchronized Object city(String city, int days) {
    if (days < 1 || days > 16) throw new ApiException(422, "Số ngày phải từ 1 đến 16.");
    double[] coordinates =
        switch (city) {
          case "hanoi" -> new double[] {21.0285, 105.8542};
          case "danang" -> new double[] {16.0544, 108.2022};
          case "hcm" -> new double[] {10.8231, 106.6297};
          default -> throw new ApiException(422, "Thành phố không hợp lệ.");
        };
    String key = "city:" + city + ":" + days;
    var cached = cache.get(key);
    if (cached != null && cached.expires().isAfter(clock.instant())) return cached.value();
    com.fasterxml.jackson.databind.JsonNode payload;
    try {
      payload = load(coordinates[0], coordinates[1], days, true);
    } catch (ApiException e) {
      throw new ApiException(502, "Không lấy được dự báo Open-Meteo. Vui lòng thử lại sau.");
    }
    var h = payload.path("hourly");
    var d = payload.path("daily");
    var hourly = new ArrayList<Map<String, Object>>();
    for (int i = 0; i < h.path("time").size(); i++) hourly.add(hour(h, i, false));
    var daily = new ArrayList<Map<String, Object>>();
    for (int i = 0; i < d.path("time").size(); i++)
      daily.add(
          object(
              "date",
              Instant.ofEpochSecond(d.path("time").get(i).asLong())
                  .atZone(ZoneId.of("Asia/Ho_Chi_Minh"))
                  .toLocalDate(),
              "temperature_min",
              value(d, "temperature_2m_min", i, -60, 65),
              "temperature_max",
              value(d, "temperature_2m_max", i, -60, 65),
              "precipitation_sum",
              value(d, "precipitation_sum", i, 0, 10000),
              "rain_probability_max",
              value(d, "precipitation_probability_max", i, 0, 100),
              "wind_speed_max",
              value(d, "wind_speed_10m_max", i, 0, 500)));
    Object result =
        object(
            "city",
            city,
            "source",
            "open-meteo",
            "is_project_ai",
            false,
            "retrieved_at",
            clock.instant(),
            "timezone",
            "Asia/Ho_Chi_Minh",
            "hourly",
            hourly,
            "daily",
            daily);
    remember(key, result);
    return result;
  }

  private void remember(String key, Object value) {
    cache.entrySet().removeIf(e -> e.getValue().expires().isBefore(clock.instant()));
    if (cache.size() >= 256) cache.remove(cache.keySet().iterator().next());
    cache.put(key, new Cached(clock.instant().plusSeconds(900), value));
  }
}
