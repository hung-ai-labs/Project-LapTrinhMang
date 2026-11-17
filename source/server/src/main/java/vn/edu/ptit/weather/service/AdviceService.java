package vn.edu.ptit.weather.service;

import java.time.*;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import vn.edu.ptit.weather.dto.WeatherDto.AdviceResponse;
import vn.edu.ptit.weather.exception.ApiException;

/**
 * Turns live readings into "wear a jacket" style advice. The model reaches the data through the
 * same tools the chatbot uses, so the advisory and the chat can never disagree about the numbers.
 *
 * <p>Answers are cached per ward: everyone looking at the same place shares one Gemini call, which
 * is what keeps the free tier usable.
 */
@Service
@RequiredArgsConstructor
public class AdviceService {
  private static final Duration CACHE_TTL = Duration.ofMinutes(30);

  private static final String SYSTEM_INSTRUCTION =
      """
      Bạn là trợ lý thời tiết của Weather Stream, nói tiếng Việt.

      Nhiệm vụ: dựa trên số đo thật, khuyên người dùng hôm nay nên mặc gì và mang theo gì.

      Bắt buộc:
      - Gọi get_current_weather và get_detailed_conditions cho ward_id được cung cấp.
        Không tự bịa bất kỳ con số nào.
      - Viết 2 đến 4 câu, giọng thân thiện, đi thẳng vào việc cần làm:
        áo ấm, áo mưa, ô, kem chống nắng, khẩu trang, hạn chế ra ngoài...
      - Nêu kèm con số quan trọng nhất làm căn cứ (ví dụ nhiệt độ cảm nhận, chỉ số UV, AQI).
      - Nếu một chỉ số không lấy được thì bỏ qua, đừng nhắc tới nó.
      - Không dùng markdown, không gạch đầu dòng, chỉ văn xuôi liền mạch.
      """;

  private record Cached(AdviceResponse response, Instant expiresAt) {}

  private final ChatService chat;
  private final GeminiClient gemini;
  private final GeographyService geography;
  private final Map<String, Cached> cache = new ConcurrentHashMap<>();
  private final Map<String, Object> locks = new ConcurrentHashMap<>();

  public AdviceResponse advice(String wardId) {
    // Rejects unknown wards before spending a Gemini call.
    var ward = geography.ward(wardId);
    if (!gemini.configured())
      return AdviceResponse.unavailable("Chưa cấu hình GEMINI_API_KEY.");

    Cached cached = cache.get(wardId);
    if (cached != null && cached.expiresAt().isAfter(Instant.now())) return cached.response();

    // One generation per ward at a time; the rest wait and read the fresh cache entry.
    Object lock = locks.computeIfAbsent(wardId, key -> new Object());
    synchronized (lock) {
      Cached current = cache.get(wardId);
      if (current != null && current.expiresAt().isAfter(Instant.now())) return current.response();
      AdviceResponse response = generate(wardId, ward.getName());
      // Failures are cached briefly too, otherwise every reload retries a dead upstream.
      cache.put(
          wardId,
          new Cached(
              response, Instant.now().plus(response.available() ? CACHE_TTL : Duration.ofMinutes(2))));
      return response;
    }
  }

  private AdviceResponse generate(String wardId, String wardName) {
    String prompt =
        "Hãy khuyên người dùng đang ở "
            + wardName
            + " (ward_id = "
            + wardId
            + ") nên mặc gì và mang theo gì lúc này.";
    try {
      var completion =
          chat.complete(chat.singleTurn(prompt), SYSTEM_INSTRUCTION, ChatService.SILENT);
      String advice = completion.answer().strip();
      if (advice.isEmpty()) return AdviceResponse.unavailable("Trợ lý chưa tạo được lời khuyên.");
      return new AdviceResponse(true, advice, null, Instant.now());
    } catch (ApiException e) {
      return AdviceResponse.unavailable(e.getMessage());
    } catch (RuntimeException e) {
      org.slf4j.LoggerFactory.getLogger(getClass()).warn("Advice generation failed", e);
      return AdviceResponse.unavailable("Chưa tạo được lời khuyên lúc này.");
    }
  }
}
