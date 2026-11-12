"""Compare both backends against one isolated PostgreSQL database; never print credentials."""
import argparse
from datetime import datetime, timezone
import json
import socket
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4


def request(base, path, method="GET", data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    payload = None if data is None else json.dumps(data).encode()
    try:
        response = urlopen(Request(base + path, data=payload, method=method, headers=headers), timeout=20)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.load(response)


def normalized(value):
    if isinstance(value, float):
        return round(value, 9)
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalized(item) for item in value]
    if isinstance(value, str):
        if value.startswith("http://127.0.0.1:"):
            url = urlsplit(value)
            return url.path + "?" + url.query
        if len(value) > 19 and value[4:5] == "-" and "T" in value:
            try:
                return datetime.fromisoformat(value).astimezone(timezone.utc).isoformat()
            except ValueError:
                pass
    return value


def tcp(port, value):
    with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
        connection.sendall((json.dumps(value) + "\n").encode())
        with connection.makefile("rb") as stream:
            return json.loads(stream.readline())


def run(args):
    old, new = args.legacy_url.rstrip("/"), args.spring_url.rstrip("/")
    if any(urlsplit(base).hostname not in {"127.0.0.1", "localhost"} for base in (old, new)):
        raise SystemExit("Only isolated localhost test servers are allowed")
    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
        print("PASS:", name)

    for path in ["/api/v1/health", "/api/v1/provinces?page_size=1", "/api/v1/wards?province_id=01&page_size=2", "/api/v1/wards/00004", "/api/v1/geography/nearest-ward"]:
        method, data = ("POST", {"latitude": 21.03, "longitude": 105.85}) if "nearest" in path else ("GET", None)
        a, b = request(old, path, method, data), request(new, path, method, data)
        check("public " + path, a[0] == b[0] == 200 and normalized(a[1]) == normalized(b[1]))
    for path in ["/api/v1/provinces?page=0", "/api/v1/wards?page_size=101", "/api/v1/missing", "/api/v1/auth/me"]:
        a, b = request(old, path), request(new, path)
        check("error " + path, a[0] == b[0] and a[1]["error"]["code"] == b[1]["error"]["code"])

    prefix = str(uuid4())
    account_a = {"name": "Parity A", "email": prefix + "a@example.com", "password": "Parity-test-password-123"}
    account_b = {**account_a, "name": "Parity B", "email": prefix + "b@example.com"}
    status, registered_a = request(old, "/api/v1/auth/register", "POST", account_a)
    check("FastAPI registers legacy account", status == 201)
    token_a = registered_a["data"]["access_token"]
    status, me = request(new, "/api/v1/auth/me", token=token_a)
    check("Spring accepts FastAPI JWT", status == 200 and me["data"] == registered_a["data"]["user"])
    status, _ = request(new, "/api/v1/auth/login", "POST", {key: account_a[key] for key in ("email", "password")})
    check("Spring verifies existing Argon2 hash", status == 200)
    status, registered_b = request(new, "/api/v1/auth/register", "POST", account_b)
    check("Spring registers account on Alembic schema", status == 201)
    token_b = registered_b["data"]["access_token"]
    check("FastAPI accepts Spring JWT", request(old, "/api/v1/auth/me", token=token_b)[0] == 200)
    check("FastAPI verifies Java Argon2 hash", request(old, "/api/v1/auth/login", "POST", {key: account_b[key] for key in ("email", "password")})[0] == 200)

    path = "/api/v1/users/me/address"
    check("Spring saves address", request(new, path, "PATCH", {"ward_id": " 00004 ", "address_text": "  Địa chỉ A  "}, token_a)[0] == 200)
    check("address persists identically across runtimes", normalized(request(old, path, token=token_a)) == normalized(request(new, path, token=token_a)))
    check("user B cannot see A address", request(new, path, token=token_b)[1]["data"]["ward"] is None)
    check("delete address persists", request(new, path, "DELETE", token=token_a)[0] == 200 and request(old, path, token=token_a)[1]["data"]["ward"] is None)

    for source in ("simulator", "provider"):
        event = {"event_id": str(uuid4()), "ward_id": "00004", "temperature": 36, "humidity": 80, "wind_speed": 55, "rainfall": 25, "source": source, "observed_at": "2026-11-04T07:15:00.123456789+07:00"}
        check(source + " accepted by FastAPI TCP", tcp(args.legacy_tcp, event)["status"] == "accepted")
        check(source + " duplicate accepted across runtimes", tcp(args.spring_tcp, event)["status"] == "duplicate")
        check(source + " conflict detected across runtimes", tcp(args.spring_tcp, {**event, "temperature": 20})["code"] == "event_conflict")
        event["event_id"] = str(uuid4())
        check(source + " accepted by Java TCP", tcp(args.spring_tcp, event)["status"] == "accepted")
        check(source + " Java write readable as duplicate by FastAPI", tcp(args.legacy_tcp, event)["status"] == "duplicate")
    for path in ["/api/v1/wards/00004/weather/current", "/api/v1/wards/00004/weather/history?page_size=1"]:
        a, b = request(old, path), request(new, path)
        check("observation parity " + path, a[0] == b[0] == 200 and normalized(a[1]) == normalized(b[1]))
    check("Java logout succeeds", request(new, "/api/v1/auth/logout", "POST", token=token_a)[0] == 200)
    check("Java logout revokes legacy JWT on both servers", all(request(base, "/api/v1/auth/me", token=token_a)[0] == 401 for base in (old, new)))
    check("FastAPI logout succeeds", request(old, "/api/v1/auth/logout", "POST", token=token_b)[0] == 200)
    check("FastAPI logout revokes Java JWT on both servers", all(request(base, "/api/v1/auth/me", token=token_b)[0] == 401 for base in (old, new)))
    print(json.dumps({"checks": len(checks), "result": "PASS", "database": "isolated PostgreSQL; no Neon writes"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-url", default="http://127.0.0.1:18801")
    parser.add_argument("--spring-url", default="http://127.0.0.1:18802")
    parser.add_argument("--legacy-tcp", type=int, default=19901)
    parser.add_argument("--spring-tcp", type=int, default=19902)
    run(parser.parse_args())
