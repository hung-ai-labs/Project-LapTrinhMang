package vn.edu.ptit.weather;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import java.io.*;
import java.net.*;
import java.net.http.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.*;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.ActiveProfiles;
import vn.edu.ptit.weather.entity.*;
import vn.edu.ptit.weather.network.TcpIngestionServer;
import vn.edu.ptit.weather.repository.*;

@SpringBootTest(
    webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
    properties = {
      "weather.heartbeat-millis=100",
      "weather.tcp-frame-timeout-millis=500",
      "weather.database-url=jdbc:h2:mem:network-parity;MODE=PostgreSQL;DB_CLOSE_DELAY=-1"
    })
@ActiveProfiles("test")
class NetworkParityTest {
  @Autowired TestRestTemplate http;
  @Autowired ObjectMapper json;
  @Autowired ProvinceRepository provinces;
  @Autowired WardRepository wards;
  @Autowired TcpIngestionServer tcp;
  @LocalServerPort int port;

  @BeforeEach
  void catalog() {
    if (provinces.existsById("01")) return;
    var p = new Province();
    p.setId("01");
    p.setName("Hà Nội");
    p.setDatasetVersion("test");
    provinces.save(p);
    for (String id : List.of("00004", "00008")) {
      var w = new Ward();
      w.setId(id);
      w.setProvinceId("01");
      w.setName(id);
      w.setDatasetVersion("test");
      wards.save(w);
    }
  }

  record Channel(
      WebSocket socket, BlockingQueue<JsonNode> messages, CompletableFuture<Integer> closed)
      implements AutoCloseable {
    @Override
    public void close() {
      socket.abort();
    }
  }

  Channel socket(String ward, String origin) throws Exception {
    var messages = new LinkedBlockingQueue<JsonNode>();
    var closed = new CompletableFuture<Integer>();
    var builder = HttpClient.newHttpClient().newWebSocketBuilder();
    if (origin != null) builder.header("Origin", origin);
    var ws =
        builder
            .buildAsync(
                URI.create("ws://localhost:" + port + "/api/v1/ws/wards/" + ward + "/weather"),
                new WebSocket.Listener() {
                  StringBuilder buffer = new StringBuilder();

                  public void onOpen(WebSocket socket) {
                    socket.request(1);
                  }

                  public CompletionStage<?> onText(
                      WebSocket socket, CharSequence text, boolean last) {
                    buffer.append(text);
                    if (last) {
                      try {
                        messages.add(json.readTree(buffer.toString()));
                      } catch (Exception e) {
                        throw new RuntimeException(e);
                      }
                      buffer.setLength(0);
                    }
                    socket.request(1);
                    return null;
                  }

                  public CompletionStage<?> onClose(WebSocket socket, int status, String reason) {
                    closed.complete(status);
                    return null;
                  }
                })
            .get(3, TimeUnit.SECONDS);
    return new Channel(ws, messages, closed);
  }

  Map<String, Object> observation(String source, String ward) {
    return Map.of(
        "event_id",
        UUID.randomUUID().toString(),
        "ward_id",
        ward,
        "temperature",
        36,
        "humidity",
        80,
        "wind_speed",
        55,
        "rainfall",
        25,
        "source",
        source,
        "observed_at",
        "2026-11-04T07:15:00+07:00");
  }

  JsonNode send(Object data) throws Exception {
    try (Socket socket = new Socket("127.0.0.1", tcp.boundPort())) {
      socket.setSoTimeout(2000);
      socket
          .getOutputStream()
          .write(
              (json.writeValueAsString(data) + "\n")
                  .getBytes(java.nio.charset.StandardCharsets.UTF_8));
      socket.getOutputStream().flush();
      return json.readTree(
          new BufferedReader(new InputStreamReader(socket.getInputStream())).readLine());
    }
  }

  @Test
  void heartbeatContinuesWithoutWeatherAndReconnectReceivesNewUpdates() throws Exception {
    for (int attempt = 0; attempt < 2; attempt++)
      try (var channel = socket("00004", null)) {
        assertThat(channel.messages.poll(2, TimeUnit.SECONDS).path("type").asText())
            .isEqualTo("heartbeat");
        var value = observation("simulator", "00004");
        assertThat(send(value).path("status").asText()).isEqualTo("accepted");
        JsonNode update = awaitUpdate(channel, 2000);
        assertThat(update.path("observation").path("id").asText()).isEqualTo(value.get("event_id"));
      }
  }

