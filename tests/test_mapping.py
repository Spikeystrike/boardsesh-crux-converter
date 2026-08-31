import unittest

import httpx

from app.mapping import (
    MappingError,
    fetch_bridge_mapping_payload,
    mapping_summaries,
    select_mapping,
    validate_bridge_url,
)


def mapping_record(mapping_id="map-1"):
    return {
        "id": mapping_id,
        "wallid": 216943,
        "name": "Mini left",
        "board_type": "mini",
        "setup": "mini_2020",
        "mapping": {
            "boardsesh_layout_id": 6,
            "matches": [
                {"moonboard_hold_id": 1, "crux_hold_ids": ["hold-a"]},
                {"moonboard_hold_id": 2, "crux_hold_ids": ["hold-c", "hold-b"]},
            ],
        },
    }


class MappingTests(unittest.TestCase):
    def test_selects_single_mapping_and_normalizes_hold_ids(self):
        result = select_mapping({"mappings": [mapping_record()]})

        self.assertEqual(result.layout_id, 6)
        self.assertEqual(result.wall_id, 216943)
        self.assertEqual(result.hold_id_to_crux[2], ("hold-b", "hold-c"))

    def test_selects_one_of_multiple_mappings_by_id(self):
        payload = {"mappings": [mapping_record("one"), mapping_record("two")]}

        result = select_mapping(payload, "two")

        self.assertEqual(result.mapping_id, "two")

    def test_multiple_mappings_require_selection(self):
        payload = {"mappings": [mapping_record("one"), mapping_record("two")]}

        with self.assertRaisesRegex(MappingError, "Select one mapping"):
            select_mapping(payload)

    def test_accepts_bridge_save_response(self):
        result = select_mapping({"mapping": mapping_record()})

        self.assertEqual(result.mapping_name, "Mini left")

    def test_summary_exposes_board_and_layout(self):
        summary = mapping_summaries([mapping_record()])[0]

        self.assertEqual(summary["setup"], "mini_2020")
        self.assertEqual(summary["boardsesh_layout_id"], 6)

    def test_bridge_url_validation(self):
        self.assertEqual(
            validate_bridge_url("http://bridge.local:8000/"),
            "http://bridge.local:8000",
        )
        with self.assertRaises(MappingError):
            validate_bridge_url("ftp://bridge.local")
        with self.assertRaises(MappingError):
            validate_bridge_url("https://user:secret@bridge.local")


class BridgeFetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_wall_specific_mapping_endpoint(self):
        async def handler(request):
            self.assertEqual(request.url.path, "/virtualmapping/mappings")
            self.assertEqual(request.url.params["wallid"], "216943")
            return httpx.Response(200, json={"mappings": [mapping_record()]})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            result = await fetch_bridge_mapping_payload(
                "http://bridge.test",
                216943,
                timeout_seconds=1,
                client=client,
            )

        self.assertEqual(result["mappings"][0]["id"], "map-1")


if __name__ == "__main__":
    unittest.main()
