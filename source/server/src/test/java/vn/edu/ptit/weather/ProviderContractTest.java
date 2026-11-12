package vn.edu.ptit.weather;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.*;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.*;
import vn.edu.ptit.weather.entity.Ward;
import vn.edu.ptit.weather.exception.ApiException;
import vn.edu.ptit.weather.service.*;

class ProviderContractTest {
  ObjectMapper json =
      new ObjectMapper()
          .findAndRegisterModules()
          .disable(com.fasterxml.jackson.databind.SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

  @Test
  void normalizesQuarterHourRainfallAndKeepsPythonUuid() throws Exception {
    var payload =
        json.readTree(
            """
            {"current_units":{"temperature_2m":"°C","relative_humidity_2m":"%","wind_speed_10m":"km/h","precipitation":"mm"},"current":{"time":1793751300,"interval":900,"temperature_2m":25,"relative_humidity_2m":90,"wind_speed_10m":5,"precipitation":0.5}}
            """);
    // Set an explicit fixture timestamp to avoid relying on hand-converted epoch values.
    ((com.fasterxml.jackson.databind.node.ObjectNode) payload.path("current"))
        .put("time", Instant.parse("2026-11-04T00:15:00Z").getEpochSecond());
    var observation = CurrentWeatherService.normalize("00004", payload);
    assertThat(observation.rainfall()).isEqualTo(2.0);
    assertThat(observation.eventId().toString()).isEqualTo("d52abef9-d4e6-5515-8776-99d9b2c98875");
    ((com.fasterxml.jackson.databind.node.ObjectNode) payload.path("current_units"))
        .put("wind_speed_10m", "m/s");
    assertThatThrownBy(() -> CurrentWeatherService.normalize("00004", payload))
        .isInstanceOf(ApiException.class);
  }

  @Test
  void preservesArgon2HashesProducedByPython() {
    var passwords =
        org.springframework.security.crypto.argon2.Argon2PasswordEncoder
            .defaultsForSpringSecurity_v5_8();
    assertThat(
            passwords.matches(
                "Migration-test-password-123",
                "$argon2id$v=19$m=65536,t=3,p=4$60RleLN/fAjDV52laAJd1g$goMvHOGL9eJgxdj8xWkT4q1Lfdfu73ZflbBwFapqlDk"))
        .isTrue();
    assertThat(
            passwords.matches(
                "wrong-password",
                "$argon2id$v=19$m=65536,t=3,p=4$60RleLN/fAjDV52laAJd1g$goMvHOGL9eJgxdj8xWkT4q1Lfdfu73ZflbBwFapqlDk"))
        .isFalse();
  }

  @Test
  void sevenDayForecastFiltersPastHoursCachesAndNeverClaimsAi() {
    var geo = mock(GeographyService.class);
    var provider = mock(OpenMeteoClient.class);
    Ward ward = new Ward();
    ward.setId("00004");
    ward.setName("Ba Đình");
    ward.setProvinceId("01");
    ward.setLatitude(new java.math.BigDecimal("21"));
    ward.setLongitude(new java.math.BigDecimal("105"));
    when(geo.coordinates("00004")).thenReturn(ward);
    var payload = json.createObjectNode();
    var hourly = payload.putObject("hourly");
    var units = payload.putObject("hourly_units");
    Map<String, String> expected =
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
    expected.forEach(units::put);
    units.put("time", "unixtime");
    var times = hourly.putArray("time");
    expected.keySet().forEach(hourly::putArray);
    Instant start =
        Instant.now().truncatedTo(java.time.temporal.ChronoUnit.HOURS).minusSeconds(3600);
    for (int i = 0; i < 192; i++) {
      times.add(start.plusSeconds(3600L * i).getEpochSecond());
      for (String field : expected.keySet())
        ((com.fasterxml.jackson.databind.node.ArrayNode) hourly.get(field))
            .add(field.equals("temperature_2m") ? 25 : 0);
    }
    when(provider.fetch(anyDouble(), anyDouble(), anyMap())).thenReturn(payload);
    var service = new ForecastService(geo, provider);
    var result = json.valueToTree(service.future("00004"));
    assertThat(result.path("hours").asInt()).isEqualTo(168);
    assertThat(result.path("is_project_ai").asBoolean()).isFalse();
    assertThat(result.path("source").asText()).isEqualTo("open-meteo");
    assertThat(Instant.parse(result.path("hourly").get(0).path("time").asText()))
        .isAfter(Instant.now());
    service.future("00004");
    verify(provider, org.mockito.Mockito.times(1)).fetch(anyDouble(), anyDouble(), anyMap());
    var preview = json.valueToTree(service.preview("00004"));
    assertThat(preview.path("predicted_temperature").asDouble()).isEqualTo(25);
    assertThat(preview.path("method").asText()).isEqualTo("open_meteo_hourly");
    verify(provider, org.mockito.Mockito.times(2)).fetch(anyDouble(), anyDouble(), anyMap());
  }

  @Test
  void rejectsTruncatedForecastArrays() throws Exception {
    var payload = json.readTree("{\"hourly\":{\"time\":[1,2],\"temperature_2m\":[20]}}");
    assertThatThrownBy(() -> OpenMeteoClient.series(payload, "hourly", List.of("temperature_2m")))
        .isInstanceOf(ApiException.class);
  }
}
