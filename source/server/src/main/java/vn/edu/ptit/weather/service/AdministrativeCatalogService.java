package vn.edu.ptit.weather.service;

import com.fasterxml.jackson.databind.*;
import java.util.*;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Explicit catalog replacement: upsert current rows and deactivate obsolete codes, never delete.
 */
@Service
@RequiredArgsConstructor
public class AdministrativeCatalogService {
  private final JdbcTemplate db;

  public static java.math.BigDecimal coordinate(JsonNode node, double min, double max) {
    if (node == null || node.isNull()) return null;
    final java.math.BigDecimal value;
    try {
      if (!node.isNumber() && !node.isTextual()) throw new NumberFormatException();
      value = new java.math.BigDecimal(node.asText());
    } catch (NumberFormatException e) {
      throw new IllegalArgumentException("Invalid administrative coordinate");
    }
    if (value.compareTo(java.math.BigDecimal.valueOf(min)) < 0
        || value.compareTo(java.math.BigDecimal.valueOf(max)) > 0)
      throw new IllegalArgumentException("Administrative coordinate out of range");
    return value;
  }

  public static void validate(JsonNode data, JsonNode manifest, byte[] bytes) {
    try {
      String hash =
          HexFormat.of()
              .formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));
      if (!hash.equals(manifest.path("snapshot_sha256").asText())
          || !data.path("dataset_version")
              .asText()
              .equals(manifest.path("dataset_version").asText()))
        throw new IllegalArgumentException("Snapshot checksum/version mismatch");
    } catch (java.security.NoSuchAlgorithmException e) {
      throw new IllegalStateException(e);
    }
    Set<String> provinces = new HashSet<>(), wards = new HashSet<>();
    for (String block : List.of("provinces", "wards")) {
      JsonNode rows = data.path(block);
      if (!rows.isArray()
          || rows.isEmpty()
          || rows.size() != manifest.path("counts").path(block).asInt())
        throw new IllegalArgumentException("Snapshot count mismatch");
      for (var row : rows) {
        String id = row.path("id").asText(), name = row.path("name").asText();
        if (id.isBlank()
            || id.length() > 20
            || name.isBlank()
            || name.length() > 150
            || !(block.equals("provinces") ? provinces : wards).add(id))
          throw new IllegalArgumentException("Invalid/duplicate administrative row");
        if (block.equals("wards")) {
          if (!provinces.contains(row.path("province_id").asText()))
            throw new IllegalArgumentException("Unknown parent province");
          var lat = row.get("latitude");
          var lon = row.get("longitude");
          boolean hasLat = lat != null && !lat.isNull(), hasLon = lon != null && !lon.isNull();
          if (hasLat != hasLon) throw new IllegalArgumentException("Coordinate pair is incomplete");
          if (hasLat) {
            coordinate(lat, -90, 90);
            coordinate(lon, -180, 180);
          }
        }
      }
    }
  }

  @Transactional
  public void apply(JsonNode data) {
    String version = data.path("dataset_version").asText();
    var provinces = new ArrayList<Object[]>();
    var wards = new ArrayList<Object[]>();
    for (var row : data.path("provinces"))
      provinces.add(new Object[] {row.path("id").asText(), row.path("name").asText(), version});
    for (var row : data.path("wards"))
      wards.add(
          new Object[] {
            row.path("id").asText(),
            row.path("province_id").asText(),
            row.path("name").asText(),
            row.path("administrative_type").asText(null),
            coordinate(row.get("latitude"), -90, 90),
            coordinate(row.get("longitude"), -180, 180),
            version
          });
    db.batchUpdate(
        "INSERT INTO provinces(id,name,dataset_version,is_active) VALUES (?,?,?,true) ON CONFLICT(id) DO UPDATE SET name=excluded.name,dataset_version=excluded.dataset_version,is_active=true,updated_at=now()",
        provinces);
    db.batchUpdate(
        "INSERT INTO wards(id,province_id,name,administrative_type,latitude,longitude,dataset_version,is_active) VALUES (?,?,?,?,?,?,?,true) ON CONFLICT(id) DO UPDATE SET province_id=excluded.province_id,name=excluded.name,administrative_type=excluded.administrative_type,latitude=excluded.latitude,longitude=excluded.longitude,dataset_version=excluded.dataset_version,is_active=true,updated_at=now()",
        wards);
    for (String table : List.of("wards", "provinces")) {
      var ids = new ArrayList<String>();
      for (var row : data.path(table)) ids.add(row.path("id").asText());
      db.update(
          "UPDATE "
              + table
              + " SET is_active=false,updated_at=now() WHERE id NOT IN ("
              + String.join(",", Collections.nCopies(ids.size(), "?"))
              + ")",
          ids.toArray());
    }
  }
}
