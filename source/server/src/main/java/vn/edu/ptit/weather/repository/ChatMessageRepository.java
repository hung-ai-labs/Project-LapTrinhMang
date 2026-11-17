package vn.edu.ptit.weather.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import vn.edu.ptit.weather.entity.ChatMessage;

public interface ChatMessageRepository extends JpaRepository<ChatMessage, String> {
  java.util.List<ChatMessage> findByConversationIdOrderByCreatedAtAscIdAsc(String conversationId);

  /** Newest first so the caller can keep only the last N turns, then reverse them. */
  java.util.List<ChatMessage> findByConversationIdOrderByCreatedAtDescIdDesc(
      String conversationId, org.springframework.data.domain.Pageable page);

  void deleteByConversationId(String conversationId);
}