  JsonNode awaitUpdate(Channel channel, long millis) throws Exception {
    long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(millis);
    while (System.nanoTime() < deadline) {
      var row = channel.messages.poll(30, TimeUnit.MILLISECONDS);
      if (row != null && row.path("type").asText().equals("weather.update")) return row;
    }
    return null;
  }

  @Test
  void filtersBothWardAndSourceAndNeverBroadcastsDuplicate() throws Exception {
    try (var channel = socket("00004", null)) {
      assertThat(channel.messages.poll(2, TimeUnit.SECONDS)).isNotNull();
      send(observation("provider", "00004"));
      send(observation("simulator", "00008"));
      assertThat(awaitUpdate(channel, 300)).isNull();
      var value = observation("simulator", "00004");
      send(value);
      assertThat(awaitUpdate(channel, 1500)).isNotNull();
      assertThat(send(value).path("status").asText()).isEqualTo("duplicate");
      assertThat(awaitUpdate(channel, 300)).isNull();
    }
  }

  @Test
  void rejectsHostileOriginAndUnknownWard() throws Exception {
    assertThatThrownBy(() -> socket("00004", "https://untrusted.invalid"))
        .isInstanceOf(ExecutionException.class);
    try (var channel = socket("missing", null)) {
      assertThat(channel.closed.get(2, TimeUnit.SECONDS)).isEqualTo(1008);
    }
  }

  @Test
  void recoversAfterMalformedAndCoalescedFramesAndEnforcesWholeFrameDeadline() throws Exception {
    try (Socket socket = new Socket("127.0.0.1", tcp.boundPort())) {
      socket.setSoTimeout(2000);
      var out = socket.getOutputStream();
      var reader = new BufferedReader(new InputStreamReader(socket.getInputStream()));
      String frames =
          "not-json\n"
              + json.writeValueAsString(observation("simulator", "00004"))
              + "\n"
              + json.writeValueAsString(observation("simulator", "00004"))
              + "\n";
      out.write(frames.getBytes());
      out.flush();
      assertThat(json.readTree(reader.readLine()).path("code").asText())
          .isEqualTo("invalid_observation");
      assertThat(json.readTree(reader.readLine()).path("status").asText()).isEqualTo("accepted");
      assertThat(json.readTree(reader.readLine()).path("status").asText()).isEqualTo("accepted");
      for (int i = 0; i < 4; i++) {
        out.write('x');
        out.flush();
        Thread.sleep(150);
      }
      assertThat(json.readTree(reader.readLine()).path("code").asText())
          .isEqualTo("frame_limit_or_timeout");
    }
  }

  @Test
  void rejectsNaiveTimestampUnknownFieldsAndNonFiniteValues() throws Exception {
    for (var change :
        List.of(
            Map.of("observed_at", "2026-11-04T07:15:00"),
            Map.of("humidity", 101),
            Map.of("temperature", Double.NaN),
            Map.of("user_id", "unexpected"))) {
      var value = new HashMap<String, Object>(observation("simulator", "00004"));
      value.putAll(change);
      assertThat(send(value).path("code").asText()).isEqualTo("invalid_observation");
    }
  }

  @Test
  void twoProducersDoNotBlockHealthRequests() throws Exception {
    var pool = Executors.newFixedThreadPool(2);
    try {
      var jobs = new ArrayList<Future<?>>();
      for (int i = 0; i < 2; i++)
        jobs.add(
            pool.submit(
                () -> {
                  for (int n = 0; n < 20; n++)
                    try {
                      assertThat(send(observation("simulator", "00004")).path("status").asText())
                          .isEqualTo("accepted");
                    } catch (Exception e) {
                      throw new RuntimeException(e);
                    }
                }));
      for (int i = 0; i < 10; i++)
        assertThat(http.getForEntity("/api/v1/health", String.class).getStatusCode().value())
            .isEqualTo(200);
      for (var job : jobs) job.get(15, TimeUnit.SECONDS);
    } finally {
      pool.shutdownNow();
    }
  }
}
