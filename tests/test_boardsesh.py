import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from app.boardsesh import (
    BoardSeshError,
    read_catalog,
    resolve_snapshot_entry,
    validate_snapshot,
)


def create_snapshot(path: Path):
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE board_climbs (
                board_type TEXT,
                uuid TEXT,
                layout_id INTEGER,
                name TEXT,
                description TEXT,
                setter_username TEXT,
                frames TEXT,
                is_listed INTEGER,
                is_draft INTEGER,
                characteristics TEXT
            );
            CREATE TABLE board_climb_stats (
                board_type TEXT,
                climb_uuid TEXT,
                angle INTEGER,
                display_difficulty REAL,
                benchmark_difficulty REAL,
                ascensionist_count INTEGER,
                quality_average REAL
            );
            """
        )
        climbs = [
            ("moonboard", "public-40", 6, "Alpha", "", "A", "p1r42p2r44", 1, 0, '["method_no_kickboard"]'),
            ("moonboard", "draft", 6, "Draft", "", "B", "p1r42p2r44", 1, 1, None),
            ("moonboard", "unlisted", 6, "Hidden", "", "C", "p1r42p2r44", 0, 0, "[]"),
            ("moonboard", "other-layout", 2, "Other", "", "D", "p1r42p2r44", 1, 0, '["method_footless"]'),
        ]
        connection.executemany(
            "INSERT INTO board_climbs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            climbs,
        )
        stats = [
            ("moonboard", "public-40", 40, 18, 18, 5, 3.2),
            ("moonboard", "draft", 40, 18, None, 0, None),
            ("moonboard", "unlisted", 40, 18, None, 0, None),
            ("moonboard", "other-layout", 40, 18, None, 0, None),
            ("moonboard", "public-40", 25, 17, None, 2, 2.5),
        ]
        connection.executemany(
            "INSERT INTO board_climb_stats VALUES (?, ?, ?, ?, ?, ?, ?)",
            stats,
        )
        connection.commit()
    finally:
        connection.close()


class ManifestTests(unittest.TestCase):
    def test_resolves_selected_moonboard_layout(self):
        manifest = {
            "entries": [
                {
                    "boardType": "moonboard",
                    "layoutId": 6,
                    "url": "https://example.test/mini.db.gz",
                    "builtAt": "2026-08-31T07:15:00Z",
                    "contentEncoding": "gzip",
                    "bytes": 1234,
                }
            ]
        }

        entry = resolve_snapshot_entry(manifest, 6)

        self.assertEqual(entry.layout_id, 6)
        self.assertEqual(entry.bytes, 1234)

    def test_rejects_missing_layout(self):
        with self.assertRaises(BoardSeshError):
            resolve_snapshot_entry({"entries": []}, 6)


class SnapshotTests(unittest.TestCase):
    def test_validates_and_filters_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.db"
            create_snapshot(path)

            validate_snapshot(path)
            all_angles = read_catalog(path, 6)
            forty_only = read_catalog(path, 6, angle=40)

        self.assertEqual({item.angle for item in all_angles}, {25, 40})
        self.assertEqual([item.uuid for item in forty_only], ["public-40"])
        self.assertEqual(forty_only[0].display_difficulty, 18.0)
        self.assertEqual(
            forty_only[0].characteristics,
            ("method_no_kickboard",),
        )

    def test_rejects_malformed_characteristics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.db"
            create_snapshot(path)
            connection = sqlite3.connect(path)
            try:
                connection.execute(
                    "UPDATE board_climbs SET characteristics = '{' "
                    "WHERE uuid = 'public-40'"
                )
                connection.commit()
            finally:
                connection.close()

            with self.assertRaisesRegex(BoardSeshError, "characteristics JSON"):
                read_catalog(path, 6)

    def test_rejects_database_without_required_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.db"
            sqlite3.connect(path).close()

            with self.assertRaisesRegex(BoardSeshError, "required catalog tables"):
                validate_snapshot(path)


if __name__ == "__main__":
    unittest.main()
