from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


DEFAULT_ANALYSIS_SIZE = 384


def _analysis_copy(image: Image.Image, max_side: int) -> Image.Image:
    copy = image.convert("RGBA")
    if max(copy.size) > max_side:
        copy.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return copy


def _source_foreground(image: Image.Image) -> tuple[np.ndarray, dict[str, object]]:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    alpha = rgba[:, :, 3]
    transparent_fraction = float(np.count_nonzero(alpha <= 8) / alpha.size)
    if transparent_fraction >= 0.01:
        return alpha >= 48, {
            "mask_source": "alpha",
            "background_tolerance": None,
            "source_transparent_fraction": round(transparent_fraction, 6),
        }

    rgb = rgba[:, :, :3].astype(np.int16)
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]), axis=0)
    background = np.median(border, axis=0)
    distance = np.max(np.abs(rgb - background), axis=2)
    border_distance = np.max(np.abs(border - background), axis=1)
    tolerance = int(np.clip(max(18, np.percentile(border_distance, 95) + 10), 18, 58))
    foreground = distance > tolerance
    return foreground, {
        "mask_source": "estimated_border_color",
        "background_rgb": [int(round(value)) for value in background],
        "background_tolerance": tolerance,
        "source_transparent_fraction": 0.0,
    }


def _output_foreground(image: Image.Image) -> tuple[np.ndarray, dict[str, object]]:
    alpha = np.asarray(image.convert("RGBA").getchannel("A"), dtype=np.uint8)
    return alpha >= 48, {
        "mask_source": "alpha",
        "alpha_foreground_threshold": 48,
    }


def _morph(mask: np.ndarray, operation: str, size: int) -> np.ndarray:
    size = max(3, size | 1)
    image = Image.fromarray(mask.astype(np.uint8) * 255, "L")
    if operation == "dilate":
        filtered = image.filter(ImageFilter.MaxFilter(size))
    elif operation == "erode":
        filtered = image.filter(ImageFilter.MinFilter(size))
    else:
        raise ValueError(operation)
    return np.asarray(filtered, dtype=np.uint8) > 0


def _components(mask: np.ndarray) -> list[dict[str, object]]:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[dict[str, object]] = []
    for y, x in np.argwhere(mask):
        y = int(y)
        x = int(x)
        if visited[y, x]:
            continue
        queue: deque[tuple[int, int]] = deque([(y, x)])
        visited[y, x] = True
        area = 0
        perimeter = 0
        x0 = x1 = x
        y0 = y1 = y
        while queue:
            cy, cx = queue.popleft()
            area += 1
            x0 = min(x0, cx)
            x1 = max(x1, cx)
            y0 = min(y0, cy)
            y1 = max(y1, cy)
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if not (0 <= ny < height and 0 <= nx < width) or not mask[ny, nx]:
                    perimeter += 1
                elif not visited[ny, nx]:
                    visited[ny, nx] = True
                    queue.append((ny, nx))
        components.append(
            {
                "area": area,
                "perimeter": perimeter,
                "compactness": round(
                    (perimeter * perimeter) / max(1.0, 4.0 * np.pi * area),
                    6,
                ),
                "bbox": [x0, y0, x1 + 1, y1 + 1],
                "touches_border": x0 == 0 or y0 == 0 or x1 == width - 1 or y1 == height - 1,
            }
        )
    return components


def _bbox(mask: np.ndarray) -> list[int] | None:
    coordinates = np.argwhere(mask)
    if not len(coordinates):
        return None
    y0, x0 = coordinates.min(axis=0)
    y1, x1 = coordinates.max(axis=0)
    return [int(x0), int(y0), int(x1 + 1), int(y1 + 1)]


def _edge_contacts(mask: np.ndarray) -> list[str]:
    foreground_area = int(np.count_nonzero(mask))
    if foreground_area == 0:
        return []
    minimum = max(3, int(round(foreground_area * 0.0015)))
    band = max(1, int(round(min(mask.shape) * 0.006)))
    counts = {
        "top": int(np.count_nonzero(mask[:band, :])),
        "bottom": int(np.count_nonzero(mask[-band:, :])),
        "left": int(np.count_nonzero(mask[:, :band])),
        "right": int(np.count_nonzero(mask[:, -band:])),
    }
    return [edge for edge, count in counts.items() if count >= minimum]


