package vn.edu.ptit.weather.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import vn.edu.ptit.weather.entity.User;

public interface UserRepository extends JpaRepository<User, String> {
  java.util.Optional<User> findByEmail(String email);

  @org.springframework.data.jpa.repository.Modifying
  @org.springframework.data.jpa.repository.Query(
      "update User u set u.tokenVersion = u.tokenVersion + 1 where u.id = :id")
  void revokeTokens(@org.springframework.data.repository.query.Param("id") String id);
}
