package vn.edu.ptit.weather.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import vn.edu.ptit.weather.dto.ApiResponse;
import vn.edu.ptit.weather.dto.GeographyDto.AddressRequest;
import vn.edu.ptit.weather.service.UserService;

@io.swagger.v3.oas.annotations.security.SecurityRequirement(name = "bearerAuth")
@RestController
@RequestMapping("/api/v1/users/me/address")
@RequiredArgsConstructor
public class UserController {
  private final UserService service;

  @GetMapping
  public ApiResponse<?> get() {
    return ApiResponse.ok(service.address());
  }

  @PatchMapping
  public ApiResponse<?> save(@Valid @RequestBody AddressRequest request) {
    return ApiResponse.ok(service.save(request));
  }

  @DeleteMapping
  public ApiResponse<?> delete() {
    return ApiResponse.ok(service.delete());
  }
}
