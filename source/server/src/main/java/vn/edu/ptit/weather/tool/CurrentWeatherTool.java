package vn.edu.ptit.weather.tool;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import vn.edu.ptit.weather.service.ChatTool;
import vn.edu.ptit.weather.service.CurrentWeatherService;

/** Live conditions for one ward. The model must read numbers from here, never invent them. */
@Component
@RequiredArgsConstructor
public class CurrentWeatherTool implements ChatTool {
  private final CurrentWeatherService current;
  private final ObjectMapper json;

  @Override
  public String name() {
    return "get_current_weather";
  }

  @Override
  public ObjectNode declaration(ObjectMapper mapper) {
    ObjectNode properties = mapper.createObjectNode();
    properties.set("ward_id", Schemas.string(mapper, "Mã phường/xã lấy từ find_ward."));
    return Schemas.declaration(
        mapper,
        name(),
        "Thời tiết hiện tại của một phường/xã: nhiệt độ (°C), độ ẩm (%), gió (km/h), mưa (mm/h).",
        Schemas.object(mapper, properties, "ward_id"));
  }

  @Override
  public Result execute(JsonNode arguments) {
    String wardId = Schemas.text(arguments, "ward_id");
    if (wardId.isBlank())
      return Result.of(json.createObjectNode().put("error", "Thiếu ward_id, hãy gọi find_ward."));
    return Result.of(json.valueToTree(current.current(wardId)));
  }
}
