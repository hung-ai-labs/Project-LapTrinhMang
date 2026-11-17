package vn.edu.ptit.weather.tool;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.LinkedHashMap;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import vn.edu.ptit.weather.service.ChatTool;
import vn.edu.ptit.weather.service.GeographyService;
import vn.edu.ptit.weather.service.OpenMeteoClient;

/**
 * Everything the assistant needs to advise on clothing and protection: UV and air quality from the
 * Open-Meteo air-quality host, felt temperature and gusts from the forecast host. Both upstream
 * calls happen inside one tool so a single model round-trip covers them — the free Gemini tier does
 * not have the budget for one call per metric.
 */
@Component
public class DetailedConditionsTool implements ChatTool {
  private final GeographyService geography;
  private final OpenMeteoClient provider;
  private final ObjectMapper json;
  private final String forecastUrl;
  private final String airQualityUrl;

  public DetailedConditionsTool(
      GeographyService geography,
      OpenMeteoClient provider,
      ObjectMapper json,
      @Value("${weather.open-meteo-url}") String forecastUrl,
      @Value("${weather.air-quality-url}") String airQualityUrl) {
    this.geography = geography;
    this.provider = provider;
    this.json = json;
    this.forecastUrl = forecastUrl;
    this.airQualityUrl = airQualityUrl;
  }

  @Override
  public String name() {
    return "get_detailed_conditions";
  }

  @Override
  public ObjectNode declaration(ObjectMapper mapper) {
    ObjectNode properties = mapper.createObjectNode();
    properties.set("ward_id", Schemas.string(mapper, "Mã phường/xã lấy từ find_ward."));
    return Schemas.declaration(
        mapper,
        name(),
        "Chỉ số chi tiết để khuyên người dùng mặc gì, mang gì: tia UV, chất lượng không khí "
            + "(PM2.5, PM10, AQI châu Âu), nhiệt độ cảm nhận, gió giật và xác suất mưa.",
        Schemas.object(mapper, properties, "ward_id"));
  }

  @Override
  public Result execute(JsonNode arguments) {
    String wardId = Schemas.text(arguments, "ward_id");
    if (wardId.isBlank())
      return Result.of(json.createObjectNode().put("error", "Thiếu ward_id, hãy gọi find_ward."));
    var ward = geography.coordinates(wardId);
    double latitude = ward.getLatitude().doubleValue();
    double longitude = ward.getLongitude().doubleValue();

    ObjectNode payload = json.createObjectNode();
    payload.put("ward_name", ward.getName());

    var comfort = new LinkedHashMap<String, String>();
    comfort.put(
        "current",
        "apparent_temperature,temperature_2m,relative_humidity_2m,wind_speed_10m,wind_gusts_10m,precipitation,uv_index");
    comfort.put("hourly", "precipitation_probability");
    comfort.put("forecast_hours", "6");
    payload.set("comfort", block(forecastUrl, latitude, longitude, comfort, "current"));
    payload.set(
        "rain_probability_next_hours",
        hourlySeries(forecastUrl, latitude, longitude, comfort));

    var air = new LinkedHashMap<String, String>();
    air.put("current", "uv_index,pm2_5,pm10,european_aqi");
    payload.set("air_quality", block(airQualityUrl, latitude, longitude, air, "current"));

    payload.put(
        "units", "°C, %, km/h, mm/h, UV index, µg/m³, EAQI. Nguồn Open-Meteo, không phải mô hình nhóm tự train.");
    return Result.of(payload);
  }

  /** Upstream hiccups must not abort the turn: the model is told the block is missing instead. */
  private JsonNode block(
      String endpoint, double latitude, double longitude, LinkedHashMap<String, String> options, String key) {
    try {
      return provider.fetch(endpoint, latitude, longitude, options).path(key);
    } catch (RuntimeException e) {
      return json.createObjectNode().put("error", "Không lấy được dữ liệu từ nguồn này.");
    }
  }

  private JsonNode hourlySeries(
      String endpoint, double latitude, double longitude, LinkedHashMap<String, String> options) {
    try {
      var hourly = provider.fetch(endpoint, latitude, longitude, options).path("hourly");
      var values = hourly.path("precipitation_probability");
      var series = json.createArrayNode();
      for (int i = 0; i < Math.min(values.size(), 6); i++) series.add(values.get(i).asInt());
      return series;
    } catch (RuntimeException e) {
      return json.createArrayNode();
    }
  }
}
