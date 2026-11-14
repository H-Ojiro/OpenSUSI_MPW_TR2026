#!/usr/bin/env python3
# ----- ------ ----- ----- ------ ----- ----- -----
# OpenSUSI - SVG Tile Preview Generator
# LICENSE: Apache License Version 2.0
# ----- ------ ----- ----- ------ ----- ----- -----
import argparse
import html
import json
from pathlib import Path
from typing import Any

import klayout.db as pya

DEFAULT_MANIFEST = Path("project/manifest.json")
DEFAULT_OUTPUT_DIR = Path("tile-previews")

LAYER_COLORS = (
    "#1f2937",
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#9333ea",
    "#ea580c",
    "#0891b2",
    "#4b5563",
)
PADDING_RATIO = 0.04


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def polygon_path(polygon: Any) -> str:
    """Create SVG path data for a KLayout polygon, including any holes."""
    contours = [polygon.each_point_hull()]
    contours.extend(
        polygon.each_point_hole(index)
        for index in range(polygon.holes())
    )

    commands: list[str] = []
    for contour in contours:
        points = list(contour)
        if not points:
            continue

        commands.append(f"M {points[0].x} {points[0].y}")
        commands.extend(f"L {point.x} {point.y}" for point in points[1:])
        commands.append("Z")

    return " ".join(commands)


def render_preview(gds_path: Path, output_path: Path, label: str) -> None:
    layout = pya.Layout()
    layout.read(str(gds_path))

    top_cells = list(layout.top_cells())
    if len(top_cells) != 1:
        raise RuntimeError(
            f"Expected one top cell in {gds_path}, found {len(top_cells)}"
        )
    top_cell = top_cells[0]

    layer_polygons: list[tuple[str, list[Any]]] = []
    all_polygons: list[Any] = []

    for layer_index in layout.layer_indices():
        region = pya.Region(top_cell.begin_shapes_rec(layer_index))
        polygons = list(region.each())
        if not polygons:
            continue

        color = LAYER_COLORS[len(layer_polygons) % len(LAYER_COLORS)]
        layer_polygons.append((color, polygons))
        all_polygons.extend(polygons)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not all_polygons:
        safe_label = html.escape(label)
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'width="240" height="160" viewBox="0 0 240 160">'
            '<rect width="240" height="160" fill="#f3f4f6"/>'
            '<text x="120" y="82" text-anchor="middle" '
            'font-family="sans-serif" font-size="14" fill="#6b7280">'
            f"{safe_label} (no geometry)</text></svg>"
        )
        output_path.write_text(svg + "\n", encoding="utf-8")
        return

    bbox = all_polygons[0].bbox()
    for polygon in all_polygons[1:]:
        bbox += polygon.bbox()

    width = max(1, bbox.width())
    height = max(1, bbox.height())
    padding = max(1, int(max(width, height) * PADDING_RATIO))
    view_x = bbox.left - padding
    view_y = bbox.top - padding
    view_width = width + 2 * padding
    view_height = height + 2 * padding

    safe_label = html.escape(label)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="240" height="160" '
        f'viewBox="{view_x} {view_y} {view_width} {view_height}" '
        'preserveAspectRatio="xMidYMid meet">',
        f'<title>{safe_label}</title>',
        f'<rect x="{view_x}" y="{view_y}" '
        f'width="{view_width}" height="{view_height}" fill="white"/>',
    ]

    for color, polygons in layer_polygons:
        paths = "".join(
            f'<path d="{polygon_path(polygon)}"/>'
            for polygon in polygons
        )
        parts.append(
            f'<g fill="{color}" fill-rule="evenodd">{paths}</g>'
        )

    parts.append("</svg>")
    output_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def generate_previews(manifest: dict[str, Any], output_dir: Path) -> int:
    generated = 0

    for entry in manifest.get("entries", []):
        row = entry.get("row")
        col = entry.get("col")
        gds_value = entry.get("gdsFile")

        if row is None or col is None or not gds_value:
            continue

        gds_path = Path(gds_value)
        if not gds_path.is_file():
            raise FileNotFoundError(
                f"GDS for tile ({col},{row}) not found: {gds_path}"
            )

        output_path = output_dir / f"tile-{col}-{row}" / "tile-preview.svg"
        render_preview(gds_path, output_path, f"Tile ({col},{row})")
        generated += 1

    return generated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate per-tile SVG previews from GDS files"
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    count = generate_previews(manifest, args.output_dir)
    print(f"Generated {count} SVG tile preview(s) in {args.output_dir}")


if __name__ == "__main__":
    main()
