package vn.edu.ptit.weather.service;

import java.util.*;
import org.springframework.stereotype.Service;
import vn.edu.ptit.weather.dto.WeatherDto.*;

@Service
public class AlertService {
  public List<Alert> evaluate(ObservationResponse observation) {
    var alerts = new ArrayList<Alert>();
    if (observation.temperature() >= 35)
      alerts.add(new Alert("heat", "warning", "Nhiệt độ cao từ 35°C."));
    if (observation.rainfall() >= 20)
      alerts.add(new Alert("rain", "warning", "Mưa lớn từ 20 mm/giờ."));
    if (observation.windSpeed() >= 50)
      alerts.add(new Alert("wind", "warning", "Gió mạnh từ 50 km/giờ."));
    return alerts;
  }
}