def _major_components(mask: np.ndarray) -> tuple[int, list[dict[str, object]]]:
    merge_size = min(11, max(3, int(round(min(mask.shape) * 0.012)) | 1))
    merged = _morph(mask, "dilate", merge_size)
    components = _components(merged)
    if not components:
        return 0, []
    largest = max(int(component["area"]) for component in components)
    minimum = max(24, int(round(largest * 0.07)), int(round(mask.size * 0.0015)))
    major = [component for component in components if int(component["area"]) >= minimum]
    major.sort(key=lambda component: int(component["area"]), reverse=True)
    return len(major), major


def _holes(mask: np.ndarray) -> tuple[int, int, list[dict[str, object]]]:
    # Close tiny segmentation gaps so a real opening remains enclosed, while keeping
    # the raw hole area sensitive to opaque residue left inside that opening.
    closed = _morph(_morph(mask, "dilate", 3), "erode", 3)
    background_components = _components(~closed)
    foreground_bbox = _bbox(closed)
    if foreground_bbox is None:
        return 0, 0, []
    x0, y0, x1, y1 = foreground_bbox
    bbox_area = max(1, (x1 - x0) * (y1 - y0))
    minimum = max(16, int(round(bbox_area * 0.0015)))
    holes = [
        component
        for component in background_components
        if not bool(component["touches_border"]) and int(component["area"]) >= minimum
    ]
    holes.sort(key=lambda component: int(component["area"]), reverse=True)
    return len(holes), sum(int(component["area"]) for component in holes), holes


def analyze_mask(mask: np.ndarray, metadata: dict[str, object]) -> dict[str, object]:
    bbox = _bbox(mask)
    major_count, major_components = _major_components(mask)
    hole_count, hole_area, holes = _holes(mask)
    foreground_area = int(np.count_nonzero(mask))
    if bbox is None:
        bbox_area = 0
        aspect_ratio = None
    else:
        x0, y0, x1, y1 = bbox
        bbox_area = (x1 - x0) * (y1 - y0)
        aspect_ratio = round((x1 - x0) / max(1, y1 - y0), 6)
    return {
        **metadata,
        "analysis_size": [int(mask.shape[1]), int(mask.shape[0])],
        "foreground_area": foreground_area,
        "foreground_bbox": bbox,
        "foreground_aspect_ratio": aspect_ratio,
        "foreground_fraction": round(foreground_area / mask.size, 6),
        "edge_contacts": _edge_contacts(mask),
        "major_component_count": major_count,
        "major_components": major_components,
        "hole_count": hole_count,
        "hole_area": hole_area,
        "hole_fraction_of_bbox": round(hole_area / max(1, bbox_area), 6),
        "holes": holes,
    }


def analyze_source(image: Image.Image, max_side: int = DEFAULT_ANALYSIS_SIZE) -> dict[str, object]:
    prepared = _analysis_copy(image, max_side)
    mask, metadata = _source_foreground(prepared)
    return analyze_mask(mask, metadata)


def analyze_output(image: Image.Image, max_side: int = DEFAULT_ANALYSIS_SIZE) -> dict[str, object]:
    prepared = _analysis_copy(image, max_side)
    mask, metadata = _output_foreground(prepared)
    return analyze_mask(mask, metadata)


