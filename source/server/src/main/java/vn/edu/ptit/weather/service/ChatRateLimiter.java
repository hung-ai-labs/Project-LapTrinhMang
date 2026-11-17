package vn.edu.ptit.weather.service;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import vn.edu.ptit.weather.exception.ApiException;

/**
 * Per-user fixed window over the shared Gemini quota. In-memory on purpose: one JVM serves the
 * whole app, and a dropped counter after restart is harmless.
 */
@Component
public class ChatRateLimiter {
  private record Window(Instant startedAt, int used) {}

  private final Map<String, Window> windows = new ConcurrentHashMap<>();
  private final int limitPerMinute;

  public ChatRateLimiter(@Value("${weather.chat-rate-limit-per-minute}") int limitPerMinute) {
    this.limitPerMinute = limitPerMinute;
  }

  public void check(String userId) {
    if (limitPerMinute <= 0) return;
    Instant now = Instant.now();
    Window updated =
        windows.compute(
            userId,
            (key, current) ->
                current == null
                        || Duration.between(current.startedAt(), now).compareTo(Duration.ofMinutes(1))
                            >= 0
                    ? new Window(now, 1)
                    : new Window(current.startedAt(), current.used() + 1));
    if (updated.used() > limitPerMinute)
      throw new ApiException(
          429, "Bạn đã gửi quá " + limitPerMinute + " câu hỏi trong một phút, thử lại sau.");
  }
}
