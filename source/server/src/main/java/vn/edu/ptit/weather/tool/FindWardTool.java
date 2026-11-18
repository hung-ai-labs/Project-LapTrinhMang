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
        Schemas.string(
            json,
            "Tên phường/xã và/hoặc tỉnh/thành người dùng nhắc tới. Có thể ghi cả hai, phân cách"
                + " bằng dấu phẩy, ví dụ 'Ba Đình, Hà Nội' hoặc chỉ 'Hà Nội'."));
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

    // People write the place the way they say it — "Ba Đình, Hà Nội" — so each comma-separated
    // part is matched on its own and a ward that also matches the province part wins.
    var parts = new ArrayList<String>();
    for (String part : query.split("[,/]")) {
      String folded = fold(part);
      if (!folded.isBlank()) parts.add(folded);
    }
    if (parts.isEmpty())
      return Result.of(json.createObjectNode().put("error", "Thiếu tên địa danh cần tìm."));

    var provinces = new HashMap<String, String>();
    for (var province : geography.provinces().rows())
      provinces.put(province.getId(), province.getName());

    // Ranked buckets, best first: an exact ward name backed by the right province beats a loose
    // substring, which in turn beats "every ward of this province".
    var exactInProvince = new ArrayList<Ward>();
    var exact = new ArrayList<Ward>();
    var partialInProvince = new ArrayList<Ward>();
    var partial = new ArrayList<Ward>();
    var provinceOnly = new ArrayList<Ward>();
    for (Ward ward : geography.wards(null).rows()) {
      String wardName = fold(ward.getName());
      String provinceName = fold(provinces.getOrDefault(ward.getProvinceId(), ""));
      boolean isExact = false;
      boolean isPartial = false;
      boolean inProvince = false;
      for (String part : parts) {
        if (wardName.equals(part)) isExact = true;
        else if (wardName.contains(part)) isPartial = true;
        if (provinceName.equals(part)) inProvince = true;
      }
      if (isExact) (inProvince ? exactInProvince : exact).add(ward);
      else if (isPartial) (inProvince ? partialInProvince : partial).add(ward);
      else if (inProvince) provinceOnly.add(ward);
    }

    var matches =
        List.<List<Ward>>of(exactInProvince, exact, partialInProvince, partial, provinceOnly)
            .stream()
        .filter(bucket -> !bucket.isEmpty())
        .findFirst()
        .orElseGet(List::of);
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
