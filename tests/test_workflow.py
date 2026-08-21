from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import finalize_keyed_product  # noqa: E402
from finalize_keyed_product import (  # noqa: E402
    commit_staged_files,
    remove_key,
    stage_bytes,
    validate_distinct_paths,
)
from structure_checks import compare_structure_images  # noqa: E402


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
        rgb = np.asarray(result.convert("RGB"))

        self.assertEqual(int(alpha[0, 0]), 0)
        self.assertEqual(int(alpha[5, 5]), 255)
        self.assertEqual(tuple(rgb[5, 5]), (0, 180, 0))
        self.assertEqual(int(alpha[13, 13]), 0)
        self.assertEqual(metrics["protected_interior_key_pixels"], 9)
        self.assertEqual(metrics["removed_interior_key_pixels"], 9)

    def test_preserve_policy_keeps_all_disconnected_key_pixels(self) -> None:
        result, metrics = remove_key(self.make_keyed_image(), "green", "preserve")
        alpha = np.asarray(result.getchannel("A"))

        self.assertEqual(int(alpha[13, 13]), 255)
        self.assertEqual(metrics["removed_interior_key_pixels"], 0)
        self.assertEqual(metrics["protected_interior_key_pixels"], 18)

    def test_despill_neutralizes_connected_magenta_fringe(self) -> None:
        pixels = np.full((5, 5, 3), (80, 80, 80), dtype=np.uint8)
        pixels[0, 2] = (120, 70, 120)
        result, _ = remove_key(Image.fromarray(pixels, "RGB"), "magenta", "auto")
        rgba = np.asarray(result)

        self.assertGreater(int(rgba[0, 2, 3]), 0)
        self.assertLess(int(rgba[0, 2, 3]), 255)
        self.assertEqual(tuple(rgba[0, 2, :3]), (70, 70, 70))


