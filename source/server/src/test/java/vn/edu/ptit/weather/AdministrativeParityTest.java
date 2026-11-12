package vn.edu.ptit.weather;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;
import vn.edu.ptit.weather.service.AdministrativeCatalogService;

class AdministrativeParityTest {
  ObjectMapper json = new ObjectMapper();

  @Test
  void validatesPinnedSnapshotAndPreservesDecimalStringCoordinates() throws Exception {
    byte[] bytes;
    JsonNode manifest;
    try (var input = new ClassPathResource("snapshot.json").getInputStream()) {
      bytes =
          new String(input.readAllBytes(), StandardCharsets.UTF_8)
              .replace("\r\n", "\n")
              .getBytes(StandardCharsets.UTF_8);
    }
    try (var input = new ClassPathResource("manifest.json").getInputStream()) {
      manifest = json.readTree(input);
    }
    var data = json.readTree(bytes);
    AdministrativeCatalogService.validate(data, manifest, bytes);
    var first = data.path("wards").get(0);
    assertThat(AdministrativeCatalogService.coordinate(first.get("latitude"), -90, 90))
        .isBetween(new java.math.BigDecimal("8"), new java.math.BigDecimal("24"));
    assertThat(AdministrativeCatalogService.coordinate(first.get("longitude"), -180, 180))
        .isBetween(new java.math.BigDecimal("102"), new java.math.BigDecimal("110"));
  }

  @Test
  void rejectsTamperingDuplicateIdsMissingParentAndInvalidCoordinates() throws Exception {
    var data =
        json.readTree(
            "{\"dataset_version\":\"test\",\"provinces\":[{\"id\":\"01\",\"name\":\"Hà Nội\"}],\"wards\":[{\"id\":\"00004\",\"name\":\"Ba Đình\",\"province_id\":\"01\",\"latitude\":\"21.03000\",\"longitude\":\"105.85000\"}]}");
    var manifest = json.createObjectNode();
    manifest.put("dataset_version", "test");
    manifest.putObject("counts").put("provinces", 1).put("wards", 1);
    byte[] bytes = json.writeValueAsBytes(data);
    manifest.put(
        "snapshot_sha256",
        HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)));
    AdministrativeCatalogService.validate(data, manifest, bytes);
    assertThatThrownBy(() -> AdministrativeCatalogService.validate(data, manifest, new byte[] {1}))
        .isInstanceOf(IllegalArgumentException.class);
    ((com.fasterxml.jackson.databind.node.ObjectNode) data.path("wards").get(0))
        .put("province_id", "missing");
    assertThatThrownBy(() -> AdministrativeCatalogService.validate(data, manifest, bytes))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(
            () -> AdministrativeCatalogService.coordinate(json.readTree("\"NaN\""), -90, 90))
        .isInstanceOf(IllegalArgumentException.class);
  }
}
