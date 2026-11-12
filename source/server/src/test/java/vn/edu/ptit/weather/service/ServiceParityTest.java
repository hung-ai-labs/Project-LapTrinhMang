package vn.edu.ptit.weather.service;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.test.util.ReflectionTestUtils;
import vn.edu.ptit.weather.dto.WeatherDto.*;
import vn.edu.ptit.weather.entity.*;
import vn.edu.ptit.weather.exception.ApiException;
import vn.edu.ptit.weather.repository.*;

class ServiceParityTest {
  static class MutableClock extends Clock {
    volatile Instant now = Instant.parse("2026-11-04T02:20:00Z");

    public ZoneId getZone() {
      return ZoneOffset.UTC;
    }

    public Clock withZone(ZoneId zone) {
      return this;
    }

    public Instant instant() {
      return now;
    }
  }

  ObjectMapper json = new ObjectMapper().findAndRegisterModules();

  Ward ward() {
    var w = new Ward();
    w.setId("00004");
    w.setName("Ba Đình");
    w.setProvinceId("01");
    w.setLatitude(new java.math.BigDecimal("21"));
    w.setLongitude(new java.math.BigDecimal("105"));
    return w;
  }

  JsonNode previewPayload() {
    var payload = json.createObjectNode();
    var units = payload.putObject("hourly_units");
    units.put("time", "unixtime");
    var h = payload.putObject("hourly");
    var times = h.putArray("time");
    times.add(Instant.parse("2026-11-04T03:00:00Z").getEpochSecond());
    times.add(Instant.parse("2026-11-04T04:00:00Z").getEpochSecond());
    Map.of(
            "temperature_2m",
            "°C",
            "relative_humidity_2m",
            "%",
            "wind_speed_10m",
            "km/h",
            "precipitation",
            "mm")
        .forEach(
            (key, unit) -> {
              units.put(key, unit);
              h.putArray(key)
                  .add(key.equals("temperature_2m") ? 29 : 0)
                  .add(key.equals("temperature_2m") ? 32 : 0);
            });
    return payload;
  }

  @Test
  void previewSharesOnlyInflightWorkAndRefreshesLater() throws Exception {
    var geo = mock(GeographyService.class);
    when(geo.coordinates("00004")).thenReturn(ward());
    var provider = mock(OpenMeteoClient.class);
    var started = new CountDownLatch(1);
    var gate = new CountDownLatch(1);
    var calls = new java.util.concurrent.atomic.AtomicInteger();
    when(provider.fetch(anyDouble(), anyDouble(), anyMap()))
        .thenAnswer(
            inv -> {
              calls.incrementAndGet();
              started.countDown();
              assertThat(gate.await(3, TimeUnit.SECONDS)).isTrue();
              return previewPayload();
            });
    var service = new ForecastService(geo, provider, new MutableClock());
    var pool = Executors.newFixedThreadPool(5);
    try {
      var first = pool.submit(() -> service.preview("00004"));
      assertThat(started.await(2, TimeUnit.SECONDS)).isTrue();
      var second = pool.submit(() -> service.preview("00004"));
      Thread.sleep(80);
      gate.countDown();
      assertThat(first.get(3, TimeUnit.SECONDS)).isEqualTo(second.get(3, TimeUnit.SECONDS));
      assertThat(calls.get()).isEqualTo(1);
      service.preview("00004");
      assertThat(calls.get()).isEqualTo(2);
    } finally {
      gate.countDown();
      pool.shutdownNow();
      service.close();
    }
  }

  @Test
  void previewMovesToNextTargetWhenHourChangesDuringFetch() {
    var geo = mock(GeographyService.class);
    when(geo.coordinates("00004")).thenReturn(ward());
    var provider = mock(OpenMeteoClient.class);
    var clock = new MutableClock();
    clock.now = Instant.parse("2026-11-04T02:59:59Z");
    when(provider.fetch(anyDouble(), anyDouble(), anyMap()))
        .thenAnswer(
            inv -> {
              clock.now = Instant.parse("2026-11-04T03:00:01Z");
              return previewPayload();
            });
    var service = new ForecastService(geo, provider, clock);
    try {
      var data = (Map<?, ?>) service.preview("00004");
      assertThat(data.get("target_at")).isEqualTo(Instant.parse("2026-11-04T04:00:00Z"));
      assertThat(data.get("predicted_temperature")).isEqualTo(32.0);
      verify(provider, times(2)).fetch(anyDouble(), anyDouble(), anyMap());
    } finally {
      service.close();
    }
  }

