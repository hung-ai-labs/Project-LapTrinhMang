package vn.edu.ptit.weather.service;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.net.URI;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.Semaphore;
import java.util.function.Consumer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import vn.edu.ptit.weather.exception.ApiException;

/**
 * Thin wrapper over the Gemini REST API: streaming chat with tool calling, plus embeddings for
 * retrieval. Only this class knows the wire format; callers work with Jackson nodes.
 */
@Component
public class GeminiClient {
  /** Hard cap on one answer so a runaway stream cannot exhaust memory. */
  private static final int MAX_ANSWER_CHARS = 32_000;

  private static final Duration CONNECT_TIMEOUT = Duration.ofSeconds(5);
  /**
   * How long one candidate may take to return response headers. A streaming endpoint answers these
   * within seconds, so a longer wait only means that model is wedged — and waiting past the total
   * budget would strand the request on it while a healthy model sits further down the chain.
   */
  private static final Duration RESPONSE_HEADER_TIMEOUT = Duration.ofSeconds(12);
  private static final Duration EMBED_TIMEOUT = Duration.ofSeconds(30);

  /** Must stay well under the SSE emitter timeout so the client still receives an error event. */
  private static final Duration TOTAL_ATTEMPT_BUDGET = Duration.ofSeconds(70);

  private final ObjectMapper json;
  private final String baseUrl;
  private final String apiKey;
  /** Primary model first, then fallbacks tried in order when one is retired or saturated. */
  private final List<String> models;

  private final String embedModel;
  private final int embedDimensions;
  private final HttpClient http =
      HttpClient.newBuilder().connectTimeout(CONNECT_TIMEOUT).build();
  private final Semaphore slots = new Semaphore(4);

  public GeminiClient(
      ObjectMapper json,
      @Value("${weather.gemini-base-url}") String baseUrl,
      @Value("${weather.gemini-api-key}") String apiKey,
      @Value("${weather.gemini-model}") String model,
      @Value("${weather.gemini-fallback-models}") String fallbackModels,
      @Value("${weather.gemini-embed-model}") String embedModel,
      @Value("${weather.gemini-embed-dimensions}") int embedDimensions) {
    this.json = json;
    this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
    this.apiKey = apiKey == null ? "" : apiKey.strip();
    var candidates = new ArrayList<String>();
    candidates.add(model.strip());
    for (String fallback : fallbackModels.split(","))
      if (!fallback.isBlank() && !candidates.contains(fallback.strip()))
        candidates.add(fallback.strip());
    this.models = List.copyOf(candidates);
    this.embedModel = embedModel;
    this.embedDimensions = embedDimensions;
    if (!configured())
      org.slf4j.LoggerFactory.getLogger(getClass())
          .warn(
              "GEMINI_API_KEY is empty, so chat and advisory stay disabled. .env is resolved"
                  + " against the working directory, which is {}",
              java.nio.file.Path.of("").toAbsolutePath());
  }

  public boolean configured() {
    return !apiKey.isBlank();
  }

  public int embedDimensions() {
    return embedDimensions;
  }

  public void requireConfigured() {
    if (!configured())
      throw new ApiException(503, "Chatbot chưa được cấu hình: thiếu GEMINI_API_KEY trong .env.");
  }

  /** One model turn: free text plus any tools the model decided to call. */
  public record Turn(String text, List<ToolCall> calls) {}

  /**
   * Gemini 3 thinking models attach a thoughtSignature to each functionCall part and reject the
   * follow-up turn unless the signature is replayed verbatim alongside the call.
   */
  public record ToolCall(String name, JsonNode args, String thoughtSignature) {}

  /**
   * Streams one model turn. Text deltas are handed to {@code onDelta} as they arrive; the returned
   * turn also carries any function calls so the caller can run them and continue the conversation.
   */
  public Turn streamTurn(
      ArrayNode contents, ArrayNode tools, String systemInstruction, Consumer<String> onDelta) {
    // Every candidate is tried once before any sleeping. A 503 means that one model is saturated,
    // and the next candidate normally answers straight away, so spending the budget on backoff for
    // the primary would strand the request while a working model sits further down the list.
    // The HTTP status is checked before any delta is emitted, so a retry can never replay text the
    // client already saw.
    long[] roundPauseMillis = {0, 1_000, 3_000, 8_000};
    // Retries and fallbacks share one budget: the SSE response must finish before its own
    // timeout, otherwise the client is dropped with no answer at all.
    long deadline = System.nanoTime() + TOTAL_ATTEMPT_BUDGET.toNanos();
    var logger = org.slf4j.LoggerFactory.getLogger(getClass());
    var live = new ArrayList<>(models);
    ApiException last = null;
    for (long pause : roundPauseMillis) {
      if (live.isEmpty()) break;
      if (pause > 0) {
        logger.warn("All {} Gemini models busy, waiting {} ms before another sweep", live.size(), pause);
        try {
          Thread.sleep(pause);
        } catch (InterruptedException interrupted) {
          Thread.currentThread().interrupt();
          throw new ApiException(503, "Đã hủy yêu cầu tới Gemini.");
        }
      }
      for (var candidate = live.iterator(); candidate.hasNext(); ) {
        String model = candidate.next();
        Duration remaining = Duration.ofNanos(deadline - System.nanoTime());
        if (remaining.isNegative() || remaining.isZero()) {
          throw last == null ? new ApiException(503, "Gemini chưa sẵn sàng.") : last;
        }
        Duration attemptTimeout =
            remaining.compareTo(RESPONSE_HEADER_TIMEOUT) < 0 ? remaining : RESPONSE_HEADER_TIMEOUT;
        try {
          return streamOnce(model, contents, tools, systemInstruction, onDelta, attemptTimeout);
        } catch (ApiException e) {
          last = e;
          // A retired model will not come back during this request; stop offering it.
          if (e.getStatus() == 404) {
            logger.warn("Gemini {} is not available to this key (404), dropping it", model);
            candidate.remove();
            continue;
          }
          boolean retryable = e.getStatus() == 503 || e.getStatus() == 429;
          if (!retryable) throw e;
          logger.warn("Gemini {} unavailable ({}), trying next", model, e.getStatus());
        }
      }
    }
    throw last == null ? new ApiException(503, "Gemini chưa sẵn sàng.") : last;
  }

