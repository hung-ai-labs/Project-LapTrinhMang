package vn.edu.ptit.weather.dto;

import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import vn.edu.ptit.weather.entity.*;

public final class GeographyDto {
  private GeographyDto() {}

  public record ProvinceResponse(String id, String name) {
    public static ProvinceResponse from(Province p) {
      return new ProvinceResponse(p.getId(), p.getName());
    }
  }

  public record WardResponse(
      String id,
      String name,
      String provinceId,
      String administrativeType,
      BigDecimal latitude,
      BigDecimal longitude) {
    public static WardResponse from(Ward w) {
      return new WardResponse(
          w.getId(),
          w.getName(),
          w.getProvinceId(),
          w.getAdministrativeType(),
          w.getLatitude(),
          w.getLongitude());
    }
  }

  public record AddressRequest(
      @NotBlank @Size(max = 20) String wardId, @Size(max = 500) String addressText) {
    public AddressRequest {
      if (wardId != null) wardId = wardId.strip();
      if (addressText != null) addressText = addressText.strip();
    }
  }

  public record AddressResponse(String addressText, WardResponse ward, ProvinceResponse province) {}

  public record NearestRequest(
      @NotNull @DecimalMin("-90") @DecimalMax("90") Double latitude,
      @NotNull @DecimalMin("-180") @DecimalMax("180") Double longitude) {}

  public record NearestResponse(
      WardResponse ward, ProvinceResponse province, double distanceKm, String matchType) {}
}
