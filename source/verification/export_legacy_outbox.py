"""One-time, read-only export from the old collector SQLite outbox to Java JSON files."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import UUID


def export(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as database:
        rows = database.execute("SELECT event_id, payload, rejected FROM events ORDER BY rowid")
        count = 0
        for event_id, payload, rejected in rows:
            value = json.loads(payload)
            if str(UUID(event_id)) != str(UUID(value["event_id"])):
                raise ValueError("Outbox event ID mismatch")
            content = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
            digest = hashlib.sha256(content.encode()).hexdigest()
            target = destination / f"{event_id}-{digest}.json{'.rejected' if rejected else ''}"
            if not target.exists():
                temporary = target.with_suffix(target.suffix + ".tmp")
                temporary.write_text(content, encoding="utf-8")
                temporary.replace(target)
            count += 1
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(f"Exported {export(args.source, args.destination)} events; SQLite source unchanged")
