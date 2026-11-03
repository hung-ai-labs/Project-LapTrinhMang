"""Poll model-based current weather; deliver stable events over TCP with ACK/retry."""
import argparse
import json
import logging
import socket
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

LOCATIONS = {"hanoi": (21.0285, 105.8542), "danang": (16.0544, 108.2022),
             "hcm": (10.8231, 106.6297)}
VARIABLES = "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation"


def normalize(city, payload):
    current = payload["current"]
    units = payload["current_units"]
    if units["temperature_2m"] != "°C" or units["wind_speed_10m"] != "km/h":
        raise ValueError("Unexpected weather units")
    if units["precipitation"] != "mm" or units["relative_humidity_2m"] != "%":
        raise ValueError("Unexpected precipitation/humidity units")
    interval = current["interval"]
    if not isinstance(interval, (int, float)) or interval <= 0:
        raise ValueError("Invalid precipitation accumulation interval")
    observed = datetime.fromtimestamp(current["time"], timezone.utc).isoformat()
    values = [current[key] for key in VARIABLES.split(",")]
    if any(value is None for value in values):
        raise ValueError("Missing current weather value")
    return {
        "event_id": str(uuid5(NAMESPACE_URL, f"open-meteo:{city}:{observed}")),
        "city": city, "temperature": values[0], "humidity": values[1],
        "wind_speed": values[2], "rainfall": round(values[3] * 3600 / interval, 4),
        "source": "provider", "observed_at": observed,
    }


def fetch(city):
    lat, lon = LOCATIONS[city]
    query = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "current": VARIABLES,
                                   "wind_speed_unit": "kmh", "temperature_unit": "celsius",
                                   "precipitation_unit": "mm", "timeformat": "unixtime",
                                   "timezone": "UTC", "forecast_days": 1})
    request = urllib.request.Request("https://api.open-meteo.com/v1/forecast?" + query,
                                     headers={"User-Agent": "WeatherStream-Education/0.2"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return normalize(city, json.load(response))


def deliver(value, host, port):
    with socket.create_connection((host, port), timeout=10) as connection:
        connection.sendall((json.dumps(value) + "\n").encode())
        reply = json.loads(connection.makefile("rb").readline(8192))
        if reply.get("status") not in {"accepted", "duplicate"}:
            raise ValueError("TCP ingestion rejected observation")
        logging.info("%s: %s", value["city"], reply["status"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--interval", type=int, default=900)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.interval < 300:
        parser.error("Poll interval must be at least 300 seconds")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    pending = {}
    while True:
        failed = False
        for city in LOCATIONS:
            try:
                if city not in pending:
                    pending[city] = fetch(city)
                deliver(pending[city], args.host, args.port)
                del pending[city]
            except (OSError, ValueError, KeyError, TypeError):
                logging.warning("%s: provider/TCP unavailable; retry pending event next cycle", city)
                failed = True
        if args.once:
            raise SystemExit(1 if failed else 0)
        time.sleep(30 if pending else args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