class StructureComparisonTests(unittest.TestCase):
    def test_matching_component_and_hole_pass(self) -> None:
        original = Image.new("RGB", (128, 128), "white")
        original_draw = ImageDraw.Draw(original)
        original_draw.rectangle((24, 24, 104, 104), fill=(80, 80, 80))
        original_draw.ellipse((50, 50, 78, 78), fill="white")

        output = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        output_draw = ImageDraw.Draw(output)
        output_draw.rectangle((24, 24, 104, 104), fill=(100, 100, 100, 255))
        output_draw.ellipse((50, 50, 78, 78), fill=(0, 0, 0, 0))

        result = compare_structure_images(original, output, max_side=128)
        self.assertEqual(result["findings"], [])

    def test_added_major_subject_requires_review(self) -> None:
        original = Image.new("RGB", (128, 128), "white")
        ImageDraw.Draw(original).rectangle((18, 30, 62, 98), fill=(70, 70, 70))

        output = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        output_draw = ImageDraw.Draw(output)
        output_draw.rectangle((12, 30, 52, 98), fill=(90, 90, 90, 255))
        output_draw.rectangle((78, 40, 116, 90), fill=(90, 90, 90, 255))

        result = compare_structure_images(original, output, max_side=128)
        codes = {item["code"] for item in result["findings"]}
        self.assertIn("major_component_count_increased", codes)
        self.assertFalse(result["hard_failure"])

    def test_missing_major_subject_fails(self) -> None:
        original = Image.new("RGB", (128, 128), "white")
        original_draw = ImageDraw.Draw(original)
        original_draw.rectangle((10, 30, 50, 98), fill=(70, 70, 70))
        original_draw.rectangle((78, 38, 116, 92), fill=(70, 70, 70))

        output = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        ImageDraw.Draw(output).rectangle((20, 25, 84, 103), fill=(90, 90, 90, 255))

        result = compare_structure_images(original, output, max_side=128)
        codes = {item["code"] for item in result["findings"]}
        self.assertIn("major_component_count_decreased", codes)
        self.assertTrue(result["hard_failure"])

    def test_opaque_hole_residue_fails(self) -> None:
        original = Image.new("RGB", (128, 128), "white")
        original_draw = ImageDraw.Draw(original)
        original_draw.rectangle((18, 18, 110, 110), fill=(75, 75, 75))
        original_draw.ellipse((44, 44, 84, 84), fill="white")

        output = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        ImageDraw.Draw(output).rectangle((18, 18, 110, 110), fill=(95, 95, 95, 255))

        result = compare_structure_images(original, output, max_side=128)
        codes = {item["code"] for item in result["findings"]}
        self.assertIn("enclosed_hole_count_decreased", codes)
        self.assertTrue(result["hard_failure"])

    def test_fragmented_hole_edge_requires_review(self) -> None:
        original = Image.new("RGB", (128, 128), "white")
        original_draw = ImageDraw.Draw(original)
        original_draw.rectangle((18, 18, 110, 110), fill=(75, 75, 75))
        original_draw.ellipse((40, 40, 88, 88), fill="white")

        output = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        output_draw = ImageDraw.Draw(output)
        output_draw.rectangle((18, 18, 110, 110), fill=(95, 95, 95, 255))
        output_draw.ellipse((40, 40, 88, 88), fill=(0, 0, 0, 0))
        residue_boxes = (
            (40, 59, 51, 63),
            (77, 67, 88, 71),
            (59, 40, 63, 51),
            (67, 77, 71, 88),
        )
        for box in residue_boxes:
            output_draw.rectangle(box, fill=(30, 30, 30, 255))

        result = compare_structure_images(original, output, max_side=128)
        codes = {item["code"] for item in result["findings"]}
        self.assertIn("transparent_hole_edge_fragmented", codes)

    def test_source_crop_requires_review(self) -> None:
        original = Image.new("RGB", (128, 128), "white")
        ImageDraw.Draw(original).rectangle((0, 34, 82, 92), fill=(70, 70, 70))
        output = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        ImageDraw.Draw(output).rounded_rectangle(
            (18, 34, 110, 92), radius=20, fill=(90, 90, 90, 255)
        )

        result = compare_structure_images(original, output, max_side=128)
        codes = {item["code"] for item in result["findings"]}
        self.assertIn("source_crop_requires_review", codes)
        self.assertFalse(result["hard_failure"])


