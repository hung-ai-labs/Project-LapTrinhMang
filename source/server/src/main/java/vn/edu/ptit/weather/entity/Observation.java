package vn.edu.ptit.weather.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@Entity
@Table(name = "observations")
public class Observation extends BaseEntity {
  @Id
  @Column(length = 36)
  private String id;

  @Column(nullable = false, length = 20)
  private String wardId;

  @Column(nullable = false)
  private double temperature;

  @Column(nullable = false)
  private double humidity;

  @Column(nullable = false)
  private double windSpeed;

  @Column(nullable = false)
  private double rainfall;

  @Column(nullable = false, length = 32)
  private String source;

  @Column(nullable = false)
  private java.time.Instant observedAt;
}
