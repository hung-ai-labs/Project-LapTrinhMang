import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "collector", Path(__file__).resolve().parents[2] / "scripts/collect_open_meteo.py"
)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def test_provider_units_and_stable_id():
    payload = {
        "current": {
            "time": 1793664000,
            "interval": 900,
            "temperature_2m": 29,
            "relative_humidity_2m": 80,
            "wind_speed_10m": 10,
            "precipitation": 2,
        },
        "current_units": {
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "wind_speed_10m": "km/h",
            "precipitation": "mm",
        },
    }
    event = collector.normalize("001", payload)
    assert event["rainfall"] == 8
    assert event["source"] == "provider"
    assert event == collector.normalize("001", payload)
    assert event["event_id"] != collector.normalize("002", payload)["event_id"]
    payload["current"]["interval"] = 0
    with pytest.raises(ValueError):
        collector.normalize("001", payload)


@pytest.fixture
def payload():
    return {
        "current": {
            "time": 1793664000, "interval": 900, "temperature_2m": 29,
            "relative_humidity_2m": 80, "wind_speed_10m": 10, "precipitation": 2,
        },
        "current_units": {
            "temperature_2m": "°C", "relative_humidity_2m": "%",
            "wind_speed_10m": "km/h", "precipitation": "mm",
        },
    }


@pytest.mark.parametrize("duration", [20, 200])
def test_current_schedule_is_fixed_900_seconds(duration):
    now, starts = [0.0], []

    class Stop:
        stopped = False

        def is_set(self):
            return self.stopped

        def wait(self, seconds):
            now[0] += seconds
            return self.stopped

    stop = Stop()

    def cycle(*, cycle_start, deadline):
        starts.append(now[0])
        assert deadline - cycle_start == 900
        now[0] += duration
        if len(starts) == 3:
            stop.stopped = True

    collector.run_current_schedule(cycle, stop, clock=lambda: now[0])
    assert starts == [0, 900, 1800]
    assert collector.next_current_due(0, 1905) == 1800


def test_batch_requests_only_current_and_maps_requested_wards(monkeypatch, payload):
    import io
    import json
    from urllib.parse import parse_qs, urlsplit

    urls = []

    def urlopen(request, timeout):
        assert timeout == 20
        urls.append(request.full_url)
        return io.BytesIO(json.dumps([payload, payload]).encode())

    monkeypatch.setattr(collector.urllib.request, "urlopen", urlopen)
    events = collector.fetch([
        {"id": "001", "latitude": 21, "longitude": 105},
        {"id": "002", "latitude": 22, "longitude": 106},
    ])
    query = parse_qs(urlsplit(urls[0]).query)
    assert query["latitude"] == ["21,22"]
    assert query["longitude"] == ["105,106"]
    assert "current" in query and "hourly" not in query
    assert [event["ward_id"] for event in events] == ["001", "002"]
    assert "city" not in events[0]
    assert "target_at" not in events[0]


def test_incomplete_batch_does_not_misassign_ward(monkeypatch, payload):
    import io
    import json

    monkeypatch.setattr(collector.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(
        json.dumps([payload]).encode()
    ))
    with pytest.raises(ValueError, match="count"):
        collector.fetch([
            {"id": "001", "latitude": 21, "longitude": 105},
            {"id": "002", "latitude": 22, "longitude": 106},
        ])


def test_outbox_survives_restart_and_preserves_conflicting_payload(tmp_path, payload):
    path = tmp_path / "queue.sqlite3"
    event = collector.normalize("001", payload)
    conflict = {**event, "temperature": event["temperature"] + 1}
    queue = collector.Outbox(path, capacity=3)
    queue.add([event, conflict])
    queue.close()
    queue = collector.Outbox(path, capacity=3)
    assert queue.first() == event
    queue.finish(event)
    assert queue.first() == conflict
    queue.finish(conflict, rejected=True)
    assert queue.count() == 1 and queue.count(pending_only=True) == 0
    queue.close()


def test_invalid_ack_retains_pending_event(tmp_path, payload):
    import io
    import json

    value = collector.normalize("001", payload)
    queue = collector.Outbox(tmp_path / "queue.sqlite3", capacity=2)
    queue.add([value])
    connection = collector.DeliveryConnection("unused", 0)
    connection.connection = type("Socket", (), {"sendall": lambda *args: None})()
    connection.stream = io.BytesIO(json.dumps({
        "status": "accepted", "event_id": "wrong-id",
    }).encode() + b"\n")
    with pytest.raises(ValueError, match="mismatch"):
        connection.deliver(value)
    assert queue.first() == value
    queue.close()


def test_full_queue_stops_fetch_until_next_cycle(monkeypatch, tmp_path, payload):
    from types import SimpleNamespace

    async def locations(*args):
        return [{"id": "001", "latitude": 21, "longitude": 105}]

    def forbidden(*args, **kwargs):
        pytest.fail("Provider must not be called when outbox is full")

    queue = collector.Outbox(tmp_path / "queue.sqlite3", capacity=1)
    queue.add([collector.normalize("001", payload)])
    monkeypatch.setattr(collector, "load_wards", locations)
    monkeypatch.setattr(collector, "fetch", forbidden)
    args = SimpleNamespace(ward_id=[], batch_size=1, once=False, max_pending=1)
    assert collector.collect_cycle(queue, args, collector.threading.Event(), cycle_start=0,
                                   deadline=900, clock=lambda: 0) == 1
    assert queue.count() == 1
    queue.close()


def test_catalog_load_filters_wards_and_provinces(public_data):
    import asyncio

    rows = asyncio.run(collector.load_wards())
    assert {row["id"] for row in rows} == {"001", "002", "003", "005"}
    assert asyncio.run(collector.load_wards(["001"])) == [
        {"id": "001", "latitude": 21.0, "longitude": 105.0},
    ]
    with pytest.raises(ValueError, match="active"):
        asyncio.run(collector.load_wards(["004"]))
