package vn.edu.ptit.weather.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.*;
import java.util.*;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import vn.edu.ptit.weather.dto.ChatDto.*;
import vn.edu.ptit.weather.entity.*;
import vn.edu.ptit.weather.exception.ApiException;
import vn.edu.ptit.weather.repository.*;

@Service
@RequiredArgsConstructor
public class ChatService {
  /** A function call plus its answer costs one extra round-trip; cap them to bound latency. */
  private static final int MAX_TOOL_ROUNDS = 3;

  private static final String SYSTEM_INSTRUCTION =
      """
      Bạn là trợ lý của Weather Stream, một ứng dụng thời tiết Việt Nam.
      Trả lời bằng tiếng Việt, ngắn gọn, thân thiện.

      Quy tắc bắt buộc:
      - Mọi số liệu thời tiết phải lấy từ tool, tuyệt đối không tự bịa hay ước lượng.
      - Cần biết thời tiết một nơi thì gọi find_ward trước để lấy ward_id, rồi gọi tool thời tiết.
      - Câu hỏi về nghiên cứu, mô hình, dữ liệu hay báo cáo của dự án thì gọi search_documents.
      - Nếu search_documents không trả về đoạn nào liên quan, hãy nói rõ là tài liệu
        của dự án không đề cập, không được suy đoán.
      - Đơn vị: nhiệt độ °C, độ ẩm %, gió km/h, mưa mm/h. Giờ hiển thị theo giờ Việt Nam.
      """;

  private final ChatConversationRepository conversations;
  private final ChatMessageRepository messages;
  private final GeminiClient gemini;
  private final ChatRateLimiter rateLimiter;
  private final ObjectMapper json;
  private final List<ChatTool> tools;

  @Value("${weather.chat-history-turns}")
  private int historyTurns;

  /** Streaming callbacks, so the orchestration stays testable without an HTTP response. */
  public interface ChatSink {
    void delta(String text);

    void tool(String name, String status);

    void citations(List<Citation> citations);
  }

  // --- Conversation management ---

  public List<ConversationResponse> list(User user) {
    return conversations.findByUserIdOrderByUpdatedAtDescIdDesc(user.getId()).stream()
        .map(ConversationResponse::from)
        .toList();
  }

  public List<MessageResponse> history(User user, String conversationId) {
    ChatConversation conversation = require(user, conversationId);
    return messages.findByConversationIdOrderByCreatedAtAscIdAsc(conversation.getId()).stream()
        .map(
            message ->
                new MessageResponse(
                    message.getId(),
                    message.getRole(),
                    message.getContent(),
                    readCitations(message.getCitations()),
                    message.getCreatedAt()))
        .toList();
  }

  @Transactional
  public ConversationResponse rename(User user, String conversationId, String title) {
    ChatConversation conversation = require(user, conversationId);
    conversation.setTitle(title);
    return ConversationResponse.from(conversations.save(conversation));
  }

  @Transactional
  public void delete(User user, String conversationId) {
    ChatConversation conversation = require(user, conversationId);
    messages.deleteByConversationId(conversation.getId());
    conversations.delete(conversation);
  }

  private ChatConversation require(User user, String conversationId) {
    return conversations
        .findByIdAndUserId(conversationId, user.getId())
        .orElseThrow(() -> new ApiException(404, "Không tìm thấy đoạn chat."));
  }

  // --- Asking ---

  /** Runs one question to completion, pushing partial output into {@code sink} as it arrives. */
  public DoneEvent ask(User user, AskRequest request, ChatSink sink) {
    gemini.requireConfigured();
    rateLimiter.check(user.getId());
    ChatConversation conversation =
        request.conversationId() == null || request.conversationId().isBlank()
            ? create(user, request.message())
            : require(user, request.conversationId());

    ArrayNode contents = json.createArrayNode();
    for (ChatMessage past : previousTurns(conversation.getId()))
      contents.add(content(past.getRole(), past.getContent()));
    contents.add(content(ChatMessage.ROLE_USER, request.message()));
    save(conversation.getId(), ChatMessage.ROLE_USER, request.message(), List.of());

    Completion completion = complete(contents, SYSTEM_INSTRUCTION, sink);
    String answer =
        completion.answer().isBlank()
            ? "Xin lỗi, tôi chưa tạo được câu trả lời cho câu hỏi này."
            : completion.answer();
    ChatMessage saved =
        save(conversation.getId(), ChatMessage.ROLE_MODEL, answer, completion.citations());
    touch(conversation);
    return new DoneEvent(conversation.getId(), saved.getId(), conversation.getTitle());
  }

  /** Final text of one exchange plus every source the tools leaned on. */
  public record Completion(String answer, List<Citation> citations) {}

