package vn.edu.ptit.weather.dto;

import jakarta.validation.constraints.*;
import java.time.Instant;
import java.util.List;
import vn.edu.ptit.weather.entity.ChatConversation;

public final class ChatDto {
  private ChatDto() {}

  /** A new message. Omit conversationId to start a new thread. */
  public record AskRequest(
      @Size(max = 36) String conversationId, @NotBlank @Size(max = 4000) String message) {
    public AskRequest {
      if (message != null) message = message.strip();
    }
  }

  public record ConversationResponse(String id, String title, Instant createdAt, Instant updatedAt) {
    public static ConversationResponse from(ChatConversation conversation) {
      return new ConversationResponse(
          conversation.getId(),
          conversation.getTitle(),
          conversation.getCreatedAt(),
          conversation.getUpdatedAt());
    }
  }

  public record MessageResponse(
      String id, String role, String content, List<Citation> citations, Instant createdAt) {}

  /** Where a retrieved passage came from, so answers stay traceable to the repository. */
  public record Citation(String sourcePath, String heading, double score) {}

  public record RenameRequest(@NotBlank @Size(max = 200) String title) {
    public RenameRequest {
      if (title != null) title = title.strip();
    }
  }

  // --- Server-sent event payloads ---

  public record DeltaEvent(String text) {}

  public record ToolEvent(String name, String status) {}

  public record CitationsEvent(List<Citation> citations) {}

  public record DoneEvent(String conversationId, String messageId, String title) {}

  public record ErrorEvent(String code, String message) {}
}
