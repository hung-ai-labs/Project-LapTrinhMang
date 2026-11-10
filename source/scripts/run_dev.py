"""PyCharm-friendly development launcher. Never migrates or resets a database."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "source/server"
CLIENT = ROOT / "source/client"
COLLECTOR = ROOT / "source/scripts/collect_open_meteo.py"


def python_command():
    candidate = SERVER / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(candidate) if candidate.exists() else sys.executable


def port_open(port):
    with socket.socket() as connection:
        connection.settimeout(0.3)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def require_free(port):
    if port_open(port):
        raise RuntimeError(f"Cổng {port} đang được sử dụng. Hãy dừng phiên chạy cũ trước.")


def stop(process):
    if process.poll() is not None:
        return
    if os.name == "posix":
        os.killpg(process.pid, signal.SIGTERM)
    else:
        process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait()


def main():
    parser = argparse.ArgumentParser(description="Chạy Weather Stream từ PyCharm hoặc terminal")
    parser.add_argument("--service", choices=["all", "backend", "frontend", "collector"], default="all")
    parser.add_argument("--collector", action="store_true", help="Bật collector khi chạy all")
    parser.add_argument("--ward-id", action="append", default=[], help="Lặp lại để chọn nhiều phường/xã")
    parser.add_argument("--all-wards", action="store_true", help="Chủ động chọn toàn bộ Ward có tọa độ")
    parser.add_argument("--reload", action="store_true", help="Tự nạp lại backend; bỏ cờ này khi Debug")
    parser.add_argument("--check", action="store_true", help="Chỉ kiểm tra cấu hình, không mở server")
    args = parser.parse_args()
    backend = args.service in {"all", "backend"}
    frontend = args.service in {"all", "frontend"}
    collector = args.service == "collector" or (args.service == "all" and args.collector)
    if collector and not (args.ward_id or args.all_wards):
        parser.error("Collector cần --ward-id MA_XA hoặc --all-wards; mặc định không quét toàn quốc.")
    if args.ward_id and args.all_wards:
        parser.error("Chọn --ward-id hoặc --all-wards, không dùng cả hai.")
    python = python_command()
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if backend or collector:
        if not (SERVER / ".env").exists():
            raise RuntimeError("Thiếu source/server/.env. Xem docs/07_CHAY_PYCHARM.md.")
        result = subprocess.run([python, "-c", "import uvicorn, sqlalchemy, jwt, httpx"],
                                capture_output=True)
        if result.returncode:
            raise RuntimeError("Thiếu dependency backend. Cài requirements-dev.txt vào interpreter.")
    if frontend and (not npm or not (CLIENT / "node_modules/.bin/vite").exists()):
        raise RuntimeError("Thiếu Node/npm hoặc node_modules. Chạy npm ci tại source/client.")

    # Read settings without showing database credentials or the signing key.
    settings = {}
    if backend or collector:
        import json
        result = subprocess.run([python, "-c", (
            "import json; from app.core.config import get_settings; s=get_settings(); "
            "print(json.dumps({'port':s.tcp_port,'enabled':s.enable_tcp,'source':s.weather_source}))"
        )], cwd=SERVER, capture_output=True, text=True, check=True)
        settings = json.loads(result.stdout)
        if collector and (not settings["enabled"] or settings["source"] != "provider"):
            raise RuntimeError("Collector cần ENABLE_TCP=true và WEATHER_SOURCE=provider trong .env.")
    commands = []
    if backend:
        command = [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
        if args.reload:
            command.append("--reload")
        commands.append(("Backend", command, SERVER))
    if frontend:
        commands.append(("Frontend", [npm, "run", "dev", "--", "--host", "127.0.0.1",
                                      "--port", "8080", "--strictPort"], CLIENT))
    if collector:
        command = [python, str(COLLECTOR), "--port", str(settings["port"])]
        for ward in args.ward_id:
            command.extend(["--ward-id", ward])
        commands.append(("Collector", command, SERVER))
    for name, command, cwd in commands:
        print(f"{name}: {' '.join(command)}\n  Working directory: {cwd}", flush=True)
    if args.check:
        print("Kiểm tra thành công. Không chạy migration, server hoặc collector.")
        return
    if backend:
        require_free(8000)
        if settings["enabled"]:
            require_free(settings["port"])
    if frontend:
        require_free(8080)
    if collector and not backend and not port_open(settings["port"]):
        raise RuntimeError("Hãy chạy backend trước collector.")
    if args.service == "backend":
        # Run in this interpreter so PyCharm Debug can hit application breakpoints.
        os.chdir(SERVER)
        sys.path.insert(0, str(SERVER))
        if importlib.util.find_spec("uvicorn") is None:
            raise RuntimeError("Chọn interpreter source/server/.venv trong PyCharm.")
        import uvicorn
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=args.reload)
        return

    processes = []
    try:
        for name, command, cwd in commands:
            if name == "Collector" and backend:
                deadline = time.monotonic() + 45
                while True:
                    if any(p.poll() is not None for p in processes):
                        raise RuntimeError("Một service đã dừng trước khi collector khởi động.")
                    try:
                        with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health", timeout=2):
                            break
                    except (OSError, urllib.error.URLError):
                        if time.monotonic() >= deadline:
                            raise RuntimeError("Backend/DB chưa sẵn sàng. Kiểm tra .env và migration.")
                        time.sleep(1)
            processes.append(subprocess.Popen(command, cwd=cwd, start_new_session=os.name == "posix"))
        if frontend:
            print("\nWeb: http://localhost:8080 · Swagger: http://localhost:8000/docs", flush=True)
        print("Dừng bằng Ctrl+C hoặc Stop trong PyCharm. Không tự chạy migration.", flush=True)
        while True:
            for process in processes:
                if process.poll() is not None:
                    raise RuntimeError(f"Một service đã dừng (exit={process.returncode}).")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nĐang dừng các service…", flush=True)
    finally:
        for process in reversed(processes):
            stop(process)


if __name__ == "__main__":
    # PyCharm Stop normally sends SIGINT; handle SIGTERM gracefully as well.
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Không khởi động được: {exc if isinstance(exc, RuntimeError) else 'kiểm tra cấu hình backend thất bại.'}", file=sys.stderr)
        raise SystemExit(1)
