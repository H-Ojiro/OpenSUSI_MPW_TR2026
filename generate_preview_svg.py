#!/usr/bin/env python3
"""Render submitted GDSII layouts as image tiles in PREVIEW.svg."""

import argparse
import base64
import io
import json
from html import escape
from pathlib import Path

import klayout.db as kdb
from PIL import Image, ImageDraw

TILE_W, TILE_H = 140, 90
MARGIN, HEADER_H, ROW_LABEL_W = 30, 40, 30
IMAGE_W, IMAGE_H = TILE_W, TILE_H
TARGET_LAYER = (20, 0)
TARGET_COLOR = "#1d4f91"


def render_gds(gds_path: Path, top_name: str | None) -> str:
    layout = kdb.Layout()
    layout.read(str(gds_path))

    cell = layout.cell(top_name) if top_name else layout.top_cell()
    if cell is None:
        raise ValueError(f"No top cell in {gds_path}")

    layer_index = layout.layer(kdb.LayerInfo(*TARGET_LAYER))
    if layer_index is None:
        return ""

    bbox = None
    iterator = cell.begin_shapes_rec(layer_index)
    while not iterator.at_end():
        shape = iterator.shape()
        if shape.is_box() or shape.is_polygon() or shape.is_path() or shape.is_simple_polygon():
            if bbox is None:
                bbox = shape.bbox()
            else:
                bbox += shape.bbox()
        iterator.next()

    if bbox is None or bbox.empty():
        return ""

    image = Image.new("RGB", (IMAGE_W, IMAGE_H), "white")
    draw = ImageDraw.Draw(image)
    width = max(1, bbox.width())
    height = max(1, bbox.height())
    scale = min(IMAGE_W / width, IMAGE_H / height)
    offset_x = (IMAGE_W - width * scale) / 2
    offset_y = (IMAGE_H - height * scale) / 2

    def to_xy(point):
        return (
            round(offset_x + (point.x - bbox.left) * scale),
            round(offset_y + (bbox.top - point.y) * scale),
        )

    iterator = cell.begin_shapes_rec(layer_index)
    while not iterator.at_end():
        shape = iterator.shape()
        if shape.is_box() or shape.is_polygon() or shape.is_path() or shape.is_simple_polygon():
            polygon = shape.polygon.transformed(iterator.trans())
            points = [to_xy(point) for point in polygon.each_point_hull()]
            if len(points) >= 3:
                draw.polygon(points, fill=TARGET_COLOR)
        iterator.next()

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return base64.b64encode(output.getvalue()).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("project/manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("PREVIEW.svg"))
    parser.add_argument("--repo-owner", default="H-Ojiro")
    parser.add_argument("--repo-name", default="OpenSUSI_MPW_TR2026")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--update-readme", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    grid = manifest.get("grid", {})
    cols, rows = int(grid.get("x", 8)), int(grid.get("y", 8))
    width = ROW_LABEL_W + 2 * MARGIN + cols * TILE_W
    height = HEADER_H + 2 * MARGIN + rows * TILE_H

    entries = {
        (entry.get("col"), entry.get("row")): entry
        for entry in manifest.get("entries", [])
        if entry.get("type") in {"teg", "user", "fill"}
        and entry.get("col") is not None and entry.get("row") is not None
    }

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#111}.grid-label{font-size:12px}.tile{fill:none;stroke:#555;stroke-width:1}</style>',
        f'<text x="{MARGIN}" y="{MARGIN}" font-size="18" font-weight="bold">OpenSUSI MPW Layout Preview (Layer 20/0)</text>',
    ]

    for col in range(cols):
        x = ROW_LABEL_W + MARGIN + col * TILE_W
        svg.append(f'<text class="grid-label" x="{x + TILE_W / 2}" y="{HEADER_H + 15}" text-anchor="middle">{col}</text>')

    for row in range(rows):
        y = HEADER_H + MARGIN + row * TILE_H
        svg.append(f'<text class="grid-label" x="{ROW_LABEL_W + MARGIN - 10}" y="{y + TILE_H / 2}" text-anchor="end" dominant-baseline="middle">{row}</text>')

    for row in range(rows):
        for col in range(cols):
            x = ROW_LABEL_W + MARGIN + col * TILE_W
            y = HEADER_H + MARGIN + row * TILE_H
            entry = entries.get((col, row))
            if entry:
                gds_file = entry.get("gdsFile")
                gds_path = Path(gds_file) if gds_file else None
                if gds_path and gds_path.is_file():
                    try:
                        png = render_gds(gds_path, entry.get("gdsTopCell"))
                    except Exception as error:
                        print(f"Warning: could not render {gds_path}: {error}")
                        png = ""

                    if png:
                        href = f"https://github.com/{args.repo_owner}/{args.repo_name}/tree/{args.branch}/{gds_path.parent.as_posix()}"
                        svg.append(f'<a href="{escape(href, quote=True)}"><title>Tile ({col},{row}) — {escape(str(entry.get("gdsTopCell", "layout")))} (Layer 20/0)</title>')
                        svg.append(f'<image x="{x}" y="{y}" width="{IMAGE_W}" height="{IMAGE_H}" preserveAspectRatio="none" href="data:image/png;base64,{png}"/>')
                        svg.append("</a>")

            svg.append(f'<rect class="tile" x="{x}" y="{y}" width="{TILE_W}" height="{TILE_H}"/>')

    svg.append("</svg>")
    args.output.write_text("\n".join(svg) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")

    if args.update_readme:
        readme_path = Path("README.md")
        readme = readme_path.read_text(encoding="utf-8")
        marker = "![MPW Layout](./USERS.svg)"
        preview = "![MPW Layout Preview](./PREVIEW.svg)"
        if preview not in readme:
            if marker not in readme:
                raise ValueError(f"Could not find {marker!r} in README.md")
            readme = readme.replace(marker, marker + "\n\n" + preview, 1)
            readme_path.write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    main()