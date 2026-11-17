package vn.edu.ptit.weather.tool;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.text.Normalizer;
import java.util.*;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import vn.edu.ptit.weather.entity.Ward;
import vn.edu.ptit.weather.service.ChatTool;
import vn.edu.ptit.weather.service.GeographyService;

/**
 * Resolves a place name to a ward id. Every weather tool needs that id, so this is normally the
 * model's first call. Matching ignores diacritics: users type "ha noi" far more often than "Hà Nội".
 */
@Component
@RequiredArgsConstructor
public class FindWardTool implements ChatTool {
  private static final int MAX_RESULTS = 5;

  private final GeographyService geography;
  private final ObjectMapper json;

  @Override
  public String name() {
    return "find_ward";
  }

  @Override
  public ObjectNode declaration(ObjectMapper json) {
    ObjectNode properties = json.createObjectNode();
    properties.set(
        "query",
        Schemas.string(json, "Tên phường/xã hoặc tỉnh/thành người dùng nhắc tới, ví dụ 'Hà Nội'."));
    return Schemas.declaration(
        json,
        name(),
        "Tìm mã phường/xã (ward_id) theo tên địa danh. Luôn gọi tool này trước khi hỏi thời tiết.",
        Schemas.object(json, properties, "query"));
  }

  @Override
  public Result execute(JsonNode arguments) {
    String query = Schemas.text(arguments, "query");
    if (query.isBlank())
      return Result.of(json.createObjectNode().put("error", "Thiếu tên địa danh cần tìm."));

    String needle = fold(query);
    var provinces = new HashMap<String, String>();
    for (var province : geography.provinces().rows())
      provinces.put(province.getId(), province.getName());

    var exact = new ArrayList<Ward>();
    var partial = new ArrayList<Ward>();
    for (Ward ward : geography.wards(null).rows()) {
      String wardName = fold(ward.getName());
      String provinceName = fold(provinces.getOrDefault(ward.getProvinceId(), ""));
      if (wardName.equals(needle)) exact.add(ward);
      else if (wardName.contains(needle) || provinceName.equals(needle)) partial.add(ward);
      if (exact.size() >= MAX_RESULTS) break;
    }

    var matches = exact.isEmpty() ? partial : exact;
    var results = json.createArrayNode();
    for (Ward ward : matches.stream().limit(MAX_RESULTS).toList()) {
      ObjectNode row = json.createObjectNode();
      row.put("ward_id", ward.getId());
      row.put("ward_name", ward.getName());
      row.put("province_name", provinces.getOrDefault(ward.getProvinceId(), ""));
      results.add(row);
    }
    ObjectNode payload = json.createObjectNode();
    payload.put("count", results.size());
    payload.set("wards", results);
    if (results.isEmpty()) payload.put("hint", "Không tìm thấy địa danh khớp, hãy hỏi lại người dùng.");
    return Result.of(payload);
  }

  /** Lowercase, strip Vietnamese diacritics and đ/Đ so loose user spelling still matches. */
  private static String fold(String value) {
    String normalized =
        Normalizer.normalize(value, Normalizer.Form.NFD).replaceAll("\\p{M}+", "");
    return normalized.replace('đ', 'd').replace('Đ', 'D').toLowerCase(Locale.ROOT).strip();
  }
}
