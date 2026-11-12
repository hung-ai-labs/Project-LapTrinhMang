package vn.edu.ptit.weather.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import vn.edu.ptit.weather.dto.ApiResponse;
import vn.edu.ptit.weather.exception.ApiException;
import vn.edu.ptit.weather.repository.UserRepository;

@Component
@RequiredArgsConstructor
public class JwtFilter extends OncePerRequestFilter {
  private final JwtService jwtService;
  private final UserRepository users;
  private final ObjectMapper json;

  @Override
  protected void doFilterInternal(
      HttpServletRequest request, HttpServletResponse response, FilterChain chain)
      throws ServletException, IOException {
    String path = request.getServletPath();
    boolean protectedRoute =
        path.equals("/api/v1/auth/me")
            || path.equals("/api/v1/auth/logout")
            || path.startsWith("/api/v1/users/");
    if (!protectedRoute || request.getMethod().equals("OPTIONS")) {
      chain.doFilter(request, response);
      return;
    }
    String header = request.getHeader("Authorization");
    try {
      if (header == null || !header.startsWith("Bearer "))
        throw new io.jsonwebtoken.JwtException("Missing bearer");
      var claims = jwtService.parse(header.substring(7));
      var user =
          users
              .findById(claims.getSubject())
              .orElseThrow(() -> new io.jsonwebtoken.JwtException("Unknown user"));
      if (user.getTokenVersion() != ((Number) claims.get("ver")).intValue())
        throw new io.jsonwebtoken.JwtException("Revoked token");
      var authentication = new UsernamePasswordAuthenticationToken(user, null, List.of());
      SecurityContextHolder.getContext().setAuthentication(authentication);
    } catch (io.jsonwebtoken.JwtException | IllegalArgumentException e) {
      reject(response, 401, "Thông tin xác thực không hợp lệ hoặc đã hết hạn.");
      return;
    } catch (ApiException e) {
      reject(response, e.getStatus(), e.getMessage());
      return;
    } catch (org.springframework.dao.DataAccessException
        | org.springframework.transaction.TransactionException e) {
      reject(response, 503, "Không kết nối được cơ sở dữ liệu.");
      return;
    }
    chain.doFilter(request, response);
  }

  private void reject(HttpServletResponse response, int status, String message) throws IOException {
    response.setStatus(status);
    response.setContentType("application/json;charset=UTF-8");
    if (status == 401) response.setHeader("WWW-Authenticate", "Bearer");
    json.writeValue(response.getOutputStream(), ApiResponse.fail("http_" + status, message, null));
  }
}
