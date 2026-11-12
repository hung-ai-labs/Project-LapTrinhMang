package vn.edu.ptit.weather.dto;

import jakarta.validation.constraints.*;
import vn.edu.ptit.weather.entity.User;

public final class AuthDto {
  private AuthDto() {}

  public record LoginRequest(
      @NotBlank @Email @Size(max = 254) String email,
      @NotNull @Size(min = 8, max = 128) String password) {
    public LoginRequest {
      if (email != null) email = email.strip();
    }
  }

  public record RegisterRequest(
      @NotBlank @Size(max = 100) String name,
      @NotBlank @Email @Size(max = 254) String email,
      @NotNull @Size(min = 8, max = 128) String password) {
    public RegisterRequest {
      if (email != null) email = email.strip();
    }
  }

  public record UserResponse(String id, String name, String email) {
    public static UserResponse from(User user) {
      return new UserResponse(user.getId(), user.getName(), user.getEmail());
    }
  }

  public record TokenResponse(
      String accessToken, String tokenType, long expiresIn, UserResponse user) {}
}
