package vn.edu.ptit.weather.dto;

public record ApiResponse<T>(
    boolean success,
    T data,
    @com.fasterxml.jackson.annotation.JsonInclude(
            com.fasterxml.jackson.annotation.JsonInclude.Include.NON_NULL)
        ApiError error) {
  public record ApiError(String code, String message, Object details) {}

  public static <T> ApiResponse<T> ok(T data) {
    return new ApiResponse<>(true, data, null);
  }

  public static ApiResponse<Void> fail(String code, String message, Object details) {
    return new ApiResponse<>(false, null, new ApiError(code, message, details));
  }
}
