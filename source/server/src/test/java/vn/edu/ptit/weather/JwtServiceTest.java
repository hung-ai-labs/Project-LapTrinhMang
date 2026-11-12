package vn.edu.ptit.weather;

import static org.assertj.core.api.Assertions.*;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;
import org.junit.jupiter.api.Test;
import vn.edu.ptit.weather.entity.User;
import vn.edu.ptit.weather.security.JwtService;

class JwtServiceTest {
  private static final String SECRET = "integration-test-secret-at-least-32-characters";
  private final JwtService service = new JwtService(SECRET, 30);

  @Test
  void roundTrip() {
    var user = new User();
    user.setId("test-id");
    assertThat(service.parse(service.issue(user)).getSubject()).isEqualTo("test-id");
  }

  @Test
  void rejectsTamperingExpiredAndIncompleteTokens() {
    var user = new User();
    user.setId("test-id");
    String[] parts = service.issue(user).split("\\.");
    String signature = (parts[2].startsWith("A") ? "B" : "A") + parts[2].substring(1);
    assertThatThrownBy(() -> service.parse(parts[0] + "." + parts[1] + "." + signature))
        .isInstanceOf(io.jsonwebtoken.JwtException.class);
    var key = Keys.hmacShaKeyFor(SECRET.getBytes(StandardCharsets.UTF_8));
    String expired =
        Jwts.builder()
            .subject("test-id")
            .issuer("weather-stream")
            .audience()
            .add("weather-web")
            .and()
            .issuedAt(Date.from(Instant.now().minusSeconds(120)))
            .expiration(Date.from(Instant.now().minusSeconds(60)))
            .id("test-token")
            .claim("ver", 0)
            .signWith(key, Jwts.SIG.HS256)
            .compact();
    assertThatThrownBy(() -> service.parse(expired))
        .isInstanceOf(io.jsonwebtoken.ExpiredJwtException.class);
    String incomplete =
        Jwts.builder()
            .subject("test-id")
            .issuer("weather-stream")
            .audience()
            .add("weather-web")
            .and()
            .signWith(key, Jwts.SIG.HS256)
            .compact();
    assertThatThrownBy(() -> service.parse(incomplete))
        .isInstanceOf(io.jsonwebtoken.JwtException.class);
  }
}
