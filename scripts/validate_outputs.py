from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


DEFAULT_SOURCE_EXTENSIONS = (
    ".bmp",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
)
DEFAULT_EXCLUDED_DIRS = (
    ".git",
    "__pycache__",
    "_批次复核",
    "_质量检查",
    "keyed",
    "outputs",
    "qa",
    "美化成品_透明PNG",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate transparent product PNG delivery.")
    parser.add_argument("--root", type=Path, required=True, help="Final output directory")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--expected", type=int, help="Legacy manual count check")
    parser.add_argument("--canvas", type=int, default=2048)
    parser.add_argument("--pattern", default="*_beautified.png")
    parser.add_argument(
        "--original-root",
        type=Path,
        help=(
            "Source image directory. When provided, expected outputs are derived from "
            "source-relative paths and --expected is only a cross-check."
        ),
    )
    parser.add_argument(
        "--source-extension",
        action="append",
        help="Repeat to override source extensions, for example --source-extension .jpg",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Additional source directory name to exclude; repeat as needed.",
    )
    parser.add_argument(
        "--allow-unreadable-originals",
        action="store_true",
        help="Report unreadable originals without failing the validation.",
    )
    return parser.parse_args()


def normalized_extensions(values: list[str] | None) -> set[str]:
    selected = values or list(DEFAULT_SOURCE_EXTENSIONS)
    return {
        value.casefold() if value.startswith(".") else f".{value.casefold()}"
        for value in selected
    }


def relative_key(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix().casefold()


def discover_originals(
    root: Path,
    extensions: set[str],
    excluded_dirs: set[str],
) -> list[Path]:
    originals: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in extensions:
            continue
        relative_parent_parts = path.relative_to(root).parts[:-1]
        if any(part.casefold() in excluded_dirs for part in relative_parent_parts):
            continue
        originals.append(path)
    return sorted(originals, key=lambda path: relative_key(path, root))


def check_originals(paths: list[Path]) -> tuple[list[Path], list[dict[str, str]]]:
    readable: list[Path] = []
    unreadable: list[dict[str, str]] = []
    for path in paths:
        try:
            with Image.open(path) as image:
                image.verify()
            readable.append(path)
        except Exception as exc:
            unreadable.append({"file": str(path.resolve()), "error": str(exc)})
    return readable, unreadable


def expected_output_relative(original: Path, original_root: Path) -> Path:
    relative = original.relative_to(original_root)
    return relative.with_name(f"{relative.stem}_beautified.png")


def build_expected_outputs(
    originals: list[Path],
    original_root: Path,
) -> tuple[dict[str, tuple[Path, Path]], list[dict[str, object]]]:
    expected: dict[str, tuple[Path, Path]] = {}
    collisions: dict[str, list[Path]] = {}
    for original in originals:
        relative = expected_output_relative(original, original_root)
        key = relative.as_posix().casefold()
        if key in expected:
            collisions.setdefault(key, [expected[key][0]]).append(original)
        else:
            expected[key] = (original, relative)

    collision_records = [
        {
            "output": key,
            "originals": [str(path.resolve()) for path in paths],
        }
        for key, paths in sorted(collisions.items())
    ]
    return expected, collision_records


def validate_output(path: Path, canvas: int) -> tuple[list[str], float | None, float | None]:
    issues: list[str] = []
    transparent_fraction: float | None = None
    opaque_fraction: float | None = None
    try:
        with Image.open(path) as image:
            image.load()
            file_format = image.format
            if file_format != "PNG":
                issues.append(f"format={file_format}")
            if image.size != (canvas, canvas):
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
    return issues, transparent_fraction, opaque_fraction


def main() -> None:
    args = parse_args()
    if not args.root.is_dir():
        raise NotADirectoryError(args.root)
    if args.original_root is not None and not args.original_root.is_dir():
        raise NotADirectoryError(args.original_root)

    files = sorted(
        (path for path in args.root.rglob(args.pattern) if path.is_file()),
        key=lambda path: relative_key(path, args.root),
    )
    failures: list[dict[str, object]] = []
    transparent_fractions: list[float] = []
    opaque_fractions: list[float] = []

    for path in files:
        issues, transparent_fraction, opaque_fraction = validate_output(path, args.canvas)
        if transparent_fraction is not None:
            transparent_fractions.append(transparent_fraction)
        if opaque_fraction is not None:
            opaque_fractions.append(opaque_fraction)
        if issues:
            failures.append({"file": str(path.resolve()), "issues": issues})

    source_count: int | None = None
    readable_source_count: int | None = None
    unreadable_originals: list[dict[str, str]] = []
    missing_outputs: list[str] = []
    unexpected_outputs: list[str] = []
    duplicate_expected_outputs: list[dict[str, object]] = []
    derived_expected_count: int | None = None

    if args.original_root is not None:
        extensions = normalized_extensions(args.source_extension)
        excluded = {name.casefold() for name in DEFAULT_EXCLUDED_DIRS}
        excluded.update(name.casefold() for name in args.exclude_dir)
        originals = discover_originals(args.original_root, extensions, excluded)
        readable_originals, unreadable_originals = check_originals(originals)
        source_count = len(originals)
        readable_source_count = len(readable_originals)

        expected, duplicate_expected_outputs = build_expected_outputs(
            readable_originals,
            args.original_root,
        )
        derived_expected_count = len(expected)
        actual = {relative_key(path, args.root): path for path in files}

        missing_keys = sorted(set(expected) - set(actual))
        unexpected_keys = sorted(set(actual) - set(expected))
        missing_outputs = [expected[key][1].as_posix() for key in missing_keys]
        unexpected_outputs = [actual[key].relative_to(args.root).as_posix() for key in unexpected_keys]

        for key in missing_keys:
            original, relative = expected[key]
            failures.append(
                {
                    "file": str((args.root / relative).resolve()),
                    "source": str(original.resolve()),
                    "issues": ["missing_output"],
                }
            )
        for key in unexpected_keys:
            failures.append(
                {
                    "file": str(actual[key].resolve()),
                    "issues": ["unexpected_output_or_wrong_relative_path"],
                }
            )
        for collision in duplicate_expected_outputs:
            failures.append(
                {
                    "file": str(args.original_root.resolve()),
                    "issues": ["multiple_originals_map_to_one_output"],
                    **collision,
                }
            )
        if unreadable_originals and not args.allow_unreadable_originals:
            for item in unreadable_originals:
                failures.append(
                    {
                        "file": item["file"],
                        "issues": [f"unreadable_original={item['error']}"],
                    }
                )
        if args.expected is not None and args.expected != derived_expected_count:
            failures.append(
                {
                    "file": str(args.original_root.resolve()),
                    "issues": [
                        f"manual_expected={args.expected}, derived_expected={derived_expected_count}"
                    ],
                }
            )
    elif args.expected is not None and len(files) != args.expected:
        failures.append(
            {
                "file": str(args.root.resolve()),
                "issues": [f"count={len(files)}, expected={args.expected}"],
            }
        )

    expected_count = derived_expected_count if derived_expected_count is not None else args.expected
    report = {
        "root": str(args.root.resolve()),
        "original_root": str(args.original_root.resolve()) if args.original_root else None,
        "pattern": args.pattern,
        "source_completeness_checked": args.original_root is not None,
        "source_count": source_count,
        "readable_source_count": readable_source_count,
        "unreadable_original_count": len(unreadable_originals),
        "unreadable_originals": unreadable_originals,
        "expected_count": expected_count,
        "actual_count": len(files),
        "missing_output_count": len(missing_outputs),
        "missing_outputs": missing_outputs,
        "unexpected_output_count": len(unexpected_outputs),
        "unexpected_outputs": unexpected_outputs,
        "duplicate_expected_outputs": duplicate_expected_outputs,
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
