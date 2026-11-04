"""Poll Ward coordinates in batches and deliver durable events through bounded TCP IO."""

import argparse
import asyncio
import json
import logging
import math
import signal
import socket
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

VARIABLES = "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation"
MAX_FRAME_BYTES = 8192


async def load_wards(ward_ids=()):
    # Lazy imports keep provider parsing independently testable without a database.
    server_root = Path(__file__).resolve().parents[1] / "server"
    if server_root.is_dir():
        sys.path.insert(0, str(server_root))
    from sqlalchemy import select

    from app.db import Province, Ward
    from app.db.session import Session, engine

    statement = (
        select(Ward.id, Ward.latitude, Ward.longitude)
        .join(Province, Province.id == Ward.province_id)
        .where(
            Ward.is_active.is_(True),
            Province.is_active.is_(True),
            Ward.latitude.is_not(None),
            Ward.longitude.is_not(None),
        )
        .order_by(Ward.id)
    )
    if ward_ids:
        statement = statement.where(Ward.id.in_(ward_ids))
    try:
        async with Session() as session:
            rows = (await session.execute(statement)).all()
        locations = [
            {"id": row.id, "latitude": float(row.latitude), "longitude": float(row.longitude)}
            for row in rows
        ]
        if ward_ids and set(ward_ids) != {row["id"] for row in locations}:
            raise ValueError("Selected wards must be active and have coordinates")
        return locations
    finally:
        await engine.dispose()


