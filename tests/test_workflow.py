from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from finalize_keyed_product import remove_key  # noqa: E402


class KeyRemovalTests(unittest.TestCase):
    def make_keyed_image(self) -> Image.Image:
        pixels = np.full((20, 20, 3), (0, 255, 0), dtype=np.uint8)
        pixels[2:18, 2:18] = (90, 90, 90)
        pixels[4:7, 4:7] = (0, 180, 0)
        pixels[12:15, 12:15] = (0, 255, 0)
        return Image.fromarray(pixels, "RGB")

    def test_auto_preserves_ambiguous_product_color_and_removes_pure_hole(self) -> None:
        result, metrics = remove_key(self.make_keyed_image(), "green", "auto")
        alpha = np.asarray(result.getchannel("A"))

        self.assertEqual(int(alpha[0, 0]), 0)
        self.assertEqual(int(alpha[5, 5]), 255)
        self.assertEqual(int(alpha[13, 13]), 0)
        self.assertEqual(metrics["protected_interior_key_pixels"], 9)
        self.assertEqual(metrics["removed_interior_key_pixels"], 9)

    def test_preserve_policy_keeps_all_disconnected_key_pixels(self) -> None:
        result, metrics = remove_key(self.make_keyed_image(), "green", "preserve")
        alpha = np.asarray(result.getchannel("A"))

        self.assertEqual(int(alpha[13, 13]), 255)
        self.assertEqual(metrics["removed_interior_key_pixels"], 0)
        self.assertEqual(metrics["protected_interior_key_pixels"], 18)


class SourceCompletenessTests(unittest.TestCase):
    def run_validator(
        self,
        original_root: Path,
        output_root: Path,
        report: Path,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "validate_outputs.py"),
                "--root",
                str(output_root),
                "--original-root",
                str(original_root),
                "--report",
                str(report),
                "--canvas",
                "64",
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_missing_output_fails_then_matching_relative_output_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            originals = root / "originals"
            outputs = root / "outputs"
            family = originals / "family"
            family.mkdir(parents=True)
            outputs.mkdir()
            Image.new("RGB", (32, 24), (120, 130, 140)).save(family / "part.JPG")

            first_report = root / "missing.json"
            first = self.run_validator(originals, outputs, first_report)
            first_data = json.loads(first_report.read_text(encoding="utf-8"))
            self.assertEqual(first.returncode, 1)
            self.assertEqual(first_data["source_count"], 1)
            self.assertEqual(first_data["missing_outputs"], ["family/part_beautified.png"])

            output_family = outputs / "family"
            output_family.mkdir()
            result = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            result.paste((100, 110, 120, 255), (8, 8, 56, 56))
            result.save(output_family / "part_beautified.png")

            second_report = root / "complete.json"
            second = self.run_validator(originals, outputs, second_report)
            second_data = json.loads(second_report.read_text(encoding="utf-8"))
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertTrue(second_data["automatic_checks_passed"])
            self.assertEqual(second_data["missing_output_count"], 0)
            self.assertEqual(second_data["unexpected_output_count"], 0)


if __name__ == "__main__":
    unittest.main()
