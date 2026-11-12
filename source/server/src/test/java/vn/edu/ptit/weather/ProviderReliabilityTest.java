package vn.edu.ptit.weather;

import static org.assertj.core.api.Assertions.*;

import com.fasterxml.jackson.databind.*;
import com.sun.net.httpserver.HttpServer;
import java.net.*;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.*;
import vn.edu.ptit.weather.exception.ApiException;
import vn.edu.ptit.weather.service.OpenMeteoClient;

class ProviderReliabilityTest {
  ObjectMapper json = new ObjectMapper();

  @Test
  void boundsTheEntireBodyReadEvenAfterHeadersArrive() throws Exception {
    HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    var executor = java.util.concurrent.Executors.newCachedThreadPool();
    server.setExecutor(executor);
    server.createContext(
        "/",
        exchange -> {
          exchange.sendResponseHeaders(200, 0);
          exchange.getResponseBody().write('{');
          exchange.getResponseBody().flush();
          try {
            Thread.sleep(3000);
          } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
          }
          exchange.close();
        });
    server.start();
    try {
      var client =
          new OpenMeteoClient(
              json, "http://127.0.0.1:" + server.getAddress().getPort(), Duration.ofMillis(200));
      long start = System.nanoTime();
      assertThatThrownBy(() -> client.fetch(21, 105, Map.of())).isInstanceOf(ApiException.class);
      assertThat(Duration.ofNanos(System.nanoTime() - start)).isLessThan(Duration.ofSeconds(2));
    } finally {
      server.stop(0);
      executor.shutdownNow();
    }
  }

  @Test
  void rejectsHttpErrorsOversizedResponsesAndMalformedJson() throws Exception {
    for (int status : List.of(429, 500, 503, 200)) {
      HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
      server.createContext(
          "/",
          exchange -> {
            byte[] bytes = (status == 200 ? "x".repeat(262145) : "error").getBytes();
            exchange.sendResponseHeaders(status, bytes.length);
            try (var out = exchange.getResponseBody()) {
              out.write(bytes);
            }
          });
      server.start();
      try {
        var client = new OpenMeteoClient(json, "http://127.0.0.1:" + server.getAddress().getPort());
        assertThatThrownBy(() -> client.fetch(21, 105, Map.of())).isInstanceOf(ApiException.class);
      } finally {
        server.stop(0);
      }
    }
  }
}
