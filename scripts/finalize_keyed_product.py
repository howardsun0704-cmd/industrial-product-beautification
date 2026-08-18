from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image


KEY_CHOICES = ("auto", "magenta", "green")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove a green or magenta key, standardize the canvas, and write QA JSON."
    )
    parser.add_argument("--source", type=Path, required=True, help="AI-edited chroma-key image")
    parser.add_argument("--original", type=Path, required=True, help="Read-only source photograph")
    parser.add_argument("--key-copy", type=Path, help="Optional preserved copy of the keyed image")
    parser.add_argument("--output", type=Path, required=True, help="Final transparent PNG")
    parser.add_argument("--qa", type=Path, required=True, help="Per-image QA JSON")
    parser.add_argument("--batch-id", default="default")
    parser.add_argument("--key", choices=KEY_CHOICES, default="auto")
    parser.add_argument("--canvas", type=int, default=2048)
    parser.add_argument("--occupancy", type=float, default=0.90)
    return parser.parse_args()


def border_key_scores(image: Image.Image) -> dict[str, float]:
    rgb = np.asarray(image.convert("RGB"), dtype=np.int16)
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]), axis=0)
    r, g, b = border[:, 0], border[:, 1], border[:, 2]
    return {
        "magenta": float(np.median(np.minimum(r, b) - g)),
        "green": float(np.median(g - np.maximum(r, b))),
    }


def select_key(image: Image.Image, requested: str) -> tuple[str, dict[str, float]]:
    scores = border_key_scores(image)
    if requested != "auto":
        return requested, scores
    selected = max(scores, key=scores.get)
    if scores[selected] < 25:
        raise RuntimeError(
            "Cannot safely detect a green or magenta border key; "
            f"scores={scores}. Specify --key only after visually checking the source."
        )
    return selected, scores


def remove_key(image: Image.Image, key: str) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    rgb = rgba[:, :, :3].astype(np.int16)
    source_alpha = rgba[:, :, 3].astype(np.float32)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

    if key == "magenta":
        dominance = np.minimum(r, b) - g
        strength = np.minimum(r, b)
    else:
        dominance = g - np.maximum(r, b)
        strength = g

    strong = (dominance >= 55) & (strength >= 115)
    fringe = (dominance >= 28) & (strength >= 90) & ~strong
    keyed_alpha = np.full(dominance.shape, 255.0, dtype=np.float32)
    keyed_alpha[strong] = 0.0
    keyed_alpha[fringe] = (
        np.clip((55.0 - dominance[fringe]) / 27.0, 0.0, 1.0) * 255.0
    )
    final_alpha = np.minimum(source_alpha, keyed_alpha)

    affected = strong | fringe
    removal = np.clip(1.0 - keyed_alpha / 255.0, 0.0, 1.0)
    spill = np.maximum(dominance.astype(np.float32), 0.0) * removal
    corrected = rgb.astype(np.float32)

    if key == "magenta":
        for channel in (0, 2):
            corrected[:, :, channel][affected] = np.maximum(
                corrected[:, :, channel][affected] - spill[affected],
                corrected[:, :, 1][affected],
            )
    else:
        corrected[:, :, 1][affected] = np.maximum(
            corrected[:, :, 1][affected] - spill[affected],
            np.minimum(corrected[:, :, 0][affected], corrected[:, :, 2][affected]),
        )

    rgba[:, :, :3] = np.clip(corrected, 0, 255).astype(np.uint8)
    rgba[:, :, 3] = np.clip(final_alpha, 0, 255).astype(np.uint8)
    rgba[rgba[:, :, 3] <= 2, 3] = 0
    rgba[rgba[:, :, 3] == 0, :3] = 0
    return Image.fromarray(rgba, "RGBA")


