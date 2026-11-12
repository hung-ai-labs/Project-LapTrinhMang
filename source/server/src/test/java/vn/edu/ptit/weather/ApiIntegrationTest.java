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
import org.springframework.http.*;
import org.springframework.test.context.ActiveProfiles;
import vn.edu.ptit.weather.entity.*;
import vn.edu.ptit.weather.network.TcpIngestionServer;
import vn.edu.ptit.weather.repository.*;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class ApiIntegrationTest {
  @Autowired TestRestTemplate http;
  @Autowired ObjectMapper json;
  @Autowired ProvinceRepository provinces;
  @Autowired WardRepository wards;
  @Autowired ObservationRepository observations;
  @Autowired UserRepository users;
  @Autowired TcpIngestionServer tcp;
  @LocalServerPort int port;

  @BeforeEach
  void seed() {
    http.getRestTemplate()
        .setRequestFactory(new org.springframework.http.client.JdkClientHttpRequestFactory());
    if (provinces.existsById("01")) return;
    var province = new Province();
    province.setId("01");
    province.setName("Hà Nội");
    province.setDatasetVersion("test");
    provinces.save(province);
    for (String id : List.of("00004", "00008")) {
      var ward = new Ward();
      ward.setId(id);
      ward.setName("Ba Đình " + id);
      ward.setProvinceId("01");
      ward.setDatasetVersion("test");
      ward.setLatitude(new java.math.BigDecimal("21.03000"));
      ward.setLongitude(new java.math.BigDecimal("105.85000"));
      wards.save(ward);
    }
  }

  JsonNode body(ResponseEntity<String> response) throws Exception {
    return json.readTree(response.getBody());
  }

  HttpEntity<?> authorized(String token, Object data) {
    var headers = new org.springframework.http.HttpHeaders();
    headers.setBearerAuth(token);
    headers.setContentType(MediaType.APPLICATION_JSON);
    return new HttpEntity<>(data, headers);
  }

  @Test
  void registerLoginAddressLogoutAndRevocation() throws Exception {
    String email = UUID.randomUUID() + "@example.com";
    var response =
        http.postForEntity(
            "/api/v1/auth/register",
            Map.of("name", "Người thử", "email", email, "password", "A-test-password-123"),
            String.class);
    assertThat(response.getStatusCode().value()).isEqualTo(201);
    var data = body(response).path("data");
    String token = data.path("access_token").asText();
    assertThat(token).isNotBlank();
    assertThat(data.path("expires_in").asLong()).isEqualTo(1800);
    assertThat(data.path("user").has("password_hash")).isFalse();
    assertThat(users.findByEmail(email).orElseThrow().getPasswordHash()).startsWith("$argon2id$");
    var me =
        http.exchange("/api/v1/auth/me", HttpMethod.GET, authorized(token, null), String.class);
    assertThat(me.getStatusCode().value()).withFailMessage(me.getBody()).isEqualTo(200);
    assertThat(body(me).path("data").path("email").asText()).isEqualTo(email);
    var address =
        http.exchange(
            "/api/v1/users/me/address",
            HttpMethod.PATCH,
            authorized(token, Map.of("ward_id", "00004", "address_text", "Nhà thử nghiệm")),
            String.class);
    assertThat(body(address).path("data").path("ward").path("id").asText()).isEqualTo("00004");
    assertThat(
            http.postForEntity(
                    "/api/v1/auth/login",
                    Map.of("email", email, "password", "wrong-password"),
                    String.class)
                .getStatusCode()
                .value())
        .isEqualTo(401);
    var login =
        http.postForEntity(
            "/api/v1/auth/login",
            Map.of("email", email, "password", "A-test-password-123"),
            String.class);
    assertThat(login.getStatusCode().value()).isEqualTo(200);
    String second = body(login).path("data").path("access_token").asText();
    assertThat(
            http.exchange(
                    "/api/v1/auth/logout", HttpMethod.POST, authorized(token, null), String.class)
                .getStatusCode()
                .value())
        .isEqualTo(200);
    for (String revoked : List.of(token, second))
      assertThat(
              http.exchange(
                      "/api/v1/auth/me", HttpMethod.GET, authorized(revoked, null), String.class)
                  .getStatusCode()
                  .value())
          .isEqualTo(401);
  }

  @Test
  void rejectsInvalidRequestsAndDuplicateAccounts() throws Exception {
    assertThat(http.getForEntity("/api/v1/auth/me", String.class).getStatusCode().value())
        .isEqualTo(401);
    var invalid =
        http.postForEntity(
            "/api/v1/auth/register",
            Map.of("name", " ", "email", "invalid", "password", "short"),
            String.class);
    assertThat(invalid.getStatusCode().value()).isEqualTo(422);
    assertThat(body(invalid).path("error").path("details").isArray()).isTrue();
    String email = UUID.randomUUID() + "@example.com";
    var request = Map.of("name", "test", "email", email, "password", "Valid-password-123");
    assertThat(
            http.postForEntity("/api/v1/auth/register", request, String.class)
                .getStatusCode()
                .value())
        .isEqualTo(201);
    assertThat(
            http.postForEntity("/api/v1/auth/register", request, String.class)
                .getStatusCode()
                .value())
        .isEqualTo(409);
    assertThat(http.getForEntity("/api/v1/wards?page=0", String.class).getStatusCode().value())
        .isEqualTo(422);
    assertThat(http.getForEntity("/api/v1/wards/missing", String.class).getStatusCode().value())
        .isEqualTo(404);
  }

  @Test
  void publicCatalogPaginationNearestAndHealth() throws Exception {
    var catalog = body(http.getForEntity("/api/v1/provinces?page_size=1", String.class));
    assertThat(catalog.path("success").asBoolean()).isTrue();
    assertThat(catalog.path("data").path("results").get(0).path("id").asText()).isEqualTo("01");
    var page =
        body(http.getForEntity("/api/v1/wards?province_id=01&page_size=1", String.class))
            .path("data");
    assertThat(page.path("count").asInt()).isEqualTo(2);
    assertThat(page.path("next").asText()).contains("page=2");
    var nearest =
        body(http.postForEntity(
                "/api/v1/geography/nearest-ward",
                Map.of("latitude", 21.03, "longitude", 105.85),
                String.class))
            .path("data");
    assertThat(nearest.path("distance_km").asDouble()).isLessThan(0.001);
    assertThat(nearest.path("match_type").asText()).isEqualTo("nearest");
    assertThat(http.getForEntity("/api/v1/health", String.class).getStatusCode().value())
        .isEqualTo(200);
  }

  Map<String, Object> observation(String id) {
    return new LinkedHashMap<>(
        Map.of(
            "event_id",
            id,
            "ward_id",
            "00004",
            "temperature",
            36.0,
            "humidity",
            80.0,
            "wind_speed",
            55.0,
            "rainfall",
            21.0,
            "source",
            "simulator",
            "observed_at",
            Instant.now().toString()));
  }

  @Test
  void tcpPersistsBeforeBroadcastAndHandlesDuplicateConflictValidationAndFragmentation()
      throws Exception {
    var messages = new LinkedBlockingQueue<String>();
    WebSocket ws =
        HttpClient.newHttpClient()
            .newWebSocketBuilder()
            .buildAsync(
                URI.create("ws://localhost:" + port + "/api/v1/ws/wards/00004/weather"),
                new WebSocket.Listener() {
                  StringBuilder buffer = new StringBuilder();

                  @Override
                  public void onOpen(WebSocket socket) {
                    socket.request(1);
                  }

                  @Override
                  public CompletionStage<?> onText(
                      WebSocket socket, CharSequence text, boolean last) {
                    buffer.append(text);
                    if (last) {
                      messages.offer(buffer.toString());
                      buffer.setLength(0);
                    }
                    socket.request(1);
                    return null;
                  }
                })
            .get(5, TimeUnit.SECONDS);
    try (Socket socket = new Socket("127.0.0.1", tcp.boundPort())) {
      socket.setSoTimeout(5000);
      var out = socket.getOutputStream();
      var reader =
          new BufferedReader(
              new InputStreamReader(
                  socket.getInputStream(), java.nio.charset.StandardCharsets.UTF_8));
      String id = UUID.randomUUID().toString();
      var request = observation(id);
      String frame = json.writeValueAsString(request) + "\n";
      out.write(frame.substring(0, 12).getBytes());
      out.flush();
      out.write(frame.substring(12).getBytes());
      out.flush();
      assertThat(json.readTree(reader.readLine()).path("status").asText()).isEqualTo("accepted");
      JsonNode update = null;
      long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
      while (System.nanoTime() < deadline) {
        String text = messages.poll(1, TimeUnit.SECONDS);
        if (text == null) continue;
        var message = json.readTree(text);
        if (message.path("type").asText().equals("weather.update")) {
          update = message;
          break;
        }
      }
      assertThat(update).isNotNull();
      assertThat(update.path("observation").path("id").asText()).isEqualTo(id);
      assertThat(update.path("alerts").size()).isEqualTo(3);
      assertThat(observations.existsById(id)).isTrue();
      out.write(frame.getBytes());
      out.flush();
      assertThat(json.readTree(reader.readLine()).path("status").asText()).isEqualTo("duplicate");
      request.put("temperature", 20.0);
      out.write((json.writeValueAsString(request) + "\n").getBytes());
      out.flush();
      assertThat(json.readTree(reader.readLine()).path("code").asText())
          .isEqualTo("event_conflict");
      request.put("event_id", UUID.randomUUID().toString());
      request.put("humidity", 101);
      out.write((json.writeValueAsString(request) + "\n").getBytes());
      out.flush();
      assertThat(json.readTree(reader.readLine()).path("code").asText())
          .isEqualTo("invalid_observation");
      request.put("humidity", 50);
      request.put("ward_id", "missing");
      out.write((json.writeValueAsString(request) + "\n").getBytes());
      out.flush();
      assertThat(json.readTree(reader.readLine()).path("code").asText()).isEqualTo("invalid_ward");
      var current = body(http.getForEntity("/api/v1/wards/00004/weather/current", String.class));
      assertThat(current.path("data").path("observation").path("source").asText())
          .isEqualTo("simulator");
      assertThat(
              body(http.getForEntity("/api/v1/wards/00004/weather/history", String.class))
                  .path("data")
                  .path("count")
                  .asInt())
          .isGreaterThan(0);
    } finally {
      ws.sendClose(WebSocket.NORMAL_CLOSURE, "done").get(2, TimeUnit.SECONDS);
    }
  }

  @Test
  void tcpBoundsFrameSize() throws Exception {
    try (Socket socket = new Socket("127.0.0.1", tcp.boundPort())) {
      socket.setSoTimeout(5000);
      socket.getOutputStream().write("x".repeat(8193).getBytes());
      socket.getOutputStream().flush();
      var reply = new BufferedReader(new InputStreamReader(socket.getInputStream())).readLine();
      assertThat(json.readTree(reply).path("code").asText()).isEqualTo("frame_limit_or_timeout");
    }
  }

  @Test
  void matchesFastApiSuccessEnvelopeAndQueryValidation() throws Exception {
    var response = body(http.getForEntity("/api/v1/provinces", String.class));
    assertThat(response.properties())
        .extracting(java.util.Map.Entry::getKey)
        .containsExactlyInAnyOrder("success", "data");
    for (String path :
        List.of(
            "/provinces?page=0",
            "/wards?page_size=101",
            "/wards/unknown/weather/history?page_size=0",
            "/wards?province_id=",
            "/provinces?q=" + "a".repeat(151))) {
      var invalid = http.getForEntity("/api/v1" + path, String.class);
      assertThat(invalid.getStatusCode().value()).as(path).isEqualTo(422);
      assertThat(body(invalid).path("error").path("code").asText()).isEqualTo("validation_error");
    }
    var publicHeaders = new org.springframework.http.HttpHeaders();
    publicHeaders.setBearerAuth("invalid-token");
    assertThat(
            http.exchange(
                    "/api/v1/provinces",
                    HttpMethod.GET,
                    new HttpEntity<>(publicHeaders),
                    String.class)
                .getStatusCode()
                .value())
        .isEqualTo(200);
    var cors = new org.springframework.http.HttpHeaders();
    cors.set("Origin", "http://localhost:5173");
    cors.set("Access-Control-Request-Method", "PATCH");
    cors.set("Access-Control-Request-Headers", "authorization,content-type");
    assertThat(
            http.exchange(
                    "/api/v1/users/me/address",
                    HttpMethod.OPTIONS,
                    new HttpEntity<>(cors),
                    String.class)
                .getHeaders()
                .getFirst("Access-Control-Allow-Origin"))
        .isEqualTo("http://localhost:5173");
  }

  String registerToken(String email) throws Exception {
    return body(http.postForEntity(
            "/api/v1/auth/register",
            Map.of("name", "Person", "email", email, "password", "Strong-test-password-123"),
            String.class))
        .path("data")
        .path("access_token")
        .asText();
  }

  @Test
  void addressesStayIsolatedValidateBeforeSavingAndCanBeDeleted() throws Exception {
    String first = registerToken(UUID.randomUUID() + "@example.com"),
        second = registerToken(UUID.randomUUID() + "@example.com");
    String path = "/api/v1/users/me/address";
    assertThat(
            http.exchange(
                    path,
                    HttpMethod.PATCH,
                    authorized(first, Map.of("ward_id", " 00004 ", "address_text", "  Nhà A  ")),
                    String.class)
                .getStatusCode()
                .value())
        .isEqualTo(200);
    var saved =
        body(http.exchange(path, HttpMethod.GET, authorized(first, null), String.class))
            .path("data");
    assertThat(saved.path("address_text").asText()).isEqualTo("Nhà A");
    assertThat(
            body(http.exchange(path, HttpMethod.GET, authorized(second, null), String.class))
                .path("data")
                .path("ward")
                .isNull())
        .isTrue();
    assertThat(
            http.exchange(
                    path,
                    HttpMethod.PATCH,
                    authorized(first, Map.of("ward_id", "missing")),
                    String.class)
                .getStatusCode()
                .value())
        .isEqualTo(404);
    assertThat(
            http.exchange(
                    path,
                    HttpMethod.PATCH,
                    authorized(first, Map.of("ward_id", "00008", "user_id", "other")),
                    String.class)
                .getStatusCode()
                .value())
        .isEqualTo(422);
    assertThat(
            body(http.exchange(path, HttpMethod.GET, authorized(first, null), String.class))
                .path("data"))
        .isEqualTo(saved);
    var removed =
        body(http.exchange(path, HttpMethod.DELETE, authorized(first, null), String.class))
            .path("data");
    assertThat(removed.path("ward").isNull()).isTrue();
    assertThat(removed.path("address_text").isNull()).isTrue();
  }

  @Test
  void inactiveProvinceDisablesWardAndWrongMethodsAreClientErrors() {
    var p = new Province();
    p.setId("99");
    p.setName("Inactive");
    p.setDatasetVersion("test");
    p.setActive(false);
    provinces.save(p);
    var w = new Ward();
    w.setId("99999");
    w.setName("Inactive parent");
    w.setDatasetVersion("test");
    w.setProvinceId("99");
    wards.save(w);
    for (String suffix :
        List.of("", "/weather/current", "/weather/history", "/weather/forecast", "/weather/future"))
      assertThat(
              http.getForEntity("/api/v1/wards/99999" + suffix, String.class)
                  .getStatusCode()
                  .value())
          .isEqualTo(404);
    assertThat(
            http.postForEntity("/api/v1/provinces", Map.of(), String.class).getStatusCode().value())
        .isEqualTo(405);
  }

  @Test
  void legacyDocumentationAliasesAndJwtSecurityArePresent() throws Exception {
    assertThat(http.getForEntity("/redoc", String.class).getStatusCode().value()).isEqualTo(200);
    var schema = body(http.getForEntity("/openapi.json", String.class));
    assertThat(schema.path("openapi").asText()).startsWith("3.");
    assertThat(schema.path("paths").path("/api/v1/auth/me").path("get").path("security").isArray())
        .isTrue();
    assertThat(schema.path("paths").path("/api/v1/provinces").path("get").has("security"))
        .isFalse();
  }
}