def compare_structure_images(
    original: Image.Image,
    output: Image.Image,
    max_side: int = DEFAULT_ANALYSIS_SIZE,
) -> dict[str, object]:
    source = analyze_source(original, max_side)
    result = analyze_output(output, max_side)
    findings: list[dict[str, object]] = []

    source_area = int(source["foreground_area"])
    output_area = int(result["foreground_area"])
    if source_area == 0:
        findings.append(
            {
                "code": "source_foreground_not_detected",
                "severity": "review",
                "detail": "Could not derive a reliable foreground mask from the original.",
            }
        )
    if output_area == 0:
        findings.append(
            {
                "code": "output_foreground_empty",
                "severity": "fail",
                "detail": "The output alpha contains no product foreground.",
            }
        )

    source_components = int(source["major_component_count"])
    output_components = int(result["major_component_count"])
    if source_components >= 2 and output_components < source_components:
        findings.append(
            {
                "code": "major_component_count_decreased",
                "severity": "fail",
                "source": source_components,
                "output": output_components,
                "detail": "One or more major product subjects may be missing.",
            }
        )
    elif source_components >= 1 and output_components > source_components:
        findings.append(
            {
                "code": "major_component_count_increased",
                "severity": "review",
                "source": source_components,
                "output": output_components,
                "detail": "The output may contain an added or split product subject.",
            }
        )

    source_holes = int(source["hole_count"])
    output_holes = int(result["hole_count"])
    source_hole_fraction = float(source["hole_fraction_of_bbox"])
    output_hole_fraction = float(result["hole_fraction_of_bbox"])
    if source_holes > output_holes:
        findings.append(
            {
                "code": "enclosed_hole_count_decreased",
                "severity": "fail",
                "source": source_holes,
                "output": output_holes,
                "detail": "A source-visible opening is no longer transparent in the output.",
            }
        )
    elif output_holes > source_holes:
        findings.append(
            {
                "code": "enclosed_hole_count_increased",
                "severity": "review",
                "source": source_holes,
                "output": output_holes,
                "detail": "The output may contain an invented opening or over-removed product area.",
            }
        )
    if source_holes > 0 and source_hole_fraction > 0:
        ratio = output_hole_fraction / source_hole_fraction
        if ratio < 0.60:
            findings.append(
                {
                    "code": "transparent_hole_area_collapsed",
                    "severity": "fail",
                    "ratio": round(ratio, 6),
                    "detail": "Transparent opening area is far smaller than in the source.",
                }
            )
        elif ratio < 0.86:
            findings.append(
                {
                    "code": "transparent_hole_area_reduced",
                    "severity": "review",
                    "ratio": round(ratio, 6),
                    "detail": "Possible opaque residue remains inside an opening.",
                }
            )

    if source_holes > 0 and output_holes > 0:
        source_compactness = float(source["holes"][0]["compactness"])
        output_compactness = float(result["holes"][0]["compactness"])
        compactness_ratio = output_compactness / max(0.000001, source_compactness)
        if compactness_ratio > 1.20 and output_compactness - source_compactness > 0.35:
            findings.append(
                {
                    "code": "transparent_hole_edge_fragmented",
                    "severity": "review",
                    "ratio": round(compactness_ratio, 6),
                    "detail": "The output opening edge is unusually fragmented; inspect for residue.",
                }
            )

    source_edges = list(source["edge_contacts"])
    if source_edges:
        findings.append(
            {
                "code": "source_crop_requires_review",
                "severity": "review",
                "edges": source_edges,
                "detail": (
                    "The original product meets a frame edge. Do not reconstruct geometry "
                    "outside the source; preserve the visible crop during visual review."
                ),
            }
        )

    source_aspect = source["foreground_aspect_ratio"]
    output_aspect = result["foreground_aspect_ratio"]
    if source_aspect and output_aspect and not source_edges:
        ratio = max(float(source_aspect), float(output_aspect)) / max(
            0.000001, min(float(source_aspect), float(output_aspect))
        )
        if ratio > 1.35:
            findings.append(
                {
                    "code": "foreground_aspect_ratio_changed",
                    "severity": "review",
                    "ratio": round(ratio, 6),
                    "detail": (
                        "The output silhouette proportions differ substantially from the source."
                    ),
                }
            )

    return {
        "source": source,
        "output": result,
        "findings": findings,
        "hard_failure": any(item["severity"] == "fail" for item in findings),
        "review_required": bool(findings),
    }


def compare_structure_files(
    original: Path,
    output: Path,
    max_side: int = DEFAULT_ANALYSIS_SIZE,
) -> dict[str, object]:
    with Image.open(original) as original_image, Image.open(output) as output_image:
        original_image.load()
        output_image.load()
        return compare_structure_images(original_image, output_image, max_side)
