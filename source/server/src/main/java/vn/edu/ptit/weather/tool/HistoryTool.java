package vn.edu.ptit.weather.tool;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import vn.edu.ptit.weather.service.ChatTool;
import vn.edu.ptit.weather.service.ObservationService;

/** Past observations already stored in PostgreSQL, newest first. */
@Component
public class HistoryTool implements ChatTool {
  private static final int MAX_PAGE_SIZE = 50;

  private final ObservationService observations;
  private final ObjectMapper json;
  private final String source;

  public HistoryTool(
      ObservationService observations, ObjectMapper json, @Value("${weather.source}") String source) {
    this.observations = observations;
    this.json = json;
    this.source = source;
  }

  @Override
  public String name() {
    return "get_history";
  }

  @Override
  public ObjectNode declaration(ObjectMapper mapper) {
    ObjectNode properties = mapper.createObjectNode();
    properties.set("ward_id", Schemas.string(mapper, "Mã phường/xã lấy từ find_ward."));
    properties.set(
        "limit", Schemas.integer(mapper, "Số bản ghi gần nhất, 1–50. Mặc định 10."));
    return Schemas.declaration(
        mapper,
        name(),
        "Lịch sử quan sát thời tiết đã lưu của một phường/xã, mới nhất trước.",
        Schemas.object(mapper, properties, "ward_id"));
  }

  @Override
  public Result execute(JsonNode arguments) {
    String wardId = Schemas.text(arguments, "ward_id");
    if (wardId.isBlank())
      return Result.of(json.createObjectNode().put("error", "Thiếu ward_id, hãy gọi find_ward."));
    int limit = Math.max(1, Math.min(Schemas.number(arguments, "limit", 10), MAX_PAGE_SIZE));
    return Result.of(json.valueToTree(observations.history(wardId, source, 1, limit)));
  }
}
