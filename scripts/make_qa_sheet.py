from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build before/after sheets from per-image QA JSON.")
    parser.add_argument("--qa-root", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=2)
    parser.add_argument("--max-items", type=int, default=0)
    return parser.parse_args()


def get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    )
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def checker(size: tuple[int, int], cell: int = 18) -> Image.Image:
    image = Image.new("RGB", size, (238, 238, 238))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle(
                    (x, y, min(x + cell - 1, size[0] - 1), min(y + cell - 1, size[1] - 1)),
                    fill=(211, 211, 211),
                )
    return image


def render_panel(path: Path, size: int) -> Image.Image:
    panel = checker((size, size))
    with Image.open(path) as source:
        image = source.convert("RGBA")
        image.thumbnail((size - 20, size - 20), Image.Resampling.LANCZOS)
    offset = ((size - image.width) // 2, (size - image.height) // 2)
    panel.paste(image, offset, image)
    return panel


def load_reports(root: Path, batch_id: str) -> list[dict[str, object]]:
    reports: list[dict[str, object]] = []
    for path in root.rglob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("batch_id") == batch_id:
            reports.append(data)
    reports.sort(key=lambda item: str(item.get("original", "")))
    return reports


def main() -> None:
    args = parse_args()
    if args.columns < 1 or args.columns > 4:
        raise ValueError("--columns must be between 1 and 4")
    reports = load_reports(args.qa_root, args.batch_id)
    if args.max_items > 0:
        reports = reports[: args.max_items]
    if not reports:
        raise RuntimeError(f"No QA reports found for batch {args.batch_id}")

    panel_size = 300
    card_width = 680
    card_height = 400
    header_height = 74
    rows = math.ceil(len(reports) / args.columns)
    canvas = Image.new(
        "RGB",
        (card_width * args.columns, header_height + card_height * rows),
        (248, 248, 248),
    )
    draw = ImageDraw.Draw(canvas)
    title_font = get_font(28)
    label_font = get_font(18)
    small_font = get_font(15)
    draw.text(
        (24, 20),
        f"Industrial product QA | batch {args.batch_id} | {len(reports)} item(s)",
        fill=(28, 28, 28),
        font=title_font,
    )

    for index, report in enumerate(reports):
        row, column = divmod(index, args.columns)
        x0 = column * card_width
        y0 = header_height + row * card_height
        original = Path(str(report["original"]))
        output = Path(str(report["output"]))

        draw.rounded_rectangle(
            (x0 + 12, y0 + 10, x0 + card_width - 12, y0 + card_height - 10),
            radius=12,
            fill=(255, 255, 255),
            outline=(220, 220, 220),
        )
        draw.text((x0 + 28, y0 + 22), original.name[:64], fill=(35, 35, 35), font=label_font)
        canvas.paste(render_panel(original, panel_size), (x0 + 28, y0 + 68))
        canvas.paste(render_panel(output, panel_size), (x0 + 352, y0 + 68))
        draw.text((x0 + 150, y0 + 372), "BEFORE", fill=(75, 75, 75), font=small_font)
        draw.text((x0 + 472, y0 + 372), "AFTER / ALPHA", fill=(75, 75, 75), font=small_font)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, format="PNG", optimize=True)
    print(f"wrote={args.output.resolve()} items={len(reports)}")


if __name__ == "__main__":
    main()