  /**
   * Drives the two-phase tool loop to completion without persisting anything. Shared by the chat
   * endpoint and by the weather advisory, so both get identical tool behaviour.
   */
  public Completion complete(ArrayNode contents, String systemInstruction, ChatSink sink) {
    ArrayNode declarations = declarations();
    var answer = new StringBuilder();
    var citations = new LinkedHashSet<Citation>();

    for (int round = 0; round <= MAX_TOOL_ROUNDS; round++) {
      // The final round withholds the tools so the model has to produce prose and cannot loop.
      boolean last = round == MAX_TOOL_ROUNDS;
      GeminiClient.Turn turn =
          gemini.streamTurn(
              contents,
              last ? null : declarations,
              systemInstruction,
              delta -> {
                answer.append(delta);
                sink.delta(delta);
              });
      if (turn.calls().isEmpty()) break;

      // Replay the model's own call, then answer it: Gemini requires both halves in order.
      ArrayNode callParts = json.createArrayNode();
      for (GeminiClient.ToolCall call : turn.calls()) {
        ObjectNode part = json.createObjectNode();
        part.set(
            "functionCall",
            json.createObjectNode().put("name", call.name()).set("args", call.args()));
        // Gemini 3 rejects the follow-up turn if the thought signature is not echoed back.
        if (call.thoughtSignature() != null)
          part.put("thoughtSignature", call.thoughtSignature());
        callParts.add(part);
      }
      contents.add(json.createObjectNode().put("role", "model").set("parts", callParts));

      ArrayNode responseParts = json.createArrayNode();
      for (GeminiClient.ToolCall call : turn.calls()) {
        sink.tool(call.name(), "running");
        ChatTool.Result result = invoke(call);
        citations.addAll(result.citations());
        responseParts.add(
            json.createObjectNode()
                .set(
                    "functionResponse",
                    json.createObjectNode()
                        .put("name", call.name())
                        .set(
                            "response",
                            json.createObjectNode().set("result", result.payload()))));
      }
      contents.add(json.createObjectNode().put("role", "user").set("parts", responseParts));
    }

    var sources = List.copyOf(citations);
    if (!sources.isEmpty()) sink.citations(sources);
    return new Completion(answer.toString(), sources);
  }

  /** Lets callers that do not stream (the advisory endpoint) ignore partial output. */
  public static final ChatSink SILENT =
      new ChatSink() {
        @Override
        public void delta(String text) {}

        @Override
        public void tool(String name, String status) {}

        @Override
        public void citations(List<Citation> citations) {}
      };

  /** Builds a single user turn for callers that do not have a stored conversation. */
  public ArrayNode singleTurn(String prompt) {
    return json.createArrayNode().add(content(ChatMessage.ROLE_USER, prompt));
  }

  /** Never lets a broken tool kill the turn: the model is told what failed and can recover. */
  private ChatTool.Result invoke(GeminiClient.ToolCall call) {
    ChatTool tool =
        tools.stream().filter(candidate -> candidate.name().equals(call.name())).findFirst().orElse(null);
    if (tool == null)
      return ChatTool.Result.of(json.createObjectNode().put("error", "Tool không tồn tại."));
    try {
      return tool.execute(call.args());
    } catch (ApiException e) {
      return ChatTool.Result.of(json.createObjectNode().put("error", e.getMessage()));
    } catch (RuntimeException e) {
      org.slf4j.LoggerFactory.getLogger(getClass()).warn("Tool {} failed", call.name(), e);
      return ChatTool.Result.of(
          json.createObjectNode().put("error", "Không lấy được dữ liệu cho " + call.name() + "."));
    }
  }

  private ArrayNode declarations() {
    ArrayNode functions = json.createArrayNode();
    for (ChatTool tool : tools) functions.add(tool.declaration(json));
    if (functions.isEmpty()) return null;
    return json.createArrayNode().add(json.createObjectNode().set("functionDeclarations", functions));
  }

  private List<ChatMessage> previousTurns(String conversationId) {
    var recent =
        messages.findByConversationIdOrderByCreatedAtDescIdDesc(
            conversationId, PageRequest.of(0, Math.max(historyTurns, 1) * 2));
    var ordered = new ArrayList<>(recent);
    Collections.reverse(ordered);
    return ordered;
  }

  private ObjectNode content(String role, String text) {
    return json.createObjectNode()
        .put("role", role)
        .set("parts", json.createArrayNode().add(json.createObjectNode().put("text", text)));
  }

  @Transactional
  ChatConversation create(User user, String firstMessage) {
    ChatConversation conversation = new ChatConversation();
    conversation.setId(UUID.randomUUID().toString());
    conversation.setUserId(user.getId());
    conversation.setTitle(title(firstMessage));
    return conversations.save(conversation);
  }

  private static String title(String message) {
    String trimmed = message.strip().replaceAll("\\s+", " ");
    if (trimmed.length() <= 60) return trimmed.isEmpty() ? "Đoạn chat mới" : trimmed;
    return trimmed.substring(0, 57) + "...";
  }

  @Transactional
  ChatMessage save(String conversationId, String role, String content, Collection<Citation> sources) {
    ChatMessage message = new ChatMessage();
    message.setId(UUID.randomUUID().toString());
    message.setConversationId(conversationId);
    message.setRole(role);
    message.setContent(content);
    message.setCitations(writeCitations(sources));
    return messages.save(message);
  }

  @Transactional
  void touch(ChatConversation conversation) {
    conversation.setUpdatedAt(java.time.Instant.now());
    conversations.save(conversation);
  }

  private String writeCitations(Collection<Citation> sources) {
    if (sources == null || sources.isEmpty()) return null;
    try {
      return json.writeValueAsString(sources);
    } catch (JsonProcessingException e) {
      return null;
    }
  }

  private List<Citation> readCitations(String stored) {
    if (stored == null || stored.isBlank()) return List.of();
    try {
      return List.of(json.readValue(stored, Citation[].class));
    } catch (JsonProcessingException e) {
      return List.of();
    }
  }
}
