package vn.edu.ptit.weather.tool;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import vn.edu.ptit.weather.service.ChatTool;
import vn.edu.ptit.weather.service.ForecastService;

/** Open-Meteo forecast: the next hour for "lát nữa", or seven days for "tuần này". */
@Component
@RequiredArgsConstructor
public class ForecastTool implements ChatTool {
  private final ForecastService forecasts;
  private final ObjectMapper json;

  @Override
  public String name() {
    return "get_forecast";
  }

  @Override
  public ObjectNode declaration(ObjectMapper mapper) {
    ObjectNode properties = mapper.createObjectNode();
    properties.set("ward_id", Schemas.string(mapper, "Mã phường/xã lấy từ find_ward."));
    properties.set(
        "range",
        Schemas.string(
            mapper, "'next_hour' cho giờ kế tiếp, 'week' cho 7 ngày tới. Mặc định 'week'."));
    return Schemas.declaration(
        mapper,
        name(),
        "Dự báo thời tiết sắp tới của một phường/xã theo Open-Meteo.",
        Schemas.object(mapper, properties, "ward_id"));
  }

  @Override
  public Result execute(JsonNode arguments) {
    String wardId = Schemas.text(arguments, "ward_id");
    if (wardId.isBlank())
      return Result.of(json.createObjectNode().put("error", "Thiếu ward_id, hãy gọi find_ward."));
    String range = Schemas.text(arguments, "range");
    Object data = "next_hour".equals(range) ? forecasts.preview(wardId) : forecasts.future(wardId);
    return Result.of(json.valueToTree(data));
  }
}
