package vn.edu.ptit.weather.network;

import com.fasterxml.jackson.databind.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Profile;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import vn.edu.ptit.weather.entity.Ward;
import vn.edu.ptit.weather.repository.WardRepository;
import vn.edu.ptit.weather.service.*;

/** Independent collection and delivery loops keep collecting during a TCP outage. */
@Component
@Profile("collector")
public class Collector {
  private final WardRepository wards;
  private final OpenMeteoClient provider;
  private final ObjectMapper json;
  private final Set<String> selected;
  private final boolean allWards;
  private final String host;
  private final int port;
  private final Path outbox;
  private final int capacity;
  private List<Ward> locations = List.of();
  private Instant locationsLoaded = Instant.EPOCH;
  private final Map<String, Instant> lastFetch = new HashMap<>();
  private Instant nextProviderAttempt = Instant.EPOCH, nextDelivery = Instant.EPOCH;
  private int deliveryBackoff = 1;

  public Collector(
      WardRepository wards,
      OpenMeteoClient provider,
      ObjectMapper json,
      @Value("${COLLECTOR_WARD_IDS:}") String selected,
      @Value("${COLLECTOR_ALL_WARDS:false}") boolean allWards,
      @Value("${COLLECTOR_HOST:127.0.0.1}") String host,
      @Value("${weather.tcp-port}") int port,
      @Value("${COLLECTOR_OUTBOX:.collector/outbox}") String outbox,
      @Value("${COLLECTOR_MAX_PENDING:10000}") int capacity) {
    if (selected.isBlank() == !allWards)
      throw new IllegalArgumentException(
          "Choose explicit COLLECTOR_WARD_IDS or COLLECTOR_ALL_WARDS=true");
    if (capacity < 1 || capacity > 100000)
      throw new IllegalArgumentException("Invalid collector outbox capacity");
    this.wards = wards;
    this.provider = provider;
    this.json = json;
    this.selected =
        selected.isBlank()
            ? Set.of()
            : new HashSet<>(Arrays.asList(selected.trim().split("\\s*,\\s*")));
    this.allWards = allWards;
    this.host = host;
    this.port = port;
    this.outbox = Path.of(outbox);
    this.capacity = capacity;
  }

  @Scheduled(fixedDelay = 1000, initialDelay = 5000)
  public void collect() {
    if (nextProviderAttempt.isAfter(Instant.now())) return;
    try {
      Files.createDirectories(outbox);
      long pending;
      try (var files = Files.list(outbox)) {
        pending =
            files
                .filter(p -> p.toString().endsWith(".json") || p.toString().endsWith(".rejected"))
                .limit(capacity)
                .count();
      }
      if (pending >= capacity) return;
      if (locationsLoaded.plusSeconds(600).isBefore(Instant.now())) {
        locations = List.copyOf(wards.findByIsActiveTrueOrderByNameAsc());
        locationsLoaded = Instant.now();
      }
      var due =
          locations.stream()
              .filter(w -> allWards || selected.contains(w.getId()))
              .filter(w -> w.getLatitude() != null && w.getLongitude() != null)
              .filter(
                  w ->
                      !lastFetch
                          .getOrDefault(w.getId(), Instant.EPOCH)
                          .plusSeconds(900)
                          .isAfter(Instant.now()))
              .limit(Math.min(50, capacity - pending))
              .toList();
      if (due.isEmpty()) return;
      var payloads =
          provider.fetchMany(
              due,
              Map.of(
                  "current",
                  "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation",
                  "forecast_days",
                  "1",
                  "timezone",
                  "UTC"));
      var events = new ArrayList<vn.edu.ptit.weather.dto.WeatherDto.ObservationRequest>();
      for (int i = 0; i < due.size(); i++)
        events.add(CurrentWeatherService.normalize(due.get(i).getId(), payloads.get(i)));
      for (var event : events) {
        String payload = json.writeValueAsString(event);
        String hash =
            HexFormat.of()
                .formatHex(
                    java.security.MessageDigest.getInstance("SHA-256")
                        .digest(payload.getBytes(StandardCharsets.UTF_8)));
        Path target = outbox.resolve(event.eventId() + "-" + hash + ".json"),
            temporary = outbox.resolve(event.eventId() + "-" + hash + ".tmp");
        // Never replace a conflicting event sharing this UUID; preserve both payloads for ACK
        // checking.
        if (!Files.exists(target)) {
          Files.writeString(temporary, payload);
          Files.move(
              temporary,
              target,
              StandardCopyOption.ATOMIC_MOVE,
              StandardCopyOption.REPLACE_EXISTING);
        }
        lastFetch.put(event.wardId(), Instant.now());
      }
    } catch (Exception e) {
      nextProviderAttempt = Instant.now().plusSeconds(60);
      warn("Collection deferred", e);
    }
  }

  @Scheduled(fixedDelay = 1000, initialDelay = 5000)
  public void deliver() {
    if (nextDelivery.isAfter(Instant.now()) || !Files.isDirectory(outbox)) return;
    try (var files = Files.list(outbox)) {
      // Bound delivery work per tick so the scheduler can continue heartbeats and collection.
      for (Path file :
          files.filter(p -> p.toString().endsWith(".json")).sorted().limit(20).toList()) {
        String payload = Files.readString(file);
        JsonNode event = json.readTree(payload);
        try (Socket socket = new Socket()) {
          socket.connect(new InetSocketAddress(host, port), 5000);
          socket.setSoTimeout(10000);
          socket.getOutputStream().write((payload + "\n").getBytes(StandardCharsets.UTF_8));
          socket.getOutputStream().flush();
          String frame =
              new BufferedReader(
                      new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8))
                  .readLine();
          JsonNode reply = frame == null ? null : json.readTree(frame);
          if (reply == null
              || !reply.path("event_id").asText().equals(event.path("event_id").asText()))
            throw new IOException("Missing or mismatched ACK");
          String status = reply.path("status").asText(), code = reply.path("code").asText();
          if (status.equals("accepted") || status.equals("duplicate")) Files.delete(file);
          else if (status.equals("error")
              && Set.of("event_conflict", "invalid_ward", "invalid_observation").contains(code))
            Files.move(
                file,
                file.resolveSibling(file.getFileName() + ".rejected"),
                StandardCopyOption.REPLACE_EXISTING);
          else throw new IOException("Delivery must retry");
          deliveryBackoff = 1;
        }
      }
    } catch (Exception e) {
      nextDelivery = Instant.now().plusSeconds(deliveryBackoff);
      deliveryBackoff = Math.min(60, deliveryBackoff * 2);
      warn("TCP delivery deferred", e);
    }
  }

  private void warn(String message, Exception error) {
    org.slf4j.LoggerFactory.getLogger(getClass())
        .warn("{}: {}", message, error.getClass().getSimpleName());
  }
}
