"""Import the pinned catalog into the isolated benchmark database only."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from app.db.session import Session, engine
from app.services.administrative_units import apply_snapshot, load_snapshot


async def main():
    catalog = Path("/source/data/administrative")
    # Windows Git checkouts can use CRLF; verify the canonical LF bytes against
    # the original manifest without changing the snapshot or weakening its hash.
    with TemporaryDirectory() as directory:
        snapshot_path = Path(directory) / "snapshot.json"
        snapshot_path.write_bytes(
            (catalog / "snapshot.json").read_bytes().replace(b"\r\n", b"\n")
        )
        snapshot = load_snapshot(snapshot_path, catalog / "manifest.json")
        try:
            async with Session.begin() as session:
                await apply_snapshot(session, snapshot)
        finally:
            await engine.dispose()
    print(
        f"Imported {len(snapshot.provinces)} provinces and {len(snapshot.wards)} wards"
    )


if __name__ == "__main__":
    asyncio.run(main())
