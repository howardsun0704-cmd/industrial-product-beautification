from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a set of transparent product PNGs.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--expected", type=int)
    parser.add_argument("--canvas", type=int, default=2048)
    parser.add_argument("--pattern", default="*_beautified.png")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.root.is_dir():
        raise NotADirectoryError(args.root)

    files = sorted(path for path in args.root.rglob(args.pattern) if path.is_file())
    failures: list[dict[str, object]] = []
    transparent_fractions: list[float] = []
    opaque_fractions: list[float] = []

    for path in files:
        issues: list[str] = []
        try:
            with Image.open(path) as image:
                image.load()
                file_format = image.format
                if file_format != "PNG":
                    issues.append(f"format={file_format}")
                if image.size != (args.canvas, args.canvas):
                    issues.append(f"size={image.size}")
                if image.mode != "RGBA":
                    issues.append(f"mode={image.mode}")
                rgba = image if image.mode == "RGBA" else image.convert("RGBA")
                alpha = rgba.getchannel("A")
                width, height = rgba.size
                corners = [
                    alpha.getpixel((0, 0)),
                    alpha.getpixel((width - 1, 0)),
                    alpha.getpixel((0, height - 1)),
                    alpha.getpixel((width - 1, height - 1)),
                ]
                if corners != [0, 0, 0, 0]:
                    issues.append(f"corner_alpha={corners}")

                histogram = alpha.histogram()
                total = width * height
                transparent_fraction = histogram[0] / total
                opaque_fraction = histogram[255] / total
                transparent_fractions.append(transparent_fraction)
                opaque_fractions.append(opaque_fraction)
                if transparent_fraction <= 0:
                    issues.append("no_fully_transparent_pixels")
                if opaque_fraction <= 0:
                    issues.append("no_fully_opaque_pixels")

                bbox = alpha.getbbox()
                if bbox is None:
                    issues.append("empty_alpha")
                elif bbox[0] <= 0 or bbox[1] <= 0 or bbox[2] >= width or bbox[3] >= height:
                    issues.append(f"product_touches_canvas_edge={bbox}")
        except Exception as exc:
            issues.append(f"unreadable={exc}")

        if issues:
            failures.append({"file": str(path.resolve()), "issues": issues})

    if args.expected is not None and len(files) != args.expected:
        failures.append(
            {
                "file": str(args.root.resolve()),
                "issues": [f"count={len(files)}, expected={args.expected}"],
            }
        )

    report = {
        "root": str(args.root.resolve()),
        "pattern": args.pattern,
        "expected_count": args.expected,
        "actual_count": len(files),
        "canvas": args.canvas,
        "automatic_checks_passed": not failures,
        "visual_structure_check_required": True,
        "transparent_fraction_range": [
            round(min(transparent_fractions), 6) if transparent_fractions else None,
            round(max(transparent_fractions), 6) if transparent_fractions else None,
        ],
        "opaque_fraction_range": [
            round(min(opaque_fractions), 6) if opaque_fractions else None,
            round(max(opaque_fractions), 6) if opaque_fractions else None,
        ],
        "failures": failures,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()

