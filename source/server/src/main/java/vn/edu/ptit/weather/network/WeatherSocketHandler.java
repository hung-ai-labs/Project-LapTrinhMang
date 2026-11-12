package vn.edu.ptit.weather.network;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.*;
import org.springframework.web.socket.*;
import org.springframework.web.socket.adapter.standard.StandardWebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import vn.edu.ptit.weather.exception.ApiException;
import vn.edu.ptit.weather.service.GeographyService;
import vn.edu.ptit.weather.service.ObservationService.StoredEvent;

@Component
@RequiredArgsConstructor
public class WeatherSocketHandler extends TextWebSocketHandler {
  private final ObjectMapper json;
  private final GeographyService geography;

  @Value("${weather.source}")
  private String source;

  private final Map<String, Client> clients = new ConcurrentHashMap<>();

  /** Each subscriber keeps only the latest 32 pending events, without blocking TCP ACKs. */
  private final class Client {
    final String wardId;
    final StandardWebSocketSession socket;
    final ArrayDeque<String> queue = new ArrayDeque<>();
    boolean sending;

    Client(String wardId, StandardWebSocketSession socket) {
      this.wardId = wardId;
      this.socket = socket;
    }

    synchronized void offer(String message) {
      if (!socket.isOpen()) {
        clients.remove(socket.getId());
        return;
      }
      if (queue.size() == 32) queue.removeFirst();
      queue.addLast(message);
      if (!sending) {
        sending = true;
        sendNext();
      }
    }

    private synchronized void sendNext() {
      String message = queue.pollFirst();
      if (message == null) {
        sending = false;
        return;
      }
      try {
        socket
            .getNativeSession()
            .getAsyncRemote()
            .sendText(
                message,
                result -> {
                  if (result.isOK()) sendNext();
                  else fail();
                });
      } catch (Exception e) {
        fail();
      }
    }

    private synchronized void fail() {
      queue.clear();
      sending = false;
      clients.remove(socket.getId());
      try {
        socket.close(CloseStatus.SESSION_NOT_RELIABLE);
      } catch (Exception ignored) {
      }
    }
  }

  @Override
  public void afterConnectionEstablished(WebSocketSession session) throws Exception {
    String[] path = session.getUri().getPath().split("/");
    String wardId = path[path.length - 2];
    try {
      geography.ward(wardId);
    } catch (ApiException e) {
      session.close(CloseStatus.POLICY_VIOLATION);
      return;
    } catch (org.springframework.dao.DataAccessException
        | org.springframework.transaction.TransactionException e) {
      /* Keep heartbeat available during a database outage. */
    }
    if (!(session instanceof StandardWebSocketSession socket)) {
      session.close(CloseStatus.SERVER_ERROR);
      return;
    }
    socket.getNativeSession().getAsyncRemote().setSendTimeout(10000);
    clients.put(socket.getId(), new Client(wardId, socket));
  }

  @Override
  public void afterConnectionClosed(WebSocketSession socket, CloseStatus status) {
    clients.remove(socket.getId());
  }

  @Override
  public void handleTransportError(WebSocketSession socket, Throwable error) throws Exception {
    clients.remove(socket.getId());
    socket.close(CloseStatus.SERVER_ERROR);
  }

  @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
  public void stored(StoredEvent event) {
    if (source.equals(event.event().observation().source()))
      broadcast(event.wardId(), event.event());
  }

  @Scheduled(fixedDelayString = "${weather.heartbeat-millis:15000}")
  public void heartbeat() {
    broadcast(null, Map.of("type", "heartbeat", "at", Instant.now()));
  }

  private void broadcast(String wardId, Object value) {
    final String message;
    try {
      message = json.writeValueAsString(value);
    } catch (java.io.IOException e) {
      throw new IllegalStateException(e);
    }
    for (Client client : clients.values())
      if (wardId == null || wardId.equals(client.wardId)) client.offer(message);
  }
}
