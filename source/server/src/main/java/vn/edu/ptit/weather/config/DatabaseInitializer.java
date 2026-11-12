package vn.edu.ptit.weather.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import javax.sql.DataSource;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.*;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.transaction.support.TransactionTemplate;

@Configuration
@Profile("init-db")
public class DatabaseInitializer {
  @Bean
  ApplicationRunner initializeDatabase(
      DataSource source, ObjectMapper json, ConfigurableApplicationContext context) {
    return args -> {
      byte[] bytes;
      try (var stream = new ClassPathResource("snapshot.json").getInputStream()) {
        bytes =
            new String(stream.readAllBytes(), StandardCharsets.UTF_8)
                .replace("\r\n", "\n")
                .getBytes(StandardCharsets.UTF_8);
      }
      com.fasterxml.jackson.databind.JsonNode manifest;
      try (var stream = new ClassPathResource("manifest.json").getInputStream()) {
        manifest = json.readTree(stream);
      }
      String hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
      if (!hash.equals(manifest.path("snapshot_sha256").asText()))
        throw new IllegalStateException("Administrative snapshot checksum mismatch");
      var data = json.readTree(bytes);
      if (data.path("provinces").size() != manifest.path("counts").path("provinces").asInt()
          || data.path("wards").size() != manifest.path("counts").path("wards").asInt())
        throw new IllegalStateException("Administrative snapshot count mismatch");
      vn.edu.ptit.weather.service.AdministrativeCatalogService.validate(data, manifest, bytes);
      String version = data.path("dataset_version").asText();
      // Explicit opt-in only; all DDL and inserts commit together, without replacing existing rows.
      new TransactionTemplate(new DataSourceTransactionManager(source))
          .executeWithoutResult(
              transaction -> {
                new ResourceDatabasePopulator(new ClassPathResource("schema.sql")).execute(source);
                JdbcTemplate db = new JdbcTemplate(source);
                db.queryForList("SELECT ward_id FROM observations LIMIT 1");
                var provinces = new java.util.ArrayList<Object[]>();
                for (var p : data.path("provinces"))
                  provinces.add(
                      new Object[] {p.path("id").asText(), p.path("name").asText(), version});
                db.batchUpdate(
                    "INSERT INTO provinces(id,name,dataset_version,is_active) VALUES (?,?,?,true) ON CONFLICT (id) DO NOTHING",
                    provinces);
                var wards = new java.util.ArrayList<Object[]>();
                for (var w : data.path("wards"))
                  wards.add(
                      new Object[] {
                        w.path("id").asText(),
                        w.path("province_id").asText(),
                        w.path("name").asText(),
                        w.path("administrative_type").asText(null),
                        vn.edu.ptit.weather.service.AdministrativeCatalogService.coordinate(
                            w.get("latitude"), -90, 90),
                        vn.edu.ptit.weather.service.AdministrativeCatalogService.coordinate(
                            w.get("longitude"), -180, 180),
                        version
                      });
                db.batchUpdate(
                    "INSERT INTO wards(id,province_id,name,administrative_type,latitude,longitude,dataset_version,is_active) VALUES (?,?,?,?,?,?,?,true) ON CONFLICT (id) DO NOTHING",
                    wards);
              });
      System.out.println("Khởi tạo database hoàn tất.");
      context.close();
    };
  }
}
