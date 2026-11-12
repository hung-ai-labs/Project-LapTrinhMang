package vn.edu.ptit.weather.service;

import java.util.*;
import lombok.RequiredArgsConstructor;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import vn.edu.ptit.weather.dto.*;
import vn.edu.ptit.weather.dto.WeatherDto.*;
import vn.edu.ptit.weather.entity.Observation;
import vn.edu.ptit.weather.exception.ApiException;
import vn.edu.ptit.weather.repository.ObservationRepository;

@Service
@RequiredArgsConstructor
public class ObservationService {
  private final ObservationRepository observations;
  private final GeographyService geography;
  private final AlertService alerts;
  private final ApplicationEventPublisher publisher;

  public record StoredEvent(String wardId, WeatherEvent event) {}

  public WeatherEvent event(Observation observation) {
    var out = ObservationResponse.from(observation);
    return new WeatherEvent("weather.update", out, alerts.evaluate(out));
  }

  public Optional<Observation> latest(String wardId, String source) {
    return observations.findFirstByWardIdAndSourceOrderByObservedAtDescIdDesc(wardId, source);
  }

  public PageResponse<ObservationResponse> history(
      String wardId, String source, int page, int size) {
    PageResponse.validate(page, size);
    geography.ward(wardId);
    var records =
        observations.findByWardIdAndSourceOrderByObservedAtDescIdDesc(
            wardId, source, PageRequest.of(page - 1, size));
    return PageResponse.window(
        records.getTotalElements(),
        records.getContent().stream().map(ObservationResponse::from).toList(),
        page,
        size);
  }

  // Synchronize callers in the ingestion gateway; the transaction commits before broadcasting.
  @Transactional
  public boolean ingest(ObservationRequest request) {
    geography.ward(request.wardId());
    var old = observations.findById(request.eventId().toString());
    if (old.isPresent()) {
      var o = old.get();
      boolean same =
          o.getWardId().equals(request.wardId())
              && o.getSource().equals(request.source())
              && o.getObservedAt().equals(request.observedAt())
              && o.getTemperature() == request.temperature()
              && o.getHumidity() == request.humidity()
              && o.getWindSpeed() == request.windSpeed()
              && o.getRainfall() == request.rainfall();
      if (!same) throw new ApiException(409, "event_conflict");
      return false;
    }
    var observation = new Observation();
    observation.setId(request.eventId().toString());
    observation.setWardId(request.wardId());
    observation.setTemperature(request.temperature());
    observation.setHumidity(request.humidity());
    observation.setWindSpeed(request.windSpeed());
    observation.setRainfall(request.rainfall());
    observation.setSource(request.source());
    observation.setObservedAt(request.observedAt());
    observations.saveAndFlush(observation);
    publisher.publishEvent(new StoredEvent(request.wardId(), event(observation)));
    return true;
  }
}
