"""End-to-end HTTP/JSON tests for the Web Lighting Console server."""

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from controller.devices.manager import ControllerManager
from controller.ui.server import LightingConsoleServer


class WebConsoleAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.manager = ControllerManager(data_dir=Path(self._tmp.name))
        self.manager.register_simulator()
        self.server = LightingConsoleServer(self.manager, host="127.0.0.1", port=0)
        self.server.start(background=True)

    def tearDown(self) -> None:
        self.server.stop()
        self._tmp.cleanup()

    def _req(self, path: str, body: dict | None = None) -> tuple[int, dict]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"} if body is not None else {}
        req = urllib.request.Request(self.server.url + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            try:
                return err.code, json.loads(err.read().decode("utf-8"))
            finally:
                err.close()

    def test_legacy_cli_modules_import_without_blocking(self) -> None:
        import HLEffect
        import HLMasterEffects
        import controllights
        import datasender
        import weather

        self.assertTrue(callable(controllights.main))
        self.assertTrue(callable(HLEffect.main))
        self.assertTrue(callable(HLMasterEffects.main))
        self.assertTrue(callable(datasender.main))
        self.assertTrue(callable(weather.main))

    def test_ui_state_pixels_patterns_and_dev_safety_guard(self) -> None:
        code, st = self._req("/api/state")
        self.assertEqual(code, 200)
        self.assertEqual(len(st["pixels"]), 50)
        self.assertGreaterEqual(len(st["host_effects"]), 20)

        # Gradient pixel update + pattern save
        code, res = self._req(
            "/api/pixels",
            {"action": "gradient", "stops": [[255, 0, 0], [0, 255, 0]], "show": True},
        )
        self.assertEqual(code, 200)
        self.assertEqual(res["pixels"][0], [255, 0, 0])

        code, pat = self._req(
            "/api/patterns",
            {"op": "save", "name": "TestGrad", "pixels": res["pixels"]},
        )
        self.assertEqual(code, 200)
        self.assertIn("TestGrad", pat["patterns"])

        # Read-only raw query allowed without confirmation
        code, q = self._req("/api/dev/raw", {"hex": "81 8A 8B"})
        self.assertEqual(code, 200)
        self.assertTrue(q["rx_inner_hex"].startswith("ea81"))

        # Write raw command blocked without explicit confirmation
        code, denied = self._req("/api/dev/raw", {"hex": "71 24 0F", "confirmed": False})
        self.assertEqual(code, 400)
        self.assertIn("Safety guard", denied["error"])

        # Allowed when explicitly confirmed
        code, ok = self._req("/api/dev/raw", {"hex": "71 24 0F", "confirmed": True})
        self.assertEqual(code, 200)

        # Diagnostic export endpoint
        with urllib.request.urlopen(self.server.url + "/api/dev/export", timeout=3.0) as resp:
            exported = json.loads(resp.read().decode("utf-8"))
        self.assertGreaterEqual(exported["total_recorded"], 1)
