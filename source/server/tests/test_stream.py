import json
import socket
from uuid import uuid4

from app.main import app


def observation(**changes):
    return {
        "event_id": str(uuid4()),
        "city": "hanoi",
        "temperature": 36,
        "humidity": 80,
        "wind_speed": 55,
        "rainfall": 25,
        "source": "simulator",
        "observed_at": "2026-10-20T12:00:00+07:00",
        **changes,
    }


def connect():
    port = app.state.tcp_server.sockets[0].getsockname()[1]
    return socket.create_connection(("127.0.0.1", port), timeout=5)


def send(value):
    with connect() as connection:
        connection.sendall((json.dumps(value) + "\n").encode())
        return json.loads(connection.makefile("rb").readline())


def test_tcp_to_database_and_websocket(client):
    with client.websocket_connect("/api/v1/ws/weather/hanoi") as ws:
        value = observation()
        assert send(value)["status"] == "accepted"
        event = ws.receive_json()
        assert event["observation"]["id"] == value["event_id"]
        assert {a["code"] for a in event["alerts"]} == {"heat", "rain", "wind"}
    current = client.get("/api/v1/weather/hanoi/current").json()
    assert current["observation"]["temperature"] == 36
    assert client.get("/api/v1/health").status_code == 200
    forecast = client.get("/api/v1/weather/hanoi/forecast").json()
    assert forecast["is_ai"] is False
    assert forecast["method"] == "persistence_baseline"


def test_retry_is_idempotent(client):
    value = observation()
    assert send(value)["status"] == "accepted"
    assert send(value)["status"] == "duplicate"
    assert len(client.get("/api/v1/weather/hanoi/history").json()) == 1


def test_tcp_split_and_coalesced_frames(client):
    first, second = observation(), observation()
    payload = (json.dumps(first) + "\n" + json.dumps(second) + "\n").encode()
    with connect() as connection:
        connection.sendall(payload[:20])
        connection.sendall(payload[20:])
        stream = connection.makefile("rb")
        assert json.loads(stream.readline())["status"] == "accepted"
        assert json.loads(stream.readline())["status"] == "accepted"
    assert len(client.get("/api/v1/weather/hanoi/history").json()) == 2


def test_invalid_frame_does_not_kill_connection(client):
    with connect() as connection:
        connection.sendall(b"not-json\n")
        stream = connection.makefile("rb")
        assert json.loads(stream.readline())["code"] == "invalid_observation"
        connection.sendall((json.dumps(observation()) + "\n").encode())
        assert json.loads(stream.readline())["status"] == "accepted"
    assert send(observation(humidity=101))["status"] == "error"
    assert send(observation(temperature=float("nan")))["status"] == "error"
    assert send(observation(observed_at="2026-10-20T12:00:00"))["status"] == "error"


def test_city_isolation_and_empty_state(client):
    assert client.get("/api/v1/weather/hanoi/current").status_code == 404
    assert client.get("/api/v1/weather/unknown/history").status_code == 422
    assert client.get("/api/v1/weather/hanoi/history?limit=999").status_code == 422
    with client.websocket_connect("/api/v1/ws/weather/hanoi") as ws:
        send(observation(city="danang"))
        value = observation()
        send(value)
        assert ws.receive_json()["observation"]["id"] == value["event_id"]
    assert len(client.get("/api/v1/weather/danang/history").json()) == 1


def test_oversized_tcp_frame_is_rejected(client):
    with connect() as connection:
        connection.sendall(b"x" * 9000 + b"\n")
        reply = json.loads(connection.makefile("rb").readline())
        assert reply["code"] == "frame_limit_or_timeout"
