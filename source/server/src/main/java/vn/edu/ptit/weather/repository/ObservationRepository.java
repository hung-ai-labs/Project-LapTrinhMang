package vn.edu.ptit.weather.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import vn.edu.ptit.weather.entity.Observation;

public interface ObservationRepository extends JpaRepository<Observation, String> {
  java.util.Optional<Observation> findFirstByWardIdAndSourceOrderByObservedAtDescIdDesc(
      String wardId, String source);

  org.springframework.data.domain.Page<Observation>
      findByWardIdAndSourceOrderByObservedAtDescIdDesc(
          String wardId, String source, org.springframework.data.domain.Pageable page);
}
