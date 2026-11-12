package vn.edu.ptit.weather.repository;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import vn.edu.ptit.weather.entity.Ward;

public interface WardRepository extends JpaRepository<Ward, String> {
  @Query(
      "select w from Ward w, Province p where w.provinceId = p.id and w.isActive = true and p.isActive = true order by w.provinceId, w.name, w.id")
  List<Ward> findByIsActiveTrueOrderByNameAsc();

  @Query(
      "select w from Ward w, Province p where w.provinceId = p.id and w.isActive = true and p.isActive = true and p.id = :provinceId order by w.name, w.id")
  List<Ward> findByProvinceIdAndIsActiveTrueOrderByNameAsc(@Param("provinceId") String provinceId);

  @Query(
      "select w from Ward w, Province p where w.provinceId = p.id and w.isActive = true and p.isActive = true and w.id = :id")
  Optional<Ward> findActiveById(@Param("id") String id);
}
