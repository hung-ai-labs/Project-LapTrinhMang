package vn.edu.ptit.weather.tool;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import vn.edu.ptit.weather.service.ChatTool;
import vn.edu.ptit.weather.service.CurrentWeatherService;

/**
 * Threshold warnings for a ward. These come from the project's own rules (35°C, 20 mm/h, 50 km/h),
 * not from a trained model, so the assistant must not present them as predictions.
 */
@Component
@RequiredArgsConstructor
public class AlertsTool implements ChatTool {
  private final CurrentWeatherService current;
  private final ObjectMapper json;

  @Override
  public String name() {
    return "get_alerts";
  }

  @Override
  public ObjectNode declaration(ObjectMapper mapper) {
    ObjectNode properties = mapper.createObjectNode();
    properties.set("ward_id", Schemas.string(mapper, "Mã phường/xã lấy từ find_ward."));
    return Schemas.declaration(
        mapper,
        name(),
        "Cảnh báo theo ngưỡng (nắng nóng, mưa lớn, gió mạnh) cho một phường/xã dựa trên số đo hiện tại.",
        Schemas.object(mapper, properties, "ward_id"));
  }

  @Override
  public Result execute(JsonNode arguments) {
    String wardId = Schemas.text(arguments, "ward_id");
    if (wardId.isBlank())
      return Result.of(json.createObjectNode().put("error", "Thiếu ward_id, hãy gọi find_ward."));
    var event = current.current(wardId);
    ObjectNode payload = json.createObjectNode();
    payload.set("alerts", json.valueToTree(event.alerts()));
    payload.put("rule_based", true);
    payload.put("note", "Ngưỡng cố định của dự án, không phải dự báo từ mô hình học máy.");
    return Result.of(payload);
  }
}
