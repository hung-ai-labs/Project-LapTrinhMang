"""Compatibility launcher for PyCharm Run: Java backend and React frontend."""
import argparse
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "source/server"
CLIENT = ROOT / "source/client"


def main():
    parser = argparse.ArgumentParser(description="Chạy Spring Boot + React")
    parser.add_argument("--service", choices=["all", "backend", "frontend", "collector"], default="all")
    parser.add_argument("--collector", action="store_true")
    parser.add_argument("--ward-id", action="append", default=[])
    parser.add_argument("--all-wards", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    collector = args.collector or args.service == "collector"
    if args.ward_id and args.all_wards:
        parser.error("Chọn --ward-id hoặc --all-wards.")
    if collector and not (args.ward_id or args.all_wards):
        parser.error("Collector cần --ward-id MA_XA; có thể lặp lại để chọn nhiều xã.")
    mvn = shutil.which("mvn.cmd" if os.name == "nt" else "mvn")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    commands = []
    env = os.environ.copy()
    if args.service in {"all", "backend", "collector"}:
        if not mvn or not shutil.which("java"):
            raise RuntimeError("Cần Java 17+ và Maven. Xem source/server/README.md.")
        if not (SERVER / ".env").exists():
            raise RuntimeError("Thiếu source/server/.env. Sao chép từ .env.example và điền cấu hình.")
        if collector:
            env["SPRING_PROFILES_ACTIVE"] = "collector"
            env["COLLECTOR_WARD_IDS"] = ",".join(args.ward_id)
            env["COLLECTOR_ALL_WARDS"] = str(args.all_wards).lower()
        if args.service == "collector":
            env["SPRING_MAIN_WEB_APPLICATION_TYPE"] = "none"
            env["ENABLE_TCP"] = "false"
        commands.append(("Spring Boot", [mvn, "spring-boot:run"], SERVER))
    if args.service in {"all", "frontend"}:
        if not npm or not (CLIENT / "node_modules").exists():
            raise RuntimeError("Cần Node/npm và npm ci tại source/client.")
        commands.append(("React", [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", "8080", "--strictPort"], CLIENT))
    for name, command, cwd in commands:
        print(f"{name}: {' '.join(command)}\n  Working directory: {cwd}", flush=True)
    if args.check:
        print("Kiểm tra công cụ hoàn tất. Chưa kết nối database, chưa chạy migration.")
        return
    processes = []
    try:
        for _, command, cwd in commands:
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, start_new_session=os.name == "posix"))
        print("Web: http://localhost:8080 · Swagger: http://localhost:8000/docs", flush=True)
        while True:
            for process in processes:
                if process.poll() is not None:
                    raise RuntimeError(f"Một service đã dừng (exit={process.returncode}). Kiểm tra log phía trên.")
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            if process.poll() is not None:
                continue
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        main()
    except RuntimeError as error:
        raise SystemExit(str(error))
