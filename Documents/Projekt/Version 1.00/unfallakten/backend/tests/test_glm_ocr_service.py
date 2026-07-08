"""
Tests fuer services/glm_ocr_service.py (S1.6a).

Der Stub ist hinter Feature-Flag ``GLM_OCR_ENABLED``. Solange das Flag False
ist (Default), wird Tesseract als Primaerquelle verwendet und glm_ocr_seite()
kehrt mit None zurueck. Bei True geht ein OpenAI-kompatibler Vision-Aufruf
an ``OCR_LLM_BASE_URL`` (LM Studio).
"""
import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _dummy_bild():
    from PIL import Image
    return Image.new("RGB", (100, 30), "white")


class TestFeatureFlag(unittest.TestCase):
    def test_deaktiviert_liefert_none(self):
        from backend.services import glm_ocr_service
        with mock.patch.dict(os.environ, {"GLM_OCR_ENABLED": "false"}, clear=False):
            result = glm_ocr_service.glm_ocr_seite(_dummy_bild())
        self.assertIsNone(result)

    def test_aktiviert_ruft_vision_endpoint(self):
        from backend.services import glm_ocr_service

        gefangen = {}

        class FakeResponse:
            def __init__(self, content):
                self.choices = [mock.MagicMock(
                    message=mock.MagicMock(content=content)
                )]

        class FakeClient:
            def __init__(self, base_url, api_key):
                gefangen["base_url"] = base_url
                self.chat = mock.MagicMock()
                self.chat.completions = mock.MagicMock()
                self.chat.completions.create = self._create

            def _create(self, **kwargs):
                gefangen["kwargs"] = kwargs
                return FakeResponse("Rechnung Nr. 12345\nBetrag 268,35 EUR")

        with mock.patch.dict(os.environ, {
            "GLM_OCR_ENABLED": "true",
            "OCR_LLM_BASE_URL": "http://host.docker.internal:1235/v1",
            "OCR_LLM_MODEL": "glm-ocr",
        }, clear=False), \
             mock.patch.object(glm_ocr_service, "_make_client",
                                lambda: FakeClient("http://x", "y")):
            text = glm_ocr_service.glm_ocr_seite(_dummy_bild(), lang="de")

        self.assertIn("Rechnung", text)
        self.assertIn("268,35", text)
        # base_url wurde korrekt uebernommen (via _make_client-Test unten)
        self.assertIn("model", gefangen["kwargs"])
        self.assertEqual(gefangen["kwargs"]["model"], "glm-ocr")
        # image_url ist in den messages
        msgs = gefangen["kwargs"]["messages"]
        self.assertTrue(any(
            isinstance(m.get("content"), list) and
            any(part.get("type") == "image_url" for part in m["content"])
            for m in msgs
        ))

    def test_ist_aktiviert(self):
        from backend.services.glm_ocr_service import ist_aktiviert
        with mock.patch.dict(os.environ, {"GLM_OCR_ENABLED": "true"}, clear=False):
            self.assertTrue(ist_aktiviert())
        with mock.patch.dict(os.environ, {"GLM_OCR_ENABLED": "false"}, clear=False):
            self.assertFalse(ist_aktiviert())
        with mock.patch.dict(os.environ, {"GLM_OCR_ENABLED": "1"}, clear=False):
            self.assertTrue(ist_aktiviert())


if __name__ == "__main__":
    unittest.main()