  @Test
  void boundedSharedQueueSurvivesCallerCancellation() throws Exception {
    try (var shared = new SharedRequests(1, 1)) {
      var started = new CountDownLatch(1);
      var gate = new CountDownLatch(1);
      var pool = Executors.newFixedThreadPool(2);
      try {
        var first =
            pool.submit(
                () ->
                    shared.get(
                        "same",
                        () -> {
                          started.countDown();
                          try {
                            gate.await();
                          } catch (InterruptedException e) {
                            throw new RuntimeException(e);
                          }
                          return "ok";
                        }));
        assertThat(started.await(2, TimeUnit.SECONDS)).isTrue();
        assertThatThrownBy(() -> shared.get("extra", () -> "bad")).isInstanceOf(ApiException.class);
        first.cancel(true);
        var second =
            pool.submit(
                () ->
                    shared.get(
                        "same",
                        () -> {
                          throw new AssertionError("must reuse request");
                        }));
        Thread.sleep(50);
        gate.countDown();
        assertThat(second.get(2, TimeUnit.SECONDS)).isEqualTo("ok");
      } finally {
        gate.countDown();
        pool.shutdownNow();
      }
    }
  }

  @Test
  void catalogKeepsAtomicProvinceAndWardSnapshotDuringDatabaseFailure() {
    var provinces = mock(ProvinceRepository.class);
    var wards = mock(WardRepository.class);
    var clock = new MutableClock();
    var p = new Province();
    p.setId("01");
    p.setName("Hà Nội");
    when(provinces.findByIsActiveTrueOrderByNameAsc()).thenReturn(List.of(p));
    when(wards.findByIsActiveTrueOrderByNameAsc()).thenReturn(List.of(ward()));
    var service = new GeographyService(provinces, wards, clock);
    assertThat(service.provinces().stale()).isFalse();
    clock.now = clock.now.plusSeconds(601);
    when(provinces.findByIsActiveTrueOrderByNameAsc())
        .thenThrow(new DataAccessResourceFailureException("private-detail"));
    assertThat(service.provinces().stale()).isTrue();
    assertThat(service.wards("01").rows()).hasSize(1);
    assertThat(service.wards("01").stale()).isTrue();
    assertThatThrownBy(() -> new GeographyService(provinces, wards, clock).provinces())
        .isInstanceOf(ApiException.class)
        .hasMessageContaining("mất kết nối");
  }

  Observation oldObservation() {
    var o = new Observation();
    o.setId(UUID.randomUUID().toString());
    o.setWardId("00004");
    o.setSource("provider");
    o.setObservedAt(Instant.now().minusSeconds(3600));
    return o;
  }

  @Test
  void delayedProviderCurrentIsFetchedOnlyOncePerBucketAndFailureFallsBack() throws Exception {
    var geo = mock(GeographyService.class);
    when(geo.ward("00004")).thenReturn(ward());
    when(geo.coordinates("00004")).thenReturn(ward());
    var observations = mock(ObservationService.class);
    var ingestion = mock(IngestionGateway.class);
    var provider = mock(OpenMeteoClient.class);
    var record = oldObservation();
    when(observations.latest("00004", "provider")).thenReturn(Optional.of(record));
    var event = new WeatherEvent("weather.update", ObservationResponse.from(record), List.of());
    when(observations.event(record)).thenReturn(event);
    var payload =
        json.readTree(
            "{\"current_units\":{\"temperature_2m\":\"°C\",\"relative_humidity_2m\":\"%\",\"wind_speed_10m\":\"km/h\",\"precipitation\":\"mm\"},\"current\":{\"time\":1793751300,\"interval\":900,\"temperature_2m\":25,\"relative_humidity_2m\":80,\"wind_speed_10m\":5,\"precipitation\":0.5}}");
    when(provider.fetch(anyDouble(), anyDouble(), anyMap())).thenReturn(payload);
    var service = new CurrentWeatherService(geo, observations, ingestion, provider);
    ReflectionTestUtils.setField(service, "source", "provider");
    assertThat(service.current("00004")).isEqualTo(event);
    assertThat(service.current("00004")).isEqualTo(event);
    verify(provider, times(1)).fetch(anyDouble(), anyDouble(), anyMap());
    var failing = new CurrentWeatherService(geo, observations, ingestion, provider);
    ReflectionTestUtils.setField(failing, "source", "provider");
    when(provider.fetch(anyDouble(), anyDouble(), anyMap()))
        .thenThrow(new ApiException(503, "provider error"));
    assertThat(failing.current("00004")).isEqualTo(event);
    assertThat(failing.current("00004")).isEqualTo(event);
    verify(provider, times(2)).fetch(anyDouble(), anyDouble(), anyMap());
  }

  @Test
  void savedAddressRemainsReadableAfterAdministrativeCodeBecomesInactive() {
    var auth = mock(AuthService.class);
    var geo = mock(GeographyService.class);
    var users = mock(UserRepository.class);
    var user = new User();
    user.setDefaultWardId("00004");
    user.setAddressText("Địa chỉ đã lưu");
    when(auth.currentUser()).thenReturn(user);
    var saved = ward();
    saved.setActive(false);
    var parent = new Province();
    parent.setId("01");
    parent.setName("Tỉnh cũ");
    parent.setActive(false);
    when(geo.savedWard("00004")).thenReturn(saved);
    when(geo.savedProvince("01")).thenReturn(parent);
    var result = new UserService(auth, geo, users).address();
    assertThat(result.ward().id()).isEqualTo("00004");
    assertThat(result.province().id()).isEqualTo("01");
    verify(geo, never()).ward(anyString());
  }
}
