package vn.edu.ptit.weather.service;

import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import vn.edu.ptit.weather.dto.WeatherDto.*;
import vn.edu.ptit.weather.entity.Ward;
import vn.edu.ptit.weather.exception.ApiException;

@Service
@RequiredArgsConstructor
public class CurrentWeatherService {
  private final GeographyService geography;
  private final ObservationService observations;
  private final IngestionGateway ingestion;
  private final OpenMeteoClient provider;

  @Value("${weather.source}")
  private String source;

  private record CachedCurrent(long bucket, WeatherEvent event) {}

  private final Map<String, CachedCurrent> cache = new ConcurrentHashMap<>();
  private final Map<String, Instant> retryAfter = new ConcurrentHashMap<>();
  private final Object[] locks =
      java.util.stream.IntStream.range(0, 64).mapToObj(i -> new Object()).toArray();

  public WeatherEvent current(String wardId) {
    Ward ward = geography.ward(wardId);
    synchronized (locks[Math.floorMod(wardId.hashCode(), locks.length)]) {
      long bucket = Instant.now().getEpochSecond() / 900;
      var cached = cache.get(wardId);
      if (source.equals("provider") && cached != null && cached.bucket() == bucket)
        return cached.event();
      var latest = observations.latest(wardId, source);
      if (!source.equals("provider"))
        return observations.event(
            latest.orElseThrow(() -> new ApiException(404, "Chưa có dữ liệu cho nguồn đã chọn.")));
      if (latest.isPresent()
          && latest.get().getObservedAt().getEpochSecond() / 900
              == Instant.now().getEpochSecond() / 900) return observations.event(latest.get());
      if (retryAfter.getOrDefault(wardId, Instant.EPOCH).isAfter(Instant.now()))
        return observations.event(
            latest.orElseThrow(() -> new ApiException(503, "Open-Meteo đang chờ thử lại.")));
      try {
        geography.coordinates(wardId);
        var payload =
            provider.fetch(
                ward.getLatitude().doubleValue(),
                ward.getLongitude().doubleValue(),
                Map.of(
                    "current",
                    "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
                    "forecast_days",
                    "1",
                    "timezone",
                    "UTC"));
        var request = normalize(wardId, payload);
        ingestion.ingest(request);
        retryAfter.remove(wardId);
        WeatherEvent event = observations.event(observations.latest(wardId, source).orElseThrow());
        if (cache.size() >= 4096)
          cache.entrySet().removeIf(entry -> entry.getValue().bucket() < bucket);
        if (cache.size() < 4096 || cache.containsKey(wardId))
          cache.put(wardId, new CachedCurrent(bucket, event));
        return event;
      } catch (ApiException e) {
        if (e.getStatus() != 503 && e.getStatus() != 409) throw e;
        if (retryAfter.size() > 4096)
          retryAfter.entrySet().removeIf(entry -> entry.getValue().isBefore(Instant.now()));
        retryAfter.put(wardId, Instant.now().plusSeconds(60));
        if (latest.isPresent()) return observations.event(latest.get());
        throw new ApiException(503, "Chưa lấy được dữ liệu Open-Meteo.");
      }
    }
  }

  public static ObservationRequest normalize(
      String wardId, com.fasterxml.jackson.databind.JsonNode payload) {
    OpenMeteoClient.units(
        payload,
        "current",
        Map.of(
            "temperature_2m",
            "°C",
            "relative_humidity_2m",
            "%",
            "wind_speed_10m",
            "km/h",
            "precipitation",
            "mm"));
    var current = payload.path("current");
    if (!current.path("time").isIntegralNumber()
        || !current.path("interval").isIntegralNumber()
        || !current.path("interval").canConvertToInt()
        || current.path("interval").asInt() <= 0)
      throw new ApiException(503, "Thời điểm Open-Meteo không hợp lệ.");
    Instant at = OpenMeteoClient.timestamp(current.path("time"));
    double rainfall =
        OpenMeteoClient.number(current.get("precipitation"), 0, 1000)
            * 3600
            / current.path("interval").asInt();
    if (rainfall > 1000) throw new ApiException(503, "Lượng mưa không hợp lệ.");
    // RFC 4122 UUID v5 uses the same namespace and timestamp representation as Python.
    UUID id = providerId(wardId, at);
    return new ObservationRequest(
        id,
        wardId,
        OpenMeteoClient.number(current.get("temperature_2m"), -60, 65),
        OpenMeteoClient.number(current.get("relative_humidity_2m"), 0, 100),
        OpenMeteoClient.number(current.get("wind_speed_10m"), 0, 500),
        Math.round(rainfall * 10000) / 10000.0,
        "provider",
        at);
  }

  static UUID providerId(String wardId, Instant at) {
    try {
      var namespace = UUID.fromString("6ba7b811-9dad-11d1-80b4-00c04fd430c8");
      var bytes =
          java.nio.ByteBuffer.allocate(16)
              .putLong(namespace.getMostSignificantBits())
              .putLong(namespace.getLeastSignificantBits())
              .array();
      var digest = java.security.MessageDigest.getInstance("SHA-1");
      digest.update(bytes);
      String timestamp =
          java.time.format.DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ssXXX")
              .withZone(java.time.ZoneOffset.UTC)
              .format(at)
              .replace("Z", "+00:00");
      byte[] hash =
          digest.digest(
              ("open-meteo:ward:" + wardId + ":" + timestamp)
                  .getBytes(java.nio.charset.StandardCharsets.UTF_8));
      hash[6] = (byte) ((hash[6] & 0x0f) | 0x50);
      hash[8] = (byte) ((hash[8] & 0x3f) | 0x80);
      var buffer = java.nio.ByteBuffer.wrap(hash);
      return new UUID(buffer.getLong(), buffer.getLong());
    } catch (java.security.NoSuchAlgorithmException e) {
      throw new IllegalStateException(e);
    }
  }
}
