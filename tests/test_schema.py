import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from app.boardsesh import CatalogClimb, SnapshotEntry
from app.converter import ConversionOptions, convert_catalog
from app.mapping import MappingContext


class SchemaTests(unittest.TestCase):
    def test_generated_document_matches_schema(self):
        schema_path = (
            Path(__file__).resolve().parents[1]
            / "schema"
            / "crux-import-v2.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)

        mapping = MappingContext(
            mapping_id="mapping-1",
            mapping_name="Mini",
            wall_id=216943,
            board_type="mini",
            setup="mini_2020",
            layout_id=6,
            hold_id_to_crux={1: ("a1",), 2: ("b2",)},
        )
        snapshot = SnapshotEntry(
            layout_id=6,
            url="https://example.test/snapshot.db.gz",
            built_at="2026-08-31T07:15:00Z",
            content_encoding="gzip",
            bytes=42,
        )
        climb = CatalogClimb(
            uuid="uuid-1",
            name="Schema problem",
            description="",
            setter_username=None,
            frames="p1r42p2r44",
            angle=40,
            display_difficulty=18,
            benchmark_difficulty=None,
            ascensionist_count=0,
            quality_average=None,
            characteristics=(),
        )
        document = convert_catalog(
            [climb],
            mapping,
            snapshot,
            "https://example.test/manifest.json",
            ConversionOptions(),
        )

        errors = list(Draft202012Validator(schema).iter_errors(document))

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
