package vn.edu.ptit.weather.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import vn.edu.ptit.weather.dto.ApiResponse;
import vn.edu.ptit.weather.dto.AuthDto.*;
import vn.edu.ptit.weather.service.AuthService;

@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {
  private final AuthService service;

  @PostMapping("/register")
  public ResponseEntity<?> register(@Valid @RequestBody RegisterRequest request) {
    return ResponseEntity.status(201)
        .cacheControl(CacheControl.noStore())
        .body(ApiResponse.ok(service.register(request)));
  }

  @PostMapping("/login")
  public ResponseEntity<?> login(@Valid @RequestBody LoginRequest request) {
    return ResponseEntity.ok()
        .cacheControl(CacheControl.noStore())
        .body(ApiResponse.ok(service.login(request)));
  }

  @io.swagger.v3.oas.annotations.security.SecurityRequirement(name = "bearerAuth")
  @GetMapping("/me")
  public ApiResponse<?> me() {
    return ApiResponse.ok(UserResponse.from(service.currentUser()));
  }

  @io.swagger.v3.oas.annotations.security.SecurityRequirement(name = "bearerAuth")
  @PostMapping("/logout")
  public ApiResponse<?> logout() {
    service.logout();
    return ApiResponse.ok(null);
  }
}
