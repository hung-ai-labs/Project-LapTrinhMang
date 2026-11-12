package vn.edu.ptit.weather.config;

import com.zaxxer.hikari.*;
import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import javax.sql.DataSource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.*;

@Configuration
public class DatabaseConfig {
  @Bean
  DataSource dataSource(
      @Value("${weather.database-url}") String raw,
      @Value("${weather.database-user:}") String username,
      @Value("${weather.database-password:}") String password) {
    var config = new HikariConfig();
    String url = raw;
    if (raw.startsWith("postgresql:") || raw.startsWith("postgresql+psycopg:")) {
      URI uri = URI.create(raw.replace("postgresql+psycopg:", "postgresql:"));
      if (uri.getRawUserInfo() != null) {
        String[] credentials = uri.getRawUserInfo().split(":", 2);
        username = URLDecoder.decode(credentials[0], StandardCharsets.UTF_8);
        password =
            credentials.length > 1 ? URLDecoder.decode(credentials[1], StandardCharsets.UTF_8) : "";
      }
      // JDBC uses channelBinding (camel case), unlike libpq's channel_binding.
      String query =
          uri.getRawQuery() == null
              ? ""
              : uri.getRawQuery().replace("channel_binding=", "channelBinding=");
      url =
          "jdbc:postgresql://"
              + uri.getHost()
              + (uri.getPort() < 0 ? "" : ":" + uri.getPort())
              + uri.getRawPath()
              + (query.isEmpty() ? "" : "?" + query);
    }
    if (url.startsWith("jdbc:postgresql:")) {
      config.addDataSourceProperty("connectTimeout", "5");
      config.addDataSourceProperty("socketTimeout", "20");
      config.addDataSourceProperty("tcpKeepAlive", "true");
    }
    config.setJdbcUrl(url);
    config.setUsername(username);
    config.setPassword(password);
    config.setMaximumPoolSize(10);
    config.setMinimumIdle(0);
    config.setConnectionTimeout(5000);
    config.setInitializationFailTimeout(-1);
    return new HikariDataSource(config);
  }
}