def number(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Invalid weather number")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError("Weather number out of range")
    return value


def normalize(ward_id, payload):
    current, units = payload["current"], payload["current_units"]
    expected = {
        "temperature_2m": "°C",
        "wind_speed_10m": "km/h",
        "precipitation": "mm",
        "relative_humidity_2m": "%",
    }
    if any(units.get(key) != value for key, value in expected.items()):
        raise ValueError("Unexpected weather units")
    interval = current["interval"]
    if type(interval) is not int or interval <= 0:
        raise ValueError("Invalid precipitation accumulation interval")
    timestamp = current["time"]
    if type(timestamp) is not int:
        raise ValueError("Invalid provider timestamp")
    observed = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    rainfall = round(number(current["precipitation"], 0, 1000) * 3600 / interval, 4)
    return {
        "event_id": str(uuid5(NAMESPACE_URL, f"open-meteo:ward:{ward_id}:{observed}")),
        "ward_id": ward_id,
        "temperature": number(current["temperature_2m"], -60, 65),
        "humidity": number(current["relative_humidity_2m"], 0, 100),
        "wind_speed": number(current["wind_speed_10m"], 0, 500),
        "rainfall": number(rainfall, 0, 1000),
        "source": "provider",
        "observed_at": observed,
    }


def fetch(locations, *, timeout=20):
    query = urllib.parse.urlencode(
        {
            "latitude": ",".join(str(row["latitude"]) for row in locations),
            "longitude": ",".join(str(row["longitude"]) for row in locations),
            "current": VARIABLES,
            "wind_speed_unit": "kmh",
            "temperature_unit": "celsius",
            "precipitation_unit": "mm",
            "timeformat": "unixtime",
            "timezone": "UTC",
            "forecast_days": 1,
        }
    )
    request = urllib.request.Request(
        "https://api.open-meteo.com/v1/forecast?" + query,
        headers={"User-Agent": "WeatherStream-Education/0.3"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(1024 * 1024 + 1)
    if len(body) > 1024 * 1024:
        raise ValueError("Provider response too large")
    payloads = json.loads(body)
    if isinstance(payloads, dict):
        payloads = [payloads]
    if not isinstance(payloads, list) or len(payloads) != len(locations):
        raise ValueError("Provider response count does not match coordinate count")
    # Multi-coordinate responses follow request order; grid coordinates may differ.
    return [normalize(row["id"], payload) for row, payload in zip(locations, payloads, strict=True)]


class Outbox:
    """Bounded durable current queue; differing payloads retain the same transport event ID."""

    def __init__(self, path, capacity):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        self.capacity = capacity
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "event_id TEXT NOT NULL, payload TEXT NOT NULL, rejected INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (event_id, payload))"
        )
        self.connection.commit()

    @staticmethod
    def encode(event):
        return json.dumps(event, allow_nan=False, sort_keys=True)

    def count(self, *, pending_only=False):
        with self.lock:
            query = "SELECT COUNT(*) FROM events" + (" WHERE rejected=0" if pending_only else "")
            return self.connection.execute(query).fetchone()[0]

    def add(self, events):
        with self.lock, self.connection:
            count = self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            if count + len(events) > self.capacity:
                raise ValueError("Outbox capacity reached")
            self.connection.executemany(
                "INSERT OR IGNORE INTO events (event_id, payload) VALUES (?, ?)",
                [(event["event_id"], self.encode(event)) for event in events],
            )

    def first(self):
        with self.lock:
            row = self.connection.execute(
                "SELECT payload FROM events WHERE rejected=0 ORDER BY rowid LIMIT 1"
            ).fetchone()
            return json.loads(row[0]) if row else None

    def finish(self, event, *, rejected=False):
        with self.lock, self.connection:
            statement = (
                "UPDATE events SET rejected=1 WHERE event_id=? AND payload=?"
                if rejected
                else "DELETE FROM events WHERE event_id=? AND payload=?"
            )
            self.connection.execute(statement, (event["event_id"], self.encode(event)))

    def close(self):
        self.connection.close()


class RejectedEvent(ValueError):
    pass


class DeliveryConnection:
    def __init__(self, host, port):
        self.host, self.port = host, port
        self.connection = self.stream = None

    def close(self):
        if self.stream is not None:
            self.stream.close()
        if self.connection is not None:
            self.connection.close()
        self.connection = self.stream = None

    def deliver(self, value):
        frame = (json.dumps(value, allow_nan=False) + "\n").encode()
        if len(frame) > MAX_FRAME_BYTES:
            raise RejectedEvent("Outgoing frame exceeds limit")
        if self.connection is None:
            self.connection = socket.create_connection((self.host, self.port), timeout=10)
            self.stream = self.connection.makefile("rb")
        self.connection.sendall(frame)
        frame = self.stream.readline(MAX_FRAME_BYTES + 1)
        if len(frame) > MAX_FRAME_BYTES or not frame.endswith(b"\n"):
            raise ValueError("Incomplete or oversized ACK")
        reply = json.loads(frame)
        if not isinstance(reply, dict) or reply.get("event_id") != value["event_id"]:
            raise ValueError("ACK event_id mismatch")
        if reply.get("status") in {"accepted", "duplicate"}:
            return
        if reply.get("code") in {"invalid_ward", "invalid_observation", "event_conflict"}:
            raise RejectedEvent(reply["code"])
        raise OSError("TCP storage unavailable")


def send_pending(outbox, args, stop):
    connection = DeliveryConnection(args.host, args.port)
    retry_delay = 1
    try:
        while not stop.is_set():
            value = outbox.first()
            if value is None:
                connection.close()
                stop.wait(0.5)
                continue
            started = time.monotonic()
            try:
                connection.deliver(value)
                outbox.finish(value)
                retry_delay = 1
            except RejectedEvent as exc:
                outbox.finish(value, rejected=True)
                logging.error("Event %s retained as rejected: %s", value["event_id"], exc)
            except (OSError, ValueError, TypeError):
                connection.close()
                logging.warning("TCP unavailable or invalid ACK; retry in %ss", retry_delay)
                stop.wait(retry_delay)
                retry_delay = min(60, retry_delay * 2)
            stop.wait(max(0, 1 / args.send_rate - (time.monotonic() - started)))
    except Exception:
        logging.exception("Sender stopped; unsent events remain in outbox")
        stop.set()
    finally:
        connection.close()


CURRENT_POLL_SECONDS = 15 * 60


def next_current_due(previous_due, now):
    next_due = previous_due + CURRENT_POLL_SECONDS
    skipped = max(0, int((now - next_due) // CURRENT_POLL_SECONDS))
    if skipped:
        logging.warning("Skipped %s expired current collection ticks", skipped)
    return next_due + skipped * CURRENT_POLL_SECONDS


def run_current_schedule(collect_cycle, stop, *, clock=time.monotonic):
    due = clock()
    while not stop.is_set():
        if stop.wait(max(0, due - clock())):
            break
        try:
            collect_cycle(cycle_start=due, deadline=due + CURRENT_POLL_SECONDS)
        except Exception:
            logging.exception("Current cycle failed; next scheduled cycle will retry")
        due = next_current_due(due, clock())


def provider_cooldown(headers):
    raw = headers.get("Retry-After", "")
    if raw.isdigit():
        return max(60, int(raw))
    try:
        return max(60, (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return 60


def collect_cycle(outbox, args, stop, *, cycle_start, deadline, clock=time.monotonic):
    if clock() < getattr(args, "provider_not_before", 0):
        logging.warning("Provider cooldown active; skipping current cycle")
        return 1
    locations = asyncio.run(asyncio.wait_for(load_wards(args.ward_id), timeout=20))
    if not locations:
        raise ValueError("No active wards with coordinates; import the catalog first")
    batches = [
        locations[i : i + args.batch_size] for i in range(0, len(locations), args.batch_size)
    ]
    spacing = 1 if args.once else CURRENT_POLL_SECONDS / len(batches)
    failures, next_http = 0, cycle_start
    logging.info(
        "Current cycle: %s wards, %s batches, pending=%s",
        len(locations),
        len(batches),
        outbox.count(pending_only=True),
    )
    for index, batch in enumerate(batches):
        now = clock()
        scheduled = max(cycle_start + index * spacing, next_http)
        if stop.is_set() or now >= deadline or scheduled >= deadline:
            logging.warning("Current cycle ended before all batches completed")
            return failures + 1
        if stop.wait(max(0, scheduled - now)):
            return failures + 1
        remaining = deadline - clock()
        if remaining <= 0:
            return failures + 1
        if outbox.count() + len(batch) > args.max_pending:
            logging.warning("Outbox full; skip remaining fetches until the next 15-minute cycle")
            return failures + 1
        next_http = clock() + 1
        try:
            outbox.add(fetch(batch, timeout=min(20, remaining)))
        except urllib.error.HTTPError as exc:
            failures += 1
            if exc.code == 429:
                cooldown = provider_cooldown(exc.headers)
                args.provider_not_before = clock() + cooldown
                logging.warning(
                    "Provider rate limit; cooldown %ss, remaining batches skipped", cooldown
                )
                exc.close()
                return failures
            logging.warning("Provider HTTP %s; batch will retry next cycle", exc.code)
            exc.close()
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            failures += 1
            logging.warning("Current batch failed; retry at next 15-minute cycle", exc_info=True)
    return failures


def main():
    parser = argparse.ArgumentParser(
        description="Lấy current theo Ward mỗi 15 phút và stream qua TCP"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--send-rate", type=float, default=5)
    parser.add_argument("--max-pending", type=int, default=20000)
    parser.add_argument("--outbox", type=Path, default=Path(".collector/outbox.sqlite3"))
    parser.add_argument("--ward-id", action="append", default=[])
    parser.add_argument("--drain-timeout", type=int, default=1200)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 50:
        parser.error("Batch size must be between 1 and 50")
    if not math.isfinite(args.send_rate) or not 0 < args.send_rate <= 20:
        parser.error("Send rate must be between 0 (exclusive) and 20 events/second")
    if args.max_pending < args.batch_size or args.drain_timeout <= 0:
        parser.error("Outbox must hold at least one batch; drain timeout must be positive")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda _signum, _frame: stop.set())
    outbox = Outbox(args.outbox, args.max_pending)
    sender = threading.Thread(target=send_pending, args=(outbox, args, stop), name="tcp-sender")
    sender.start()
    failed = False
    try:
        if args.once:
            started = time.monotonic()
            try:
                failed = bool(
                    collect_cycle(
                        outbox,
                        args,
                        stop,
                        cycle_start=started,
                        deadline=started + CURRENT_POLL_SECONDS,
                    )
                )
            except Exception:
                logging.exception("Collection failed; pending events retained")
                failed = True
            deadline = time.monotonic() + args.drain_timeout
            while (
                outbox.count(pending_only=True)
                and not stop.is_set()
                and time.monotonic() < deadline
            ):
                stop.wait(0.2)
            failed = failed or outbox.count() > 0 or stop.is_set()
        else:
            run_current_schedule(
                lambda **schedule: collect_cycle(outbox, args, stop, **schedule),
                stop,
            )
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        sender.join()
        outbox.close()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
