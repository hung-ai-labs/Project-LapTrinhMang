package vn.edu.ptit.weather.security;

import io.jsonwebtoken.*;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import javax.crypto.SecretKey;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import vn.edu.ptit.weather.entity.User;
import vn.edu.ptit.weather.exception.ApiException;

@Service
public class JwtService {
  private final String secret;
  private final int minutes;

  public JwtService(
      @Value("${weather.jwt-secret}") String secret,
      @Value("${weather.jwt-expire-minutes}") int minutes) {
    this.secret = secret;
    this.minutes = minutes;
  }

  private SecretKey key() {
    if (secret.getBytes(StandardCharsets.UTF_8).length < 32)
      throw new ApiException(503, "Chưa cấu hình JWT_SECRET đủ mạnh.");
    return Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
  }

  public void requireConfigured() {
    key();
  }

  public long lifetime() {
    return minutes * 60L;
  }

  public String issue(User user) {
    Instant now = Instant.now();
    return Jwts.builder()
        .subject(user.getId())
        .issuer("weather-stream")
        .audience()
        .add("weather-web")
        .and()
        .issuedAt(Date.from(now))
        .expiration(Date.from(now.plusSeconds(lifetime())))
        .id(UUID.randomUUID().toString())
        .claim("ver", user.getTokenVersion())
        .signWith(key(), Jwts.SIG.HS256)
        .compact();
  }

  public Claims parse(String token) {
    var signed =
        Jwts.parser()
            .verifyWith(key())
            .requireIssuer("weather-stream")
            .requireAudience("weather-web")
            .build()
            .parseSignedClaims(token);
    if (!"HS256".equals(signed.getHeader().getAlgorithm()))
      throw new JwtException("Unsupported algorithm");
    Claims claims = signed.getPayload();
    if (claims.getSubject() == null
        || claims.getExpiration() == null
        || claims.getIssuedAt() == null
        || claims.getId() == null
        || !(claims.get("ver") instanceof Number)) throw new JwtException("Missing claims");
    if (claims.getIssuedAt().toInstant().isAfter(Instant.now()))
      throw new JwtException("Future issued-at");
    return claims;
  }
}
