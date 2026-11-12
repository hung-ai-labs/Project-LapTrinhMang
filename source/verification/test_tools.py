"""Verify migration helpers preserve pending events and the original outbox."""
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4
from export_legacy_outbox import export


class OutboxExportTest(unittest.TestCase):
    def test_export_is_repeatable_and_preserves_conflicts_and_rejections(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "legacy.sqlite3"
            identifier = str(uuid4())
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE events(event_id TEXT, payload TEXT, rejected INTEGER)")
                for temperature, rejected in [(20, 0), (25, 0), (30, 1)]:
                    connection.execute("INSERT INTO events VALUES (?,?,?)", (identifier, json.dumps({"event_id": identifier, "temperature": temperature}), rejected))
            target = root / "java-outbox"
            self.assertEqual(export(database, target), 3)
            self.assertEqual(export(database, target), 3)
            self.assertEqual(len(list(target.glob("*.json"))), 2)
            self.assertEqual(len(list(target.glob("*.rejected"))), 1)
            with sqlite3.connect(database) as connection:
                self.assertEqual(connection.execute("SELECT count(*) FROM events").fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main()
