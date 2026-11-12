package vn.edu.ptit.weather.network;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.*;
import java.io.*;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import vn.edu.ptit.weather.entity.Ward;
import vn.edu.ptit.weather.repository.WardRepository;
import vn.edu.ptit.weather.service.OpenMeteoClient;

class CollectorParityTest {
  @TempDir Path directory;
  ObjectMapper json =
      new ObjectMapper()
          .findAndRegisterModules()
          .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
          .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
  WardRepository wards = mock(WardRepository.class);
  OpenMeteoClient provider = mock(OpenMeteoClient.class);

  JsonNode current() throws Exception {
    return json.readTree(
        "{\"current_units\":{\"temperature_2m\":\"°C\",\"relative_humidity_2m\":\"%\",\"wind_speed_10m\":\"km/h\",\"precipitation\":\"mm\"},\"current\":{\"time\":1793751300,\"interval\":900,\"temperature_2m\":25,\"relative_humidity_2m\":80,\"wind_speed_10m\":5,\"precipitation\":0.5}}");
  }

  void setup(int count) throws Exception {
    var locations = new ArrayList<Ward>();
    for (int i = 0; i < count; i++) {
      var ward = new Ward();
      ward.setId("w" + i);
      ward.setLatitude(new java.math.BigDecimal("21"));
      ward.setLongitude(new java.math.BigDecimal("105"));
      locations.add(ward);
    }
    when(wards.findByIsActiveTrueOrderByNameAsc()).thenReturn(locations);
    when(provider.fetchMany(anyList(), anyMap()))
        .thenAnswer(
            call -> {
              List<?> batch = call.getArgument(0);
              var values = new ArrayList<JsonNode>();
              for (Object ignored : batch) values.add(current());
              return values;
            });
  }

  Collector collector(int port, int capacity) {
    return new Collector(
        wards, provider, json, "", true, "127.0.0.1", port, directory.toString(), capacity);
  }

  long pending() throws Exception {
    try (var files = Files.list(directory)) {
      return files.filter(p -> p.toString().endsWith(".json")).count();
    }
  }

  @Test
  void batchesSelectedWardsAndBoundsTheOutboxWithoutTcp() throws Exception {
    setup(55);
    var collector = collector(1, 51);
    collector.collect();
    assertThat(pending()).isEqualTo(50);
    collector.collect();
    assertThat(pending()).isEqualTo(51);
    collector.collect();
    assertThat(pending()).isEqualTo(51);
    verify(provider, times(2)).fetchMany(anyList(), anyMap());
  }

  @Test
  void replaysPendingFilesAfterRestartOnlyWithMatchingAck() throws Exception {
    setup(1);
    collector(1, 10).collect();
    assertThat(pending()).isEqualTo(1);
    var pool = Executors.newSingleThreadExecutor();
    try (var server = new ServerSocket(0, 5, InetAddress.getLoopbackAddress())) {
      var job =
          pool.submit(
              () -> {
                try (var socket = server.accept()) {
                  var event =
                      json.readTree(
                          new BufferedReader(new InputStreamReader(socket.getInputStream()))
                              .readLine());
                  socket
                      .getOutputStream()
                      .write(
                          (json.writeValueAsString(
                                      Map.of(
                                          "status",
                                          "duplicate",
                                          "event_id",
                                          event.path("event_id").asText()))
                                  + "\n")
                              .getBytes());
                  socket.getOutputStream().flush();
                } catch (Exception e) {
                  throw new RuntimeException(e);
                }
              });
      collector(server.getLocalPort(), 10).deliver();
      job.get(2, TimeUnit.SECONDS);
      assertThat(pending()).isZero();
    } finally {
      pool.shutdownNow();
    }
  }

  @Test
  void mismatchedAckRetainsFile() throws Exception {
    setup(1);
    collector(1, 10).collect();
    var pool = Executors.newSingleThreadExecutor();
    try (var server = new ServerSocket(0, 5, InetAddress.getLoopbackAddress())) {
      var job =
          pool.submit(
              () -> {
                try (var socket = server.accept()) {
                  new BufferedReader(new InputStreamReader(socket.getInputStream())).readLine();
                  socket
                      .getOutputStream()
                      .write("{\"status\":\"accepted\",\"event_id\":\"wrong\"}\n".getBytes());
                  socket.getOutputStream().flush();
                } catch (Exception e) {
                  throw new RuntimeException(e);
                }
              });
      collector(server.getLocalPort(), 10).deliver();
      job.get(2, TimeUnit.SECONDS);
      assertThat(pending()).isEqualTo(1);
    } finally {
      pool.shutdownNow();
    }
  }

  @Test
  void rejectedEventsStillCountTowardStorageCapacity() throws Exception {
    setup(1);
    Files.writeString(directory.resolve("kept.json.rejected"), "{}");
    collector(1, 1).collect();
    verify(provider, never()).fetchMany(anyList(), anyMap());
    assertThat(pending()).isZero();
  }
}