  private Turn streamOnce(
      String model,
      ArrayNode contents,
      ArrayNode tools,
      String systemInstruction,
      Consumer<String> onDelta,
      Duration attemptTimeout) {
    requireConfigured();
    ObjectNode body = json.createObjectNode();
    body.set("contents", contents);
    if (tools != null && !tools.isEmpty()) body.set("tools", tools);
    if (systemInstruction != null && !systemInstruction.isBlank())
      body.set(
          "systemInstruction",
          json.createObjectNode()
              .set(
                  "parts",
                  json.createArrayNode().add(json.createObjectNode().put("text", systemInstruction))));
    ObjectNode generation = json.createObjectNode();
    generation.put("temperature", 0.3);
    generation.put("maxOutputTokens", 2048);
    body.set("generationConfig", generation);

    var answer = new StringBuilder();
    var calls = new ArrayList<ToolCall>();
    boolean acquired = false;
    try {
      acquired = slots.tryAcquire(5, java.util.concurrent.TimeUnit.SECONDS);
      if (!acquired) throw new ApiException(503, "Chatbot đang quá tải, thử lại sau.");
      var request =
          HttpRequest.newBuilder(
                  URI.create(baseUrl + "/models/" + model + ":streamGenerateContent?alt=sse"))
              .timeout(attemptTimeout)
              // Key travels in a header, never in the URL, so it cannot leak through access logs.
              .header("x-goog-api-key", apiKey)
              .header("Content-Type", "application/json")
              .POST(
                  HttpRequest.BodyPublishers.ofString(
                      json.writeValueAsString(body), StandardCharsets.UTF_8))
              .build();
      HttpResponse<java.util.stream.Stream<String>> response =
          http.send(request, HttpResponse.BodyHandlers.ofLines());
      if (response.statusCode() != 200) {
        // Upstream detail stays in the server log; the client only sees a safe message.
        try (var error = response.body()) {
          org.slf4j.LoggerFactory.getLogger(getClass())
              .warn(
                  "Gemini streamGenerateContent {}: {}",
                  response.statusCode(),
                  error.limit(20).reduce("", (a, b) -> a + b));
        }
        throw new ApiException(statusFor(response.statusCode()), messageFor(response.statusCode()));
      }
      try (var lines = response.body()) {
        var iterator = lines.iterator();
        while (iterator.hasNext()) {
          String line = iterator.next();
          if (!line.startsWith("data:")) continue;
          String payload = line.substring(5).strip();
          if (payload.isEmpty() || payload.equals("[DONE]")) continue;
          JsonNode event = json.readTree(payload);
          for (JsonNode part : event.path("candidates").path(0).path("content").path("parts")) {
            JsonNode call = part.get("functionCall");
            if (call != null && call.hasNonNull("name")) {
              JsonNode signature = part.get("thoughtSignature");
              calls.add(
                  new ToolCall(
                      call.path("name").asText(),
                      call.has("args") ? call.get("args") : json.createObjectNode(),
                      signature != null && signature.isTextual() ? signature.asText() : null));
              continue;
            }
            String text = part.path("text").asText("");
            if (text.isEmpty()) continue;
            if (answer.length() + text.length() > MAX_ANSWER_CHARS) {
              String clipped = text.substring(0, MAX_ANSWER_CHARS - answer.length());
              answer.append(clipped);
              onDelta.accept(clipped);
              return new Turn(answer.toString(), calls);
            }
            answer.append(text);
            onDelta.accept(text);
          }
        }
      }
      return new Turn(answer.toString(), calls);
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new ApiException(503, "Đã hủy yêu cầu tới Gemini.");
    } catch (java.io.IOException e) {
      throw new ApiException(503, "Không kết nối được Gemini.");
    } finally {
      if (acquired) slots.release();
    }
  }

