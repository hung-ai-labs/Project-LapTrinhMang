package vn.edu.ptit.weather.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import vn.edu.ptit.weather.dto.WeatherDto.ObservationRequest;

@Service
@RequiredArgsConstructor
public class IngestionGateway {
  private final ObservationService observations;

  public synchronized boolean ingest(ObservationRequest request) {
    return observations.ingest(request);
  }
}
