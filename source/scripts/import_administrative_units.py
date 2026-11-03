"""Validate or import a complete, pinned administrative catalog."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT / "server"))

from app.services.administrative_units import apply_snapshot, load_snapshot


def main():
    parser = argparse.ArgumentParser(
        description="Kiểm tra và nhập danh mục tỉnh/phường xã"
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=SOURCE_ROOT / "data" / "administrative" / "snapshot.json",
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--apply", action="store_true", help="Ghi vào DATABASE_URL đã cấu hình"
    )
    args = parser.parse_args()
    manifest = args.manifest or args.snapshot.with_name("manifest.json")
    try:
        snapshot = load_snapshot(args.snapshot, manifest)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    if args.apply:
        from app.db.session import Session, engine

        async def run():
            try:
                async with Session.begin() as session:
                    await apply_snapshot(session, snapshot)
            finally:
                await engine.dispose()

        asyncio.run(run())
    print(
        json.dumps(
            {
                "mode": "applied" if args.apply else "dry_run",
                "dataset_version": snapshot.dataset_version,
                "provinces": len(snapshot.provinces),
                "wards": len(snapshot.wards),
                "wards_with_coordinates": sum(
                    row.latitude is not None for row in snapshot.wards
                ),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
