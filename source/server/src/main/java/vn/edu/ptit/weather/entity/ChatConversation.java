package vn.edu.ptit.weather.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@Entity
@Table(name = "chat_conversations")
public class ChatConversation extends BaseEntity {
  @Id
  @Column(length = 36)
  private String id;

  @Column(nullable = false, length = 36)
  private String userId;

  @Column(nullable = false, length = 200)
  private String title;
}
