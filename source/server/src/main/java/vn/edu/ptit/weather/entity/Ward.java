package vn.edu.ptit.weather.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@Entity
@Table(name = "wards")
public class Ward extends BaseEntity {
  @Id
  @Column(length = 20)
  private String id;

  @Column(nullable = false, length = 20)
  private String provinceId;

  @Column(nullable = false, length = 150)
  private String name;

  @Column(length = 32)
  private String administrativeType;

  @Column(precision = 8, scale = 5)
  private java.math.BigDecimal latitude;

  @Column(precision = 8, scale = 5)
  private java.math.BigDecimal longitude;

  @Column(nullable = false, length = 64)
  private String datasetVersion;

  @Column(nullable = false)
  private boolean isActive = true;
}
