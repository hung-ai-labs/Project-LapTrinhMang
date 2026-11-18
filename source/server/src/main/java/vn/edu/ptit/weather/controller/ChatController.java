package vn.edu.ptit.weather.controller;

import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import jakarta.validation.Valid;
import java.io.IOException;
import java.util.List;
import java.util.concurrent.*;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import vn.edu.ptit.weather.dto.ApiResponse;
import vn.edu.ptit.weather.dto.ChatDto.*;
import vn.edu.ptit.weather.exception.ApiException;
import vn.edu.ptit.weather.service.AuthService;
import vn.edu.ptit.weather.service.ChatService;

/**
 * Chat over Server-Sent Events. SSE is a better fit than WebSocket here: the stream is one-way,
 * rides ordinary HTTP, and the browser reconnects on its own.
 */
@SecurityRequirement(name = "bearerAuth")
@RestController
@RequestMapping("/api/v1/chat")
@RequiredArgsConstructor
public class ChatController {
  /** Answers hold a worker for their whole lifetime, so the pool is bounded and queued. */
  private static final ExecutorService WORKERS =
      new ThreadPoolExecutor(
          2,
          8,
          60,
          TimeUnit.SECONDS,
          new ArrayBlockingQueue<>(32),
          runnable -> {
            Thread thread = new Thread(runnable, "chat-sse");
            thread.setDaemon(true);
            return thread;
          },
          new ThreadPoolExecutor.AbortPolicy());

  /**
   * Must outlast the worst case inside ChatService: up to four model turns, each of which may burn
   * its own retry budget sweeping saturated models. Timing out here instead would drop the client
   * with nothing, after it had already waited.
   */
  private static final long STREAM_TIMEOUT_MS = 300_000;

  private final ChatService chat;
  private final AuthService auth;

  @GetMapping("/conversations")
  public ApiResponse<List<ConversationResponse>> conversations() {
    return ApiResponse.ok(chat.list(auth.currentUser()));
  }

  @GetMapping("/conversations/{id}/messages")
  public ApiResponse<List<MessageResponse>> messages(@PathVariable String id) {
    return ApiResponse.ok(chat.history(auth.currentUser(), id));
  }

  @PatchMapping("/conversations/{id}")
  public ApiResponse<ConversationResponse> rename(
      @PathVariable String id, @Valid @RequestBody RenameRequest request) {
    return ApiResponse.ok(chat.rename(auth.currentUser(), id, request.title()));
  }

  @DeleteMapping("/conversations/{id}")
  public ApiResponse<Void> delete(@PathVariable String id) {
    chat.delete(auth.currentUser(), id);
    return ApiResponse.ok(null);
  }

  @PostMapping(value = "/ask", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
  public SseEmitter ask(@Valid @RequestBody AskRequest request) {
    // Resolve the user on the request thread: SecurityContext does not follow us into the pool.
    var user = auth.currentUser();
    var emitter = new SseEmitter(STREAM_TIMEOUT_MS);
    // Without these the container raises AsyncRequestTimeoutException as an unhandled failure.
    emitter.onTimeout(emitter::complete);
    emitter.onError(error -> emitter.complete());
    try {
      WORKERS.execute(() -> run(user, request, emitter));
    } catch (RejectedExecutionException e) {
      throw new ApiException(503, "Chatbot đang bận, vui lòng thử lại sau.");
    }
    return emitter;
  }

  private void run(
      vn.edu.ptit.weather.entity.User user, AskRequest request, SseEmitter emitter) {
    try {
      DoneEvent done =
          chat.ask(
              user,
              request,
              new ChatService.ChatSink() {
                @Override
                public void delta(String text) {
                  send(emitter, "delta", new DeltaEvent(text));
                }

                @Override
                public void tool(String name, String status) {
                  send(emitter, "tool", new ToolEvent(name, status));
                }

                @Override
                public void citations(List<Citation> citations) {
                  send(emitter, "citations", new CitationsEvent(citations));
                }
              });
      send(emitter, "done", done);
      finish(emitter);
    } catch (ApiException e) {
      if (e.getStatus() != 499)
        trySend(emitter, "error", new ErrorEvent("http_" + e.getStatus(), e.getMessage()));
      finish(emitter);
    } catch (RuntimeException e) {
      org.slf4j.LoggerFactory.getLogger(getClass()).warn("Chat stream failed", e);
      trySend(emitter, "error", new ErrorEvent("http_500", "Chatbot gặp lỗi không mong muốn."));
      finish(emitter);
    }
  }

  private void trySend(SseEmitter emitter, String event, Object payload) {
    try {
      send(emitter, event, payload);
    } catch (RuntimeException ignored) {
      // The client is already gone; nothing left to report to.
    }
  }

  private void finish(SseEmitter emitter) {
    try {
      emitter.complete();
    } catch (RuntimeException ignored) {
      // Completing an already-closed stream is not an error worth surfacing.
    }
  }

  /** A disconnected client is normal, not an error: stop writing and let the worker unwind. */
  private void send(SseEmitter emitter, String event, Object payload) {
    try {
      emitter.send(SseEmitter.event().name(event).data(payload, MediaType.APPLICATION_JSON));
    } catch (IOException | IllegalStateException e) {
      throw new ApiException(499, "Client đã ngắt kết nối.");
    }
  }
}
