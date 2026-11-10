"""Summarize real JMeter CSV samples and enforce provisional acceptance thresholds."""

import argparse
import csv
import gzip
import math
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

HTTP_LABELS = {"Provinces", "Wards", "Current weather", "Weather history"}


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("samples", type=Path)
    parser.add_argument("--users", type=int, required=True)
    parser.add_argument("--loops", type=int, required=True)
    parser.add_argument("--p95-ms", type=float, default=1000)
    parser.add_argument("--error-percent", type=float, default=1)
    args = parser.parse_args()
    opener = gzip.open if args.samples.suffix == ".gz" else open
    with opener(args.samples, "rt", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit("Không có sample; không thể kết luận.")
    groups = defaultdict(list)
    for row in rows:
        groups[row["label"]].append(row)
    start = min(int(row["timeStamp"]) for row in rows)
    end = max(int(row["timeStamp"]) + int(row["elapsed"]) for row in rows)
    duration = max((end - start) / 1000, 0.001)
    peak = max(int(row["allThreads"]) for row in rows)
    passed = peak >= args.users
    connected = {
        row["threadName"]: int(row["timeStamp"]) + int(row["elapsed"])
        for row in groups["WS connect"]
        if row["success"].lower() == "true"
    }
    finished = {
        row["threadName"]: int(row["timeStamp"])
        for row in groups["WS verify and close"]
        if row["success"].lower() == "true"
    }
    overlap = (
        max(0, (min(finished.values()) - max(connected.values())) / 1000)
        if len(connected) == len(finished) == args.users
        else 0
    )
    passed &= overlap > 0
    lines = [
        "# Kết quả Apache JMeter",
        "",
        f"Bắt đầu UTC: {datetime.fromtimestamp(start / 1000, UTC).isoformat()}",
        f"Thời gian lấy mẫu: {duration:.2f} giây; số thread đỉnh: {peak}.",
        f"Khoảng cùng giữ đủ {args.users} WebSocket thành công: {overlap:.2f} giây.",
        "",
        "Số liệu gồm cả ramp-up và kết thúc; req/s tính trên toàn cửa sổ đo.",
        "p50/p95 dùng nearest rank, gồm cả request lỗi. WS connect đo handshake;",
        "WS verify chỉ kiểm tra nhận update đúng Ward/nguồn, không đo độ trễ truyền tin.",
        "",
        "| Nhóm | Samples | Lỗi | Lỗi % | p50 ms | p95 ms | Max ms | req/s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in sorted(HTTP_LABELS | {"WS connect", "WS verify and close"}):
        samples = groups[label]
        if not samples:
            passed = False
            lines.append(f"| {label} | 0 | — | — | — | — | — | — |")
            continue
        errors = sum(row["success"].lower() != "true" for row in samples)
        rate = errors / len(samples) * 100
        elapsed = [int(row["elapsed"]) for row in samples]
        p95 = percentile(elapsed, 0.95)
        lines.append(
            f"| {label} | {len(samples)} | {errors} | {rate:.2f} | "
            f"{percentile(elapsed, 0.5)} | {p95} | {max(elapsed)} | "
            f"{len(samples) / duration:.2f} |"
        )
        if label in HTTP_LABELS:
            passed &= rate < args.error_percent and p95 <= args.p95_ms
            passed &= len(samples) == args.users * args.loops
        else:
            passed &= errors == 0 and len(samples) == args.users
    http = [row for row in rows if row["label"] in HTTP_LABELS]
    lines.extend(
        [
            "",
            f"Thông lượng HTTP tổng: {len(http) / duration:.2f} req/s.",
            (
                f"Ngưỡng đề xuất: từng API có lỗi < {args.error_percent:g}% và p95 ≤ "
                f"{args.p95_ms:g} ms; đủ {args.users} WS mở/kiểm tra thành công; "
                f"thread đỉnh ≥ {args.users}."
            ),
            f"Mỗi API phải đủ {args.users * args.loops} mẫu và có khoảng giữ đồng thời đủ WS.",
            "",
            f"Kết luận theo ngưỡng đề xuất: **{'ĐẠT' if passed else 'KHÔNG ĐẠT'}**.",
            "Đây là kết quả của kịch bản và môi trường đã đo, không phải sức tải tối đa.",
            "",
        ]
    )
    output = args.samples.with_name("summary.md")
    output.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
