package vn.edu.ptit.weather.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.*;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.*;
import vn.edu.ptit.weather.dto.ApiResponse;
import vn.edu.ptit.weather.security.JwtFilter;

@org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication(
    type =
        org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication.Type.SERVLET)
@Configuration
public class SecurityConfig {
  @Bean
  FilterRegistrationBean<JwtFilter> disableServletRegistration(JwtFilter filter) {
    var bean = new FilterRegistrationBean<>(filter);
    bean.setEnabled(false);
    return bean;
  }

  @Bean
  SecurityFilterChain security(
      HttpSecurity http, JwtFilter filter, ObjectMapper json, CorsConfigurationSource cors)
      throws Exception {
    return http.csrf(c -> c.disable())
        .cors(c -> c.configurationSource(cors))
        .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
        .authorizeHttpRequests(
            a ->
                a.requestMatchers("/api/v1/auth/me", "/api/v1/auth/logout", "/api/v1/users/**")
                    .authenticated()
                    .anyRequest()
                    .permitAll())
        .exceptionHandling(
            e ->
                e.authenticationEntryPoint(
                    (req, res, ex) -> {
                      res.setStatus(401);
                      res.setContentType("application/json;charset=UTF-8");
                      json.writeValue(
                          res.getOutputStream(),
                          ApiResponse.fail("http_401", "Cần đăng nhập.", null));
                    }))
        .addFilterBefore(filter, UsernamePasswordAuthenticationFilter.class)
        .build();
  }

  @Bean
  CorsConfigurationSource cors(@Value("${weather.cors-origins}") String origins) {
    var config = new CorsConfiguration();
    config.setAllowedOrigins(
        List.of(
            origins
                .replace("[", "")
                .replace("]", "")
                .replace("\"", "")
                .replace(" ", "")
                .split(",")));
    config.setAllowedMethods(List.of("GET", "POST", "PATCH", "DELETE", "OPTIONS"));
    config.setAllowedHeaders(List.of("*"));
    config.setExposedHeaders(List.of("X-Data-Stale"));
    var source = new UrlBasedCorsConfigurationSource();
    source.registerCorsConfiguration("/**", config);
    return source;
  }
}
