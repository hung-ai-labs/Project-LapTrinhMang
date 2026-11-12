package vn.edu.ptit.weather.service;

import java.util.*;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import vn.edu.ptit.weather.dto.AuthDto.*;
import vn.edu.ptit.weather.entity.User;
import vn.edu.ptit.weather.exception.ApiException;
import vn.edu.ptit.weather.repository.UserRepository;
import vn.edu.ptit.weather.security.JwtService;

@Service
@RequiredArgsConstructor
public class AuthService {
  private final UserRepository users;
  private final PasswordEncoder passwords;
  private final JwtService jwt;
  private String dummyHash;

  @jakarta.annotation.PostConstruct
  void initializeDummyHash() {
    dummyHash = passwords.encode("unused-timing-comparison-password");
  }

  private String normalize(String email) {
    return email.trim().toLowerCase(Locale.ROOT);
  }

  @Transactional
  public TokenResponse register(RegisterRequest request) {
    if (users.findByEmail(normalize(request.email())).isPresent())
      throw new ApiException(409, "Email đã được sử dụng.");
    User user = new User();
    user.setId(UUID.randomUUID().toString());
    user.setName(request.name().trim());
    user.setEmail(normalize(request.email()));
    user.setPasswordHash(passwords.encode(request.password()));
    // Issue before writing: missing signing configuration must never create a partial account.
    TokenResponse token = token(user);
    try {
      users.saveAndFlush(user);
    } catch (org.springframework.dao.DataIntegrityViolationException e) {
      throw new ApiException(409, "Email đã được sử dụng.");
    }
    return token;
  }

  public TokenResponse login(LoginRequest request) {
    jwt.requireConfigured();
    User user = users.findByEmail(normalize(request.email())).orElse(null);
    boolean matches =
        passwords.matches(request.password(), user == null ? dummyHash : user.getPasswordHash());
    if (user == null || !matches) throw new ApiException(401, "Email hoặc mật khẩu không đúng.");
    return token(user);
  }

  public User currentUser() {
    var auth = SecurityContextHolder.getContext().getAuthentication();
    if (auth == null || !(auth.getPrincipal() instanceof User user))
      throw new ApiException(401, "Cần đăng nhập.");
    return user;
  }

  @Transactional
  public void logout() {
    users.revokeTokens(currentUser().getId());
  }

  private TokenResponse token(User user) {
    return new TokenResponse(jwt.issue(user), "bearer", jwt.lifetime(), UserResponse.from(user));
  }
}
