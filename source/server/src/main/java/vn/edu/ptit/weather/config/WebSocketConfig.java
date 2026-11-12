package vn.edu.ptit.weather.config;

import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.*;
import vn.edu.ptit.weather.network.WeatherSocketHandler;

@org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication(
    type =
        org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication.Type.SERVLET)
@Configuration
@EnableWebSocket
@RequiredArgsConstructor
public class WebSocketConfig implements WebSocketConfigurer {
  private final WeatherSocketHandler handler;

  @Value("${weather.cors-origins}")
  private String origins;

  @Override
  public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
    registry
        .addHandler(handler, "/api/v1/ws/wards/{wardId}/weather")
        .setAllowedOrigins(
            origins
                .replace("[", "")
                .replace("]", "")
                .replace("\"", "")
                .replace(" ", "")
                .split(","));
  }
}
