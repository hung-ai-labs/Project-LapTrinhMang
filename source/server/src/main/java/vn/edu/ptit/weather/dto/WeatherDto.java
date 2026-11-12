package vn.edu.ptit.weather.dto;

import jakarta.validation.constraints.*;
import java.time.Instant;
import java.util.*;
import vn.edu.ptit.weather.entity.Observation;

public final class WeatherDto {
  private WeatherDto() {}

  public record ObservationRequest(
      @NotNull UUID eventId,
      @NotBlank @Size(max = 20) String wardId,
      @NotNull @DecimalMin("-60") @DecimalMax("65") Double temperature,
      @NotNull @DecimalMin("0") @DecimalMax("100") Double humidity,
      @NotNull @DecimalMin("0") @DecimalMax("500") Double windSpeed,
      @NotNull @DecimalMin("0") @DecimalMax("1000") Double rainfall,
      @NotNull @Pattern(regexp = "simulator|provider") String source,
      @NotNull
          @com.fasterxml.jackson.annotation.JsonFormat(
              shape = com.fasterxml.jackson.annotation.JsonFormat.Shape.STRING)
          Instant observedAt) {
    public ObservationRequest {
      if (source == null) source = "simulator";
      if (observedAt != null)
        observedAt = observedAt.truncatedTo(java.time.temporal.ChronoUnit.MICROS);
    }
  }

  public record ObservationResponse(
      String id,
      String wardId,
      double temperature,
      double humidity,
      double windSpeed,
      double rainfall,
      String source,
      Instant observedAt) {
    public static ObservationResponse from(Observation o) {
      return new ObservationResponse(
          o.getId(),
          o.getWardId(),
          o.getTemperature(),
          o.getHumidity(),
          o.getWindSpeed(),
          o.getRainfall(),
          o.getSource(),
          o.getObservedAt());
    }
  }

  public record Alert(String code, String severity, String message) {}

  public record WeatherEvent(String type, ObservationResponse observation, List<Alert> alerts) {}
}
