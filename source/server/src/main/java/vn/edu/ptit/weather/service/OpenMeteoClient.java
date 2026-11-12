package vn.edu.ptit.weather.service;

import com.fasterxml.jackson.databind.*;
import java.io.ByteArrayOutputStream;
import java.net.*;
import java.net.http.*;
import java.nio.ByteBuffer;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import vn.edu.ptit.weather.exception.ApiException;

@Component
public class OpenMeteoClient {
  private final ObjectMapper json;
  private final String baseUrl;
  private final HttpClient http =
      HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
  private final Duration timeout;
  private final Semaphore slots = new Semaphore(4);

  @org.springframework.beans.factory.annotation.Autowired
  public OpenMeteoClient(ObjectMapper json, @Value("${weather.open-meteo-url}") String baseUrl) {
    this(json, baseUrl, Duration.ofSeconds(12));
  }

  public OpenMeteoClient(ObjectMapper json, String baseUrl, Duration timeout) {
    this.json = json;
    this.baseUrl = baseUrl;
    this.timeout = timeout;
  }

  public JsonNode fetch(double latitude, double longitude, Map<String, String> options) {
    JsonNode result =
        fetchCoordinates(Double.toString(latitude), Double.toString(longitude), options);
    if (!result.isObject()) throw new ApiException(503, "Dữ liệu Open-Meteo không hợp lệ.");
    return result;
  }

  public List<JsonNode> fetchMany(
      List<vn.edu.ptit.weather.entity.Ward> wards, Map<String, String> options) {
    if (wards.isEmpty() || wards.size() > 50)
      throw new IllegalArgumentException("Provider batch must contain 1–50 wards");
    String lat =
        wards.stream()
            .map(w -> w.getLatitude().toPlainString())
            .collect(java.util.stream.Collectors.joining(","));
    String lon =
        wards.stream()
            .map(w -> w.getLongitude().toPlainString())
            .collect(java.util.stream.Collectors.joining(","));
    var result = fetchCoordinates(lat, lon, options);
    var rows = new ArrayList<JsonNode>();
    if (result.isArray()) result.forEach(rows::add);
    else rows.add(result);
    if (rows.size() != wards.size() || rows.stream().anyMatch(row -> !row.isObject()))
      throw new ApiException(503, "Số điểm dự báo không khớp.");
    return rows;
  }

  private JsonNode fetchCoordinates(
      String latitude, String longitude, Map<String, String> options) {
    var params = new LinkedHashMap<String, String>();
    params.put("latitude", latitude);
    params.put("longitude", longitude);
    params.put("temperature_unit", "celsius");
    params.put("wind_speed_unit", "kmh");
    params.put("precipitation_unit", "mm");
    params.put("timeformat", "unixtime");
    params.put("timezone", "Asia/Ho_Chi_Minh");
    params.putAll(options);
    String query =
        params.entrySet().stream()
            .map(
                e ->
                    e.getKey()
                        + "="
                        + URLEncoder.encode(e.getValue(), java.nio.charset.StandardCharsets.UTF_8))
            .collect(java.util.stream.Collectors.joining("&"));
    boolean acquired = false;
    try {
      acquired = slots.tryAcquire(2, java.util.concurrent.TimeUnit.SECONDS);
      if (!acquired) throw new ApiException(503, "Hàng đợi Open-Meteo đang đầy.");
      var request =
          HttpRequest.newBuilder(URI.create(baseUrl + "?" + query))
              .timeout(timeout)
              .header("User-Agent", "WeatherStream-Education/1.0")
              .GET()
              .build();
      var pending = http.sendAsync(request, ignored -> new BoundedBody(262144));
      HttpResponse<byte[]> response;
      try {
        response = pending.get(timeout.toMillis(), TimeUnit.MILLISECONDS);
      } catch (TimeoutException e) {
        pending.cancel(true);
        throw new ApiException(503, "Open-Meteo quá thời gian chờ.");
      } catch (ExecutionException e) {
        throw new ApiException(503, "Chưa lấy được dữ liệu Open-Meteo.");
      } catch (InterruptedException e) {
        pending.cancel(true);
        throw e;
      }
      if (response.statusCode() != 200) throw new ApiException(503, "Open-Meteo chưa sẵn sàng.");
      JsonNode data = json.readTree(response.body());
      if (data == null || (!data.isObject() && !data.isArray()))
        throw new ApiException(503, "Dữ liệu Open-Meteo không hợp lệ.");
      return data;
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      throw new ApiException(503, "Đã hủy yêu cầu Open-Meteo.");
    } catch (java.io.IOException e) {
      throw new ApiException(503, "Chưa lấy được dữ liệu Open-Meteo.");
    } finally {
      if (acquired) slots.release();
    }
  }

  private static final class BoundedBody implements HttpResponse.BodySubscriber<byte[]> {
    private final int limit;
    private final ByteArrayOutputStream bytes = new ByteArrayOutputStream();
    private final CompletableFuture<byte[]> result = new CompletableFuture<>();
    private Flow.Subscription subscription;

    BoundedBody(int limit) {
      this.limit = limit;
    }

    @Override
    public CompletionStage<byte[]> getBody() {
      return result;
    }

    @Override
    public void onSubscribe(Flow.Subscription subscription) {
      this.subscription = subscription;
      subscription.request(1);
    }

    @Override
    public void onNext(List<ByteBuffer> buffers) {
      for (var buffer : buffers) {
        if (bytes.size() + (long) buffer.remaining() > limit) {
          subscription.cancel();
          result.completeExceptionally(new ApiException(503, "Dữ liệu Open-Meteo quá lớn."));
          return;
        }
        byte[] chunk = new byte[buffer.remaining()];
        buffer.get(chunk);
        bytes.writeBytes(chunk);
      }
      subscription.request(1);
    }

    @Override
    public void onError(Throwable error) {
      result.completeExceptionally(error);
    }

    @Override
    public void onComplete() {
      result.complete(bytes.toByteArray());
    }
  }

  public static java.time.Instant timestamp(JsonNode node) {
    if (node == null || !node.isIntegralNumber() || !node.canConvertToLong())
      throw new ApiException(503, "Mốc thời gian Open-Meteo không hợp lệ.");
    try {
      return java.time.Instant.ofEpochSecond(node.longValue());
    } catch (java.time.DateTimeException e) {
      throw new ApiException(503, "Mốc thời gian Open-Meteo ngoài phạm vi.");
    }
  }

  public static double number(JsonNode node, double min, double max) {
    if (node == null
        || !node.isNumber()
        || !Double.isFinite(node.doubleValue())
        || node.doubleValue() < min
        || node.doubleValue() > max)
      throw new ApiException(503, "Giá trị Open-Meteo không hợp lệ.");
    return node.doubleValue();
  }

  public static void units(JsonNode payload, String block, Map<String, String> expected) {
    for (var e : expected.entrySet())
      if (!payload.path(block + "_units").path(e.getKey()).asText().equals(e.getValue()))
        throw new ApiException(503, "Đơn vị Open-Meteo không hợp lệ.");
  }

  public static void series(JsonNode payload, String block, Collection<String> fields) {
    var values = payload.path(block);
    var times = values.path("time");
    if (!times.isArray() || times.isEmpty()) throw new ApiException(503, "Dự báo trống.");
    for (var t : times) timestamp(t);
    for (String field : fields)
      if (!values.path(field).isArray() || values.path(field).size() != times.size())
        throw new ApiException(503, "Dữ liệu dự báo thiếu trường.");
  }
}
