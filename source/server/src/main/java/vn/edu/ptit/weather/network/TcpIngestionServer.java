package vn.edu.ptit.weather.network;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PreDestroy;
import jakarta.validation.Validator;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import vn.edu.ptit.weather.dto.WeatherDto.ObservationRequest;
import vn.edu.ptit.weather.exception.ApiException;
import vn.edu.ptit.weather.service.IngestionGateway;

@Component
public class TcpIngestionServer {
  private final ObjectMapper json;
  private final Validator validator;
  private final IngestionGateway ingestion;
  private final String host;
  private final int port;
  private final boolean enabled;
  private ServerSocket server;

  @Value("${weather.tcp-frame-timeout-millis:60000}")
  private long frameTimeoutMillis = 60000;

  private final ScheduledExecutorService writeTimeouts =
      Executors.newSingleThreadScheduledExecutor(
          task -> {
            Thread thread = new Thread(task, "weather-tcp-write-timeout");
            thread.setDaemon(true);
            return thread;
          });
  private final Set<Socket> clients = ConcurrentHashMap.newKeySet();
  private final ThreadPoolExecutor pool =
      new ThreadPoolExecutor(
          0,
          64,
          60,
          TimeUnit.SECONDS,
          new SynchronousQueue<>(),
          new ThreadPoolExecutor.AbortPolicy());

  public TcpIngestionServer(
      ObjectMapper json,
      Validator validator,
      IngestionGateway ingestion,
      @Value("${weather.tcp-host}") String host,
      @Value("${weather.tcp-port}") int port,
      @Value("${weather.enable-tcp}") boolean enabled) {
    this.json = json;
    this.validator = validator;
    this.ingestion = ingestion;
    this.host = host;
    this.port = port;
    this.enabled = enabled;
  }

  @EventListener(ApplicationReadyEvent.class)
  public void start() throws IOException {
    if (!enabled) return;
    server = new ServerSocket();
    server.bind(new InetSocketAddress(host, port));
    Thread thread = new Thread(this::accept, "weather-tcp-listener");
    thread.setDaemon(true);
    thread.start();
  }

  private void accept() {
    while (!server.isClosed()) {
      try {
        Socket socket = server.accept();
        socket.setSoTimeout((int) frameTimeoutMillis);
        clients.add(socket);
        try {
          pool.execute(() -> handle(socket));
        } catch (RejectedExecutionException e) {
          clients.remove(socket);
          socket.close();
        }
      } catch (IOException e) {
        if (!server.isClosed())
          org.slf4j.LoggerFactory.getLogger(getClass()).warn("TCP accept failed");
      }
    }
  }

  private void handle(Socket socket) {
    try (socket;
        var input = new BufferedInputStream(socket.getInputStream(), 8192);
        var output = socket.getOutputStream()) {
      while (true) {
        String frame;
        try {
          frame = frame(input, socket);
        } catch (SocketTimeoutException | FrameLimitException e) {
          reply(socket, output, Map.of("status", "error", "code", "frame_limit_or_timeout"));
          break;
        }
        if (frame == null) break;
        Map<String, Object> response;
        ObservationRequest value = null;
        try {
          value = json.readValue(frame, ObservationRequest.class);
          if (!validator.validate(value).isEmpty())
            throw new IllegalArgumentException("Invalid observation");
          boolean created = ingestion.ingest(value);
          response =
              Map.of("status", created ? "accepted" : "duplicate", "event_id", value.eventId());
        } catch (ApiException e) {
          String code =
              e.getStatus() == 409
                  ? "event_conflict"
                  : e.getStatus() == 404 ? "invalid_ward" : "storage_unavailable";
          response =
              Map.of(
                  "status",
                  "error",
                  "code",
                  code,
                  "event_id",
                  value == null ? "" : value.eventId());
        } catch (com.fasterxml.jackson.core.JsonProcessingException | IllegalArgumentException e) {
          response = Map.of("status", "error", "code", "invalid_observation");
        } catch (Exception e) {
          response = Map.of("status", "error", "code", "storage_unavailable");
        }
        reply(socket, output, response);
      }
    } catch (IOException ignored) {
    } finally {
      clients.remove(socket);
    }
  }

  private static class FrameLimitException extends IOException {}

  private String frame(InputStream input, Socket socket) throws IOException {
    long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(frameTimeoutMillis);
    var bytes = new ByteArrayOutputStream();
    int b;
    int configuredTimeout = -1;
    while (true) {
      long remaining = TimeUnit.NANOSECONDS.toMillis(deadline - System.nanoTime());
      if (remaining <= 0) throw new SocketTimeoutException();
      int timeout = (int) Math.max(1, remaining);
      if (timeout != configuredTimeout) {
        socket.setSoTimeout(timeout);
        configuredTimeout = timeout;
      }
      b = input.read();
      if (b == -1) break;
      if (b == '\n') return bytes.toString(StandardCharsets.UTF_8);
      bytes.write(b);
      if (bytes.size() > 8192) throw new FrameLimitException();
    }
    return bytes.size() == 0 ? null : bytes.toString(StandardCharsets.UTF_8);
  }

  private void reply(Socket socket, OutputStream output, Object response) throws IOException {
    var timeout =
        writeTimeouts.schedule(
            () -> {
              try {
                socket.close();
              } catch (IOException ignored) {
              }
            },
            10,
            TimeUnit.SECONDS);
    try {
      output.write(json.writeValueAsBytes(response));
      output.write('\n');
      output.flush();
    } finally {
      timeout.cancel(false);
    }
  }

  public int boundPort() {
    return server == null ? -1 : server.getLocalPort();
  }

  @PreDestroy
  public void stop() throws IOException {
    if (server != null) server.close();
    for (Socket client : clients) {
      try {
        client.close();
      } catch (IOException ignored) {
      }
    }
    pool.shutdownNow();
    writeTimeouts.shutdownNow();
  }
}
