package vn.edu.ptit.weather.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@Entity
@Table(name = "chat_messages")
public class ChatMessage extends BaseEntity {
  /** Gemini only accepts "user" and "model" as content roles. */
  public static final String ROLE_USER = "user";

  public static final String ROLE_MODEL = "model";

  @Id
  @Column(length = 36)
  private String id;

  @Column(nullable = false, length = 36)
  private String conversationId;

  @Column(nullable = false, length = 16)
  private String role;

  @Column(nullable = false, columnDefinition = "text")
  private String content;

  /** JSON array of retrieved sources, kept so the UI can re-render past answers. */
  @Column(columnDefinition = "text")
  private String citations;
}