class FinalizerStructureGateTests(unittest.TestCase):
    def test_crop_review_is_blocked_then_explicitly_approved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_path = root / "original.png"
            keyed_path = root / "keyed.png"
            output_path = root / "output.png"
            qa_path = root / "qa.json"

            original = Image.new("RGB", (64, 64), "white")
            ImageDraw.Draw(original).rectangle((0, 18, 42, 46), fill=(90, 90, 90))
            original.save(original_path)

            keyed = Image.new("RGB", (64, 64), (0, 255, 0))
            ImageDraw.Draw(keyed).rounded_rectangle(
                (8, 16, 56, 48), radius=10, fill=(100, 100, 100)
            )
            keyed.save(keyed_path)

            base_command = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "finalize_keyed_product.py"),
                "--source",
                str(keyed_path),
                "--original",
                str(original_path),
                "--output",
                str(output_path),
                "--qa",
                str(qa_path),
                "--key",
                "green",
                "--canvas",
                "256",
                "--structure-analysis-size",
                "128",
            ]
            blocked = subprocess.run(
                base_command,
                text=True,
                capture_output=True,
                check=False,
            )
            blocked_data = json.loads(qa_path.read_text(encoding="utf-8"))
            self.assertEqual(blocked.returncode, 1)
            self.assertEqual(blocked_data["status"], "structure_rejected")
            self.assertFalse(output_path.exists())

            approved = subprocess.run(
                base_command
                + [
                    "--structure-policy",
                    "warn",
                    "--approve-structure-review",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            approved_data = json.loads(qa_path.read_text(encoding="utf-8"))
            self.assertEqual(approved.returncode, 0, approved.stderr)
            self.assertTrue(output_path.exists())
            self.assertEqual(approved_data["status"], "review_approved")
            self.assertTrue(approved_data["delivery_ready"])


class FinalizerAtomicWriteTests(unittest.TestCase):
    def make_inputs(self, root: Path) -> tuple[Path, Path]:
        original_path = root / "original.png"
        keyed_path = root / "keyed.png"

        original = Image.new("RGB", (64, 64), "white")
        ImageDraw.Draw(original).rectangle((16, 16, 48, 48), fill=(90, 90, 90))
        original.save(original_path)

        keyed = Image.new("RGB", (64, 64), (0, 255, 0))
        ImageDraw.Draw(keyed).rectangle((16, 16, 48, 48), fill=(90, 90, 90))
        keyed.save(keyed_path)
        return original_path, keyed_path

    def run_finalizer(
        self,
        original: Path,
        source: Path,
        output: Path,
        qa: Path,
        extra_args: list[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "finalize_keyed_product.py"),
            "--source",
            str(source),
            "--original",
            str(original),
            "--output",
            str(output),
            "--qa",
            str(qa),
            "--canvas",
            "256",
            "--structure-policy",
            "off",
        ]
        command.extend(extra_args or [])
        return subprocess.run(command, text=True, capture_output=True, check=False)

    def test_all_declared_paths_are_pairwise_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = ["source", "original", "key-copy", "output", "qa"]
            paths = [root / f"{name}.dat" for name in names]
            for first_index in range(len(paths)):
                for second_index in range(first_index + 1, len(paths)):
                    candidates = list(paths)
                    candidates[second_index] = candidates[first_index]
                    with self.subTest(
                        first=names[first_index],
                        second=names[second_index],
                    ):
                        with self.assertRaises(ValueError):
                            validate_distinct_paths(list(zip(names, candidates)))

    def test_existing_hardlink_alias_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.dat"
            alias = root / "alias.dat"
            source.write_bytes(b"same file")
            try:
                finalize_keyed_product.os.link(source, alias)
            except OSError as error:
                self.skipTest(f"Hard links are unavailable: {error}")

            with self.assertRaises(ValueError):
                validate_distinct_paths([("source", source), ("output", alias)])


    def test_qa_cannot_overwrite_original(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original, keyed = self.make_inputs(root)
            original_before = original.read_bytes()
            output = root / "output.png"

            result = self.run_finalizer(original, keyed, output, original)

            self.assertEqual(result.returncode, 1)
            self.assertEqual(original.read_bytes(), original_before)
            self.assertFalse(output.exists())

    def test_invalid_qa_destination_leaves_no_orphan_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original, keyed = self.make_inputs(root)
            output = root / "output.png"
            qa_directory = root / "qa"
            qa_directory.mkdir()

            result = self.run_finalizer(original, keyed, output, qa_directory)

            self.assertEqual(result.returncode, 1)
            self.assertFalse(output.exists())

    def test_commit_failure_restores_old_files_and_removes_new_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            existing_target = root / "existing.dat"
            new_target = root / "new.dat"
            existing_target.write_bytes(b"old-existing")
            staged_existing = stage_bytes(existing_target, b"new-existing")
            staged_new = stage_bytes(new_target, b"new-file")
            real_replace = finalize_keyed_product.os.replace
            failed = False

            def fail_second_commit(source: str | Path, target: str | Path) -> None:
                nonlocal failed
                is_second_commit = (
                    Path(source) == staged_new[0]
                    and Path(target) == new_target
                    and not failed
                )
                if is_second_commit:
                    failed = True
                    raise OSError("simulated commit failure")
                real_replace(source, target)

            with mock.patch.object(
                finalize_keyed_product.os,
                "replace",
                side_effect=fail_second_commit,
            ):
                with self.assertRaisesRegex(OSError, "simulated commit failure"):
                    commit_staged_files([staged_existing, staged_new])

            self.assertEqual(existing_target.read_bytes(), b"old-existing")
            self.assertFalse(new_target.exists())
            self.assertEqual(list(root.iterdir()), [existing_target])

    def test_success_publishes_all_artifacts_without_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original, keyed = self.make_inputs(root)
            output = root / "output.png"
            qa = root / "qa.json"
            key_copy = root / "keyed-copy.png"

            result = self.run_finalizer(
                original,
                keyed,
                output,
                qa,
                ["--key-copy", str(key_copy)],
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(key_copy.read_bytes(), keyed.read_bytes())
            with Image.open(output) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.size, (256, 256))
            report = json.loads(qa.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "passed")
            self.assertTrue(report["delivery_ready"])
            self.assertEqual(
                sorted(path.name for path in root.iterdir()),
                [
                    "keyed-copy.png",
                    "keyed.png",
                    "original.png",
                    "output.png",
                    "qa.json",
                ],
            )


class SourceCompletenessTests(unittest.TestCase):
    def run_validator(
        self,
        original_root: Path,
        output_root: Path,
        report: Path,
        extra_args: list[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
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
        ]
        command.extend(extra_args or [])
        return subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_review_only_finding_requires_explicit_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            originals = root / "originals" / "family"
            outputs = root / "outputs" / "family"
            originals.mkdir(parents=True)
            outputs.mkdir(parents=True)

            original = Image.new("RGB", (64, 64), "white")
            ImageDraw.Draw(original).rectangle((0, 18, 42, 46), fill=(90, 90, 90))
            original.save(originals / "part.jpg")

            output = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(output).rounded_rectangle(
                (8, 16, 56, 48), radius=10, fill=(100, 100, 100, 255)
            )
            output.save(outputs / "part_beautified.png")

            blocked_report = root / "blocked.json"
            blocked = self.run_validator(root / "originals", root / "outputs", blocked_report)
            self.assertEqual(blocked.returncode, 1)

            approved_report = root / "approved.json"
            approved = self.run_validator(
                root / "originals",
                root / "outputs",
                approved_report,
                ["--approve-structure-review", "family/part_beautified.png"],
            )
            approved_data = json.loads(approved_report.read_text(encoding="utf-8"))
            self.assertEqual(approved.returncode, 0, approved.stderr)
            self.assertTrue(approved_data["delivery_ready"])
            self.assertEqual(approved_data["structure_review_approved_count"], 1)

    def test_hard_structure_failure_cannot_be_approved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            originals = root / "originals" / "family"
            outputs = root / "outputs" / "family"
            originals.mkdir(parents=True)
            outputs.mkdir(parents=True)

            original = Image.new("RGB", (64, 64), "white")
            original_draw = ImageDraw.Draw(original)
            original_draw.rectangle((5, 14, 25, 50), fill=(90, 90, 90))
            original_draw.rectangle((39, 16, 59, 48), fill=(90, 90, 90))
            original.save(originals / "part.jpg")

            output = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(output).rectangle((12, 12, 48, 52), fill=(100, 100, 100, 255))
            output.save(outputs / "part_beautified.png")

            report = root / "hard.json"
            result = self.run_validator(
                root / "originals",
                root / "outputs",
                report,
                [
                    "--structure-policy",
                    "warn",
                    "--approve-structure-review",
                    "family/part_beautified.png",
                ],
            )
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(result.returncode, 1)
            self.assertFalse(data["structure_checks"][0]["review_approved"])
            self.assertFalse(data["delivery_ready"])

    def test_missing_output_fails_then_matching_relative_output_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            originals = root / "originals"
            outputs = root / "outputs"
            family = originals / "family"
            family.mkdir(parents=True)
            outputs.mkdir()
            original = Image.new("RGB", (32, 24), "white")
            ImageDraw.Draw(original).rectangle((8, 4, 23, 19), fill=(120, 130, 140))
            original.save(family / "part.JPG")

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
