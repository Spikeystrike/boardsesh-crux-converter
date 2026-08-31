import unittest
from datetime import datetime, timezone

from app.boardsesh import CatalogClimb, SnapshotEntry
from app.converter import (
    ConversionError,
    ConversionOptions,
    convert_catalog,
    foot_rule_from_characteristics,
    grade_label,
    parse_frames,
)
from app.mapping import MappingContext


MAPPING = MappingContext(
    mapping_id="map-1",
    mapping_name="Mini left",
    wall_id=216943,
    board_type="mini",
    setup="mini_2020",
    layout_id=6,
    hold_id_to_crux={
        1: ("crux-start",),
        2: ("crux-hand",),
        3: ("crux-finish",),
    },
)
SNAPSHOT = SnapshotEntry(
    layout_id=6,
    url="https://example.test/mini.db.gz",
    built_at="2026-08-31T07:15:00Z",
    content_encoding="gzip",
    bytes=123,
)


def climb(
    frames="p1r42p2r43p3r44",
    uuid="climb-1",
    characteristics=(),
):
    return CatalogClimb(
        uuid=uuid,
        name="Test problem",
        description="",
        setter_username="Setter",
        frames=frames,
        angle=40,
        display_difficulty=18.0,
        benchmark_difficulty=18.0,
        ascensionist_count=12,
        quality_average=3.5,
        characteristics=tuple(characteristics),
    )


class FrameTests(unittest.TestCase):
    def test_parses_roles(self):
        self.assertEqual(
            parse_frames("p1r42p2r43p3r44"),
            [(1, "start"), (2, "hand"), (3, "finish")],
        )

    def test_rejects_unknown_role(self):
        with self.assertRaisesRegex(ConversionError, "role code"):
            parse_frames("p1r99")

    def test_rejects_trailing_garbage(self):
        with self.assertRaises(ConversionError):
            parse_frames("p1r42x")


class GradeTests(unittest.TestCase):
    def test_maps_grade_systems(self):
        self.assertEqual(grade_label(18.0, "boardsesh"), "6B")
        self.assertEqual(grade_label(18.0, "font"), "6b")
        self.assertEqual(grade_label(18.0, "v_scale"), "V4")

    def test_non_integral_grade_is_unknown(self):
        self.assertIsNone(grade_label(18.5, "font"))


class FootRuleTests(unittest.TestCase):
    def test_default_is_feet_follow_hands_with_open_kicker(self):
        self.assertEqual(
            foot_rule_from_characteristics(["crimpy", "powerful"]),
            "feet_follow_hands_open_kicker",
        )

    def test_maps_moonboard_methods(self):
        self.assertEqual(
            foot_rule_from_characteristics(["method_no_kickboard"]),
            "feet_follow_hands",
        )
        self.assertEqual(
            foot_rule_from_characteristics(["method_footless"]),
            "campus",
        )

    def test_maps_generic_characteristics(self):
        self.assertEqual(
            foot_rule_from_characteristics(["no_kickboard"]),
            "feet_follow_hands",
        )
        self.assertEqual(
            foot_rule_from_characteristics(["campus"]),
            "campus",
        )

    def test_rejects_footless_with_kickboard(self):
        with self.assertRaisesRegex(ConversionError, "no exact CRUX"):
            foot_rule_from_characteristics(["method_footless_kickboard"])

    def test_rejects_multiple_moonboard_methods(self):
        with self.assertRaisesRegex(ConversionError, "Multiple MoonBoard"):
            foot_rule_from_characteristics(
                ["method_footless", "method_no_kickboard"]
            )


class ConversionTests(unittest.TestCase):
    def test_converts_complete_climb(self):
        document = convert_catalog(
            [climb()],
            MAPPING,
            SNAPSHOT,
            "https://example.test/manifest.json",
            ConversionOptions(),
            generated_at=datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(document["format"], "crux-climb-import")
        self.assertEqual(document["version"], 2)
        self.assertEqual(document["summary"]["included_climbs"], 1)
        converted = document["climbs"][0]
        self.assertEqual(converted["external_id"], "boardsesh:climb-1:40")
        self.assertEqual(converted["grade"], "6b")
        self.assertEqual(
            converted["foot_rules"],
            "feet_follow_hands_open_kicker",
        )
        self.assertEqual(converted["source"]["characteristics"], [])
        self.assertEqual(
            converted["holds"],
            [
                {"id": "crux-start", "hold_type": "start"},
                {"id": "crux-hand", "hold_type": "hand"},
                {"id": "crux-finish", "hold_type": "finish"},
            ],
        )

    def test_derives_foot_rule_per_climb(self):
        document = convert_catalog(
            [
                climb(uuid="no-kicker", characteristics=["method_no_kickboard"]),
                climb(uuid="campus", characteristics=["method_footless"]),
            ],
            MAPPING,
            SNAPSHOT,
            "https://example.test/manifest.json",
            ConversionOptions(),
        )

        self.assertEqual(
            [item["foot_rules"] for item in document["climbs"]],
            ["feet_follow_hands", "campus"],
        )
        self.assertEqual(
            document["summary"]["foot_rule_counts"],
            {"feet_follow_hands": 1, "campus": 1},
        )

    def test_skips_footless_with_kickboard_with_diagnostics(self):
        document = convert_catalog(
            [climb(characteristics=["method_footless_kickboard"])],
            MAPPING,
            SNAPSHOT,
            "https://example.test/manifest.json",
            ConversionOptions(),
        )

        self.assertEqual(document["climbs"], [])
        self.assertEqual(
            document["summary"]["skipped_unsupported_foot_rule"],
            1,
        )
        self.assertEqual(
            document["summary"]["skipped_examples"][0]["reason"],
            "unsupported_foot_rule",
        )

    def test_skips_incomplete_mapping_with_diagnostics(self):
        document = convert_catalog(
            [climb(frames="p1r42p99r44")],
            MAPPING,
            SNAPSHOT,
            "https://example.test/manifest.json",
            ConversionOptions(),
        )

        self.assertEqual(document["climbs"], [])
        self.assertEqual(document["summary"]["skipped_missing_mapping"], 1)
        self.assertEqual(
            document["summary"]["skipped_examples"][0]["moonboard_hold_ids"],
            [99],
        )

    def test_skips_invalid_frames(self):
        document = convert_catalog(
            [climb(frames="broken")],
            MAPPING,
            SNAPSHOT,
            "https://example.test/manifest.json",
            ConversionOptions(),
        )

        self.assertEqual(document["summary"]["skipped_invalid_frames"], 1)

    def test_rejects_layout_mismatch(self):
        other_snapshot = SnapshotEntry(
            layout_id=2,
            url=SNAPSHOT.url,
            built_at=SNAPSHOT.built_at,
            content_encoding=SNAPSHOT.content_encoding,
            bytes=SNAPSHOT.bytes,
        )

        with self.assertRaisesRegex(ConversionError, "does not match"):
            convert_catalog(
                [climb()],
                MAPPING,
                other_snapshot,
                "https://example.test/manifest.json",
                ConversionOptions(),
            )


if __name__ == "__main__":
    unittest.main()
