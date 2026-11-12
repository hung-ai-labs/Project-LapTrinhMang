package vn.edu.ptit.weather.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@Entity
@Table(name = "provinces")
public class Province extends BaseEntity {
  @Id
  @Column(length = 20)
  private String id;

  @Column(nullable = false, length = 150)
  private String name;

  @Column(nullable = false, length = 64)
  private String datasetVersion;

  @Column(nullable = false)
  private boolean isActive = true;
}
