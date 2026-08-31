import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["version"], "0.3.0")

    def test_home_renders(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("BoardSesh", response.text)
        self.assertIn("CRUX", response.text)
        self.assertIn('<html lang="en">', response.text)
        self.assertIn("MoonBoard catalog converter", response.text)
        self.assertIn('id="language-toggle"', response.text)
        self.assertIn("Switch to German", response.text)

    def test_language_switch_is_persistent(self):
        response = self.client.get("/static/app.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn('LANGUAGE_STORAGE_KEY = "boardsesh-crux-language"', response.text)
        self.assertIn("localStorage.setItem", response.text)
        self.assertIn("MoonBoard-Katalogkonverter", response.text)

    def test_schema_is_served(self):
        response = self.client.get("/schema/crux-import-v2.schema.json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["properties"]["version"]["const"],
            2,
        )

    def test_legacy_schema_is_still_served(self):
        response = self.client.get("/schema/crux-import-v1.schema.json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["properties"]["version"]["const"], 1)

    def test_bridge_mapping_proxy_returns_summaries(self):
        record = {
            "id": "mapping-1",
            "wallid": 216943,
            "name": "Mini",
            "board_type": "mini",
            "setup": "mini_2020",
            "mapping": {
                "boardsesh_layout_id": 6,
                "matches": [
                    {"moonboard_hold_id": 1, "crux_hold_ids": ["hold-a"]}
                ],
            },
        }
        with patch(
            "app.main.fetch_bridge_mapping_payload",
            new=AsyncMock(return_value={"mappings": [record]}),
        ):
            response = self.client.post(
                "/api/bridge/mappings",
                json={"bridge_url": "http://bridge.test", "wall_id": 216943},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["mappings"][0]["boardsesh_layout_id"],
            6,
        )


if __name__ == "__main__":
    unittest.main()