  /**
   * Embeds several passages in one call. {@code taskType} must be RETRIEVAL_DOCUMENT when indexing
   * and RETRIEVAL_QUERY when searching — Gemini tunes the vector space per task.
   */
  /**
   * The free embedding tier is limited per minute, and indexing bursts straight through it. Retry
   * with widening backoff instead of failing a whole re-index on one throttled call.
   */
  public List<float[]> embed(List<String> texts, String taskType) {
    long[] backoffMillis = {2_000, 5_000, 15_000, 30_000};
    for (int attempt = 0; ; attempt++) {
      try {
        return embedOnce(texts, taskType);
      } catch (ApiException e) {
        if (e.getStatus() != 429 || attempt >= backoffMillis.length) throw e;
        org.slf4j.LoggerFactory.getLogger(getClass())
            .warn("Gemini embeddings throttled, retrying in {} ms", backoffMillis[attempt]);
        try {
          Thread.sleep(backoffMillis[attempt]);
        } catch (InterruptedException interrupted) {
          Thread.currentThread().interrupt();
          throw new ApiException(503, "Đã hủy yêu cầu tới Gemini.");
        }
      }
    }
  }

  private List<float[]> embedOnce(List<String> texts, String taskType) {
    requireConfigured();
    if (texts.isEmpty()) return List.of();
    ArrayNode requests = json.createArrayNode();
    for (String text : texts) {
      ObjectNode one = json.createObjectNode();
      one.put("model", "models/" + embedModel);
      one.set(
          "content",
          json.createObjectNode()
              .set("parts", json.createArrayNode().add(json.createObjectNode().put("text", text))));
      one.put("taskType", taskType);
      one.put("outputDimensionality", embedDimensions);
      requests.add(one);
    }
    ObjectNode body = json.createObjectNode();
    body.set("requests", requests);
    try {
      var request =
          HttpRequest.newBuilder(
                  URI.create(baseUrl + "/models/" + embedModel + ":batchEmbedContents"))
              .timeout(EMBED_TIMEOUT)
              .header("x-goog-api-key", apiKey)
              .header("Content-Type", "application/json")
              .POST(
                  HttpRequest.BodyPublishers.ofString(
                      json.writeValueAsString(body), StandardCharsets.UTF_8))
              .build();
      HttpResponse<byte[]> response =
          http.send(request, HttpResponse.BodyHandlers.ofByteArray());
      if (response.statusCode() != 200) {
        org.slf4j.LoggerFactory.getLogger(getClass())
            .warn(
                "Gemini batchEmbedContents {}: {}",
                response.statusCode(),
                new String(response.body(), StandardCharsets.UTF_8));
        throw new ApiException(statusFor(response.statusCode()), messageFor(response.statusCode()));
      }
      JsonNode embeddings = json.readTree(response.body()).path("embeddings");
      if (!embeddings.isArray() || embeddings.size() != texts.size())
        throw new ApiException(503, "Gemini trả về số vector không khớp.");
      var vectors = new ArrayList<float[]>(texts.size());
      for (JsonNode embedding : embeddings) vectors.add(normalize(embedding.path("values")));
      return vectors;
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new ApiException(503, "Đã hủy yêu cầu tới Gemini.");
    } catch (java.io.IOException e) {
      throw new ApiException(503, "Không kết nối được Gemini.");
    }
  }

  public float[] embedOne(String text, String taskType) {
    return embed(List.of(text), taskType).get(0);
  }

  /**
   * gemini-embedding-001 only returns unit-length vectors at full width; truncating via
   * outputDimensionality requires re-normalising, otherwise cosine distance is skewed.
   */
  private float[] normalize(JsonNode values) {
    if (!values.isArray() || values.size() != embedDimensions)
      throw new ApiException(503, "Vector Gemini sai số chiều.");
    var vector = new float[values.size()];
    double sum = 0;
    for (int i = 0; i < values.size(); i++) {
      double value = values.get(i).asDouble();
      if (!Double.isFinite(value)) throw new ApiException(503, "Vector Gemini không hợp lệ.");
      vector[i] = (float) value;
      sum += value * value;
    }
    double length = Math.sqrt(sum);
    if (length <= 0) throw new ApiException(503, "Vector Gemini rỗng.");
    for (int i = 0; i < vector.length; i++) vector[i] = (float) (vector[i] / length);
    return vector;
  }

  /**
   * 404 (retired model) and 400 (malformed request) are kept distinct: neither is worth retrying,
   * and collapsing them into 503 would burn the whole retry budget on a permanent failure.
   */
  private int statusFor(int upstream) {
    return switch (upstream) {
      case 429 -> 429;
      case 404 -> 404;
      case 400 -> 400;
      default -> 503;
    };
  }

  private String messageFor(int upstream) {
    return switch (upstream) {
      case 400 -> "Yêu cầu gửi tới Gemini không hợp lệ.";
      case 401, 403 -> "GEMINI_API_KEY không hợp lệ hoặc bị từ chối.";
      case 404 -> "Model Gemini không còn khả dụng, hãy cập nhật GEMINI_MODEL.";
      case 429 -> "Đã vượt hạn mức Gemini, thử lại sau ít phút.";
      default -> "Gemini đang quá tải, vui lòng thử lại sau ít phút.";
    };
  }
}
