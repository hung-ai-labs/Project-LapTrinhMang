package vn.edu.ptit.weather.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import vn.edu.ptit.weather.entity.ChatConversation;

public interface ChatConversationRepository extends JpaRepository<ChatConversation, String> {
  java.util.List<ChatConversation> findByUserIdOrderByUpdatedAtDescIdDesc(String userId);

  java.util.Optional<ChatConversation> findByIdAndUserId(String id, String userId);
}
