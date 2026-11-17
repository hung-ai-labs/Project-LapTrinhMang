package vn.edu.ptit.weather.config;

import org.springframework.boot.ApplicationRunner;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.*;
import vn.edu.ptit.weather.service.DocumentIndexService;

/**
 * Opt-in indexing pass, mirroring the init-db profile: never runs while serving traffic, builds the
 * retrieval index, then exits.
 */
@Configuration
@Profile("index-docs")
public class DocumentIndexConfig {
  @Bean
  ApplicationRunner indexDocuments(
      DocumentIndexService documents, ConfigurableApplicationContext context) {
    return args -> {
      var report = documents.reindex();
      System.out.println(
          "Index tài liệu hoàn tất: "
              + report.files()
              + " file, thêm "
              + report.created()
              + " đoạn, xóa "
              + report.removed()
              + " đoạn, tổng "
              + report.total()
              + " đoạn.");
      context.close();
    };
  }
}
