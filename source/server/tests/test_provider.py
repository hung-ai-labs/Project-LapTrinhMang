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
    event = collector.normalize("hanoi", payload)
    assert event["rainfall"] == 8
    assert event["source"] == "provider"
    assert event == collector.normalize("hanoi", payload)
    assert event["event_id"] != collector.normalize("danang", payload)["event_id"]
    payload["current"]["interval"] = 0
    with pytest.raises(ValueError):
        collector.normalize("hanoi", payload)
