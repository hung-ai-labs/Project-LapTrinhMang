package vn.edu.ptit.weather.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.*;
import org.springframework.core.io.ClassPathResource;
import vn.edu.ptit.weather.service.AdministrativeCatalogService;

@Configuration
@Profile("import-catalog")
public class CatalogImportConfig {
  @Bean
  ApplicationRunner importCatalog(
      ObjectMapper json,
      AdministrativeCatalogService service,
      ConfigurableApplicationContext context,
      @Value("${CATALOG_SNAPSHOT:}") String snapshot,
      @Value("${CATALOG_MANIFEST:}") String manifest,
      @Value("${CATALOG_APPLY:false}") boolean apply) {
    return args -> {
      byte[] bytes = read(snapshot, "snapshot.json");
      byte[] canonical =
          new String(bytes, java.nio.charset.StandardCharsets.UTF_8)
              .replace("\r\n", "\n")
              .getBytes(java.nio.charset.StandardCharsets.UTF_8);
      var data = json.readTree(canonical);
      var metadata = json.readTree(read(manifest, "manifest.json"));
      AdministrativeCatalogService.validate(data, metadata, canonical);
      if (apply) service.apply(data);
      System.out.println(
          "Catalog "
              + (apply ? "applied" : "dry-run")
              + ": "
              + data.path("provinces").size()
              + " provinces, "
              + data.path("wards").size()
              + " wards");
      context.close();
    };
  }

  private byte[] read(String path, String resource) throws java.io.IOException {
    if (!path.isBlank()) return Files.readAllBytes(Path.of(path));
    try (var input = new ClassPathResource(resource).getInputStream()) {
      return input.readAllBytes();
    }
  }
}
