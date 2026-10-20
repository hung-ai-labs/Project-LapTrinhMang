"""Standalone TCP producer, standard library only; all generated data is synthetic."""
import argparse
import json
import math
import socket
import time
from datetime import datetime, timezone
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description="Phát dữ liệu thời tiết mô phỏng qua TCP")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--interval", type=float, default=3)
    parser.add_argument("--count", type=int, default=0, help="0 = chạy liên tục")
    args = parser.parse_args()
    if args.interval <= 0 or args.count < 0:
        parser.error("interval > 0, count >= 0")
    pending = None
    tick = 0
    cities = ["hanoi", "danang", "hcm"]
    while not args.count or tick < args.count:
        try:
            with socket.create_connection((args.host, args.port), timeout=10) as connection:
                stream = connection.makefile("rb")
                while not args.count or tick < args.count:
                    if pending is None:
                        pending = {
                            "event_id": str(uuid4()),
                            "city": cities[tick % 3],
                            "temperature": round(30 + 7 * math.sin(tick / 5), 1),
                            "humidity": round(70 + 20 * math.cos(tick / 5), 1),
                            "wind_speed": round(20 + 35 * abs(math.sin(tick / 7)), 1),
                            "rainfall": 25 if tick % 10 == 0 else 0,
                            "source": "simulator",
                            "observed_at": datetime.now(timezone.utc).isoformat(),
                        }
                    connection.sendall((json.dumps(pending) + "\n").encode())
                    response = stream.readline(8192)
                    if not response:
                        raise ConnectionError("Server đóng kết nối")
                    ack = json.loads(response)
                    if ack.get("status") not in {"accepted", "duplicate"}:
                        raise ConnectionError(f"Server từ chối: {ack}")
                    print(f"{pending['city']}: {ack}", flush=True)
                    pending = None
                    tick += 1
                    time.sleep(args.interval)
        except (OSError, ConnectionError, ValueError) as exc:
            print(f"Kết nối lỗi ({exc}); thử lại sau 3 giây.", flush=True)
            time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