def resize_premultiplied(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
    alpha = rgba[:, :, 3:4] / 255.0
    premultiplied = np.concatenate((rgba[:, :, :3] * alpha, rgba[:, :, 3:4]), axis=2)
    resized = np.asarray(
        Image.fromarray(np.clip(premultiplied, 0, 255).astype(np.uint8), "RGBA").resize(
            size, Image.Resampling.LANCZOS
        ),
        dtype=np.float32,
    )
    output_alpha = resized[:, :, 3:4]
    output_rgb = np.zeros_like(resized[:, :, :3])
    np.divide(
        resized[:, :, :3] * 255.0,
        output_alpha,
        out=output_rgb,
        where=output_alpha > 0,
    )
    output = np.concatenate((np.clip(output_rgb, 0, 255), output_alpha), axis=2)
    result = output.astype(np.uint8)
    result[result[:, :, 3] == 0, :3] = 0
    return Image.fromarray(result, "RGBA")


def alpha_metrics(image: Image.Image) -> dict[str, object]:
    alpha = image.getchannel("A")
    width, height = image.size
    corners = [
        alpha.getpixel((0, 0)),
        alpha.getpixel((width - 1, 0)),
        alpha.getpixel((0, height - 1)),
        alpha.getpixel((width - 1, height - 1)),
    ]
    histogram = alpha.histogram()
    total = width * height
    bbox = alpha.getbbox()
    return {
        "corner_alpha": corners,
        "transparent_fraction": round(histogram[0] / total, 6),
        "opaque_fraction": round(histogram[255] / total, 6),
        "partially_transparent_pixels": total - histogram[0] - histogram[255],
        "product_bbox": list(bbox) if bbox else None,
    }


def main() -> None:
    args = parse_args()
    if args.canvas < 256:
        raise ValueError("--canvas must be at least 256")
    if not 0.10 <= args.occupancy <= 0.98:
        raise ValueError("--occupancy must be between 0.10 and 0.98")
    if args.output.suffix.lower() != ".png":
        raise ValueError("--output must use the .png extension")
    if not args.source.is_file() or not args.original.is_file():
        raise FileNotFoundError("Both --source and --original must be readable files")
    if args.output.resolve() in {args.source.resolve(), args.original.resolve()}:
        raise ValueError("--output must not overwrite the source or original image")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.qa.parent.mkdir(parents=True, exist_ok=True)
    if args.key_copy:
        if args.key_copy.resolve() in {args.source.resolve(), args.original.resolve()}:
            raise ValueError("--key-copy must not overwrite a source file")
        args.key_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.source, args.key_copy)

    with Image.open(args.source) as source:
        source.load()
        selected_key, key_scores = select_key(source, args.key)
        transparent = remove_key(source, selected_key)

    alpha = transparent.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise RuntimeError("Chroma keying removed the entire image")
    cropped = transparent.crop(bbox)

    max_extent = int(round(args.canvas * args.occupancy))
    scale = min(max_extent / cropped.width, max_extent / cropped.height)
    target_size = (
        max(1, int(round(cropped.width * scale))),
        max(1, int(round(cropped.height * scale))),
    )
    resized = resize_premultiplied(cropped, target_size)
    canvas = Image.new("RGBA", (args.canvas, args.canvas), (0, 0, 0, 0))
    offset = ((args.canvas - target_size[0]) // 2, (args.canvas - target_size[1]) // 2)
    canvas.alpha_composite(resized, offset)

    metrics = alpha_metrics(canvas)
    passed = (
        metrics["corner_alpha"] == [0, 0, 0, 0]
        and metrics["transparent_fraction"] >= 0.03
        and metrics["opaque_fraction"] >= 0.01
        and metrics["product_bbox"] is not None
    )
    if not passed:
        raise RuntimeError(f"Alpha validation failed: {metrics}")

    canvas.save(args.output, format="PNG", optimize=True)
    report = {
        "batch_id": args.batch_id,
        "original": str(args.original.resolve()),
        "source": str(args.source.resolve()),
        "key_copy": str(args.key_copy.resolve()) if args.key_copy else None,
        "output": str(args.output.resolve()),
        "selected_key": selected_key,
        "border_key_scores": {key: round(value, 3) for key, value in key_scores.items()},
        "width": args.canvas,
        "height": args.canvas,
        "mode": "RGBA",
        "target_occupancy": args.occupancy,
        **metrics,
        "automatic_checks_passed": True,
        "visual_structure_check_required": True,
    }
    args.qa.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()

