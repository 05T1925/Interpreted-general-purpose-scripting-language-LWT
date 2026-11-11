"""Gate for the S54 PowerPoint render evidence.

The deck was previously verified only as zip/XML artefacts. If PowerPoint COM is
unavailable the render tool writes an explicit error record; these tests then
skip with that reason instead of pretending the deck was rendered.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "s54-closeout" / "ppt-render.json"
MANIFEST = ROOT / "docs" / "delivery-manifest.json"


class PptRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not REPORT.exists():
            raise unittest.SkipTest(f"render evidence missing: {REPORT}")
        cls.doc = json.loads(REPORT.read_text(encoding="utf-8"))
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if cls.doc.get("renderer") is None:
            raise unittest.SkipTest(f"PowerPoint COM unavailable: {cls.doc.get('error')}")

    def test_render_record_contract(self) -> None:
        for key in ("slides", "exported", "pdf_bytes", "pages", "blank_pages",
                    "slide10_chart_signal", "ppt_sha256", "rendered_at_utc",
                    "renderer", "ok"):
            self.assertIn(key, self.doc)

    def test_every_slide_rendered_non_blank(self) -> None:
        self.assertEqual(self.doc["ok"], True)
        self.assertEqual(self.doc["slides"], len(self.doc["pages"]))
        self.assertEqual(self.doc["blank_pages"], [])
        self.assertTrue(all(not page["near_blank"] for page in self.doc["pages"]))

    def test_page_count_and_sha_match_manifest(self) -> None:
        self.assertEqual(self.doc["slides"], self.manifest["ppt_pages"])
        self.assertEqual(self.doc["ppt_sha256"], self.manifest["ppt_sha256"])

    def test_pdf_was_produced(self) -> None:
        self.assertGreater(self.doc["pdf_bytes"], 100_000)
        pdf = ROOT / self.doc["pdf"]
        self.assertTrue(pdf.is_file(), f"missing PDF: {pdf}")

    def test_slide10_carries_the_chart_signal(self) -> None:
        signal = self.doc["slide10_chart_signal"]
        self.assertTrue(signal["variance_above_median"])
        self.assertEqual(signal["rank"]["variance"], 1)
        self.assertEqual(signal["rank"]["ink_ratio"], 1)
        # The 12 chart values cannot be read from pixels; the XML count is the
        # cross-check, and the visual confirmation stays a human GUI-E item.
        self.assertEqual(self.doc["chart_value_points_xml"], 12)


if __name__ == "__main__":
    unittest.main()
