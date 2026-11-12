package vn.edu.ptit.weather.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import vn.edu.ptit.weather.entity.Province;

public interface ProvinceRepository extends JpaRepository<Province, String> {
  java.util.List<Province> findByIsActiveTrueOrderByNameAsc();
}
