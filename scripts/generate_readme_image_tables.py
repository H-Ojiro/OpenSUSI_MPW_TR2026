#!/usr/bin/env python3
"""Build linked README image tables from the generated shuttle SVG views.

Run after generate_users_svg.py and generate_preview_svg.py. Individual SVG
cards preserve the original typography; preview PNGs are external assets so
GitHub can display them without embedded data URLs.
"""
import argparse
import base64
import io

from PIL import Image, ImageChops
from copy import deepcopy
from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET

from generate_users_html_table import load_manifest, repo_tree_url

NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
START = "<!-- BEGIN MPW IMAGE TABLES -->"
END = "<!-- END MPW IMAGE TABLES -->"


def generate_table(source, kind, manifest, assets, owner, repo, branch, site_dir, base_url):
    root = ET.parse(source).getroot()
    cols = int(manifest.get("grid", {}).get("x", 8))
    rows = int(manifest.get("grid", {}).get("y", 8))
    entries = {(e.get("col"), e.get("row")): e
               for e in manifest.get("entries", [])
               if e.get("type") in {"teg", "user", "fill"}}
    cards = {}
    # Each linked group contains either a tile rectangle or a layout image.
    for link in root.findall(f"{{{NS}}}a"):
        children = list(link)
        position = next((e for e in children if e.tag in
                         {f"{{{NS}}}rect", f"{{{NS}}}image"}), None)
        if position is None:
            continue
        col = round((float(position.get("x")) - 60) / 140)
        row = round((float(position.get("y")) - 70) / 90)
        cards[col, row] = children

    title = ("OpenSUSI MPW Users Layout" if kind == "users"
             else "OpenSUSI MPW Layout Preview (Layer 20/0)")
    lines = [f"### {title}", "", '<table border="1" cellspacing="0" cellpadding="0" style="border-collapse: collapse; border-spacing: 0;">',
             '  <thead><tr><th style="border: 1px solid #555; padding: 0;"></th>' + ''.join(
                 f'<th scope="col" align="center" style="border: 1px solid #555; padding: 0;">{c}</th>' for c in range(cols))
             + '</tr></thead>', '  <tbody>']
    for row in range(rows):
        lines.append(f'    <tr><th scope="row" style="border: 1px solid #555; padding: 0;">{row}</th>')
        for col in range(cols):
            x, y = 60 + col * 140, 70 + row * 90
            card = ET.Element(f"{{{NS}}}svg", {
                "width": "140", "height": "90", "viewBox": f"{x} {y} 140 90"})
            for style in root.findall(f"{{{NS}}}style"):
                card.append(deepcopy(style))
            ET.SubElement(card, f"{{{NS}}}rect", {
                "x": str(x), "y": str(y), "width": "140", "height": "90",
                "fill": "white", "stroke": "#555" if kind == "preview" else "black"})
            text = []
            for element in cards.get((col, row), []):
                element = deepcopy(element)
                if element.tag == f"{{{NS}}}image":
                    png_name = f"{kind}-{row}-{col}.png"
                    data = element.get("href", "")
                    png = Image.open(io.BytesIO(base64.b64decode(data.split(",", 1)[1]))).convert("RGB")
                    bounds = ImageChops.difference(png, Image.new("RGB", png.size, "white")).getbbox()
                    if bounds:
                        # Remove the wide renderer canvas without distorting geometry.
                        left, top, right, bottom = bounds
                        side = max(right - left, bottom - top)
                        cx, cy = (left + right) / 2, (top + bottom) / 2
                        png = png.crop((round(cx - side / 2), round(cy - side / 2),
                                        round(cx - side / 2) + side, round(cy - side / 2) + side))
                    else:
                        png = Image.new("RGB", (72, 72), "white")
                    png.save(assets / png_name, optimize=True)
                    element.set("href", png_name)
                if element.tag == f"{{{NS}}}text":
                    text.append(''.join(element.itertext()))
                card.append(element)
            filename = assets / f"{kind}-{row}-{col}.svg"
            if kind == "users" or not cards.get((col, row)):
                ET.ElementTree(card).write(filename, encoding="utf-8", xml_declaration=True)
            # Use standalone PNGs directly for layout previews. The original
            # Crop away the renderer canvas and display square layout tiles.
            src = assets / f"{kind}-{row}-{col}.png" if kind == "preview" and cards.get((col, row)) else filename
            width, height = (140, 140) if src.suffix == '.png' else (140, 90)
            alt = escape(' — '.join(text) or f"Layout tile ({col},{row})", quote=True)
            image_url = escape(base_url.rstrip("/") + "/" + src.relative_to(site_dir).as_posix(), quote=True)
            image = f'<img src="{image_url}" width="{width}" height="{height}" alt="{alt}" style="display: block; margin: 0; padding: 0; vertical-align: top;">'
            entry = entries.get((col, row))
            if entry:
                url = escape(repo_tree_url(entry, owner, repo, branch), quote=True)
                image = f'<a href="{url}" style="display: block; margin: 0; padding: 0; line-height: 0;">{image}</a>'
            lines.append(f'      <td align="center" valign="top" style="border: 1px solid #555; padding: 0; font-size: 0; line-height: 0; vertical-align: top;">{image}</td>')
        lines.append('    </tr>')
    lines.extend(['  </tbody>', '</table>'])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path('project/manifest.json'))
    parser.add_argument('--assets', type=Path, default=Path('_site/images/mpw'))
    parser.add_argument('--site-dir', type=Path, default=Path('_site'))
    parser.add_argument('--image-base-url', help='Published Pages base URL, including any repository path')
    parser.add_argument('--readme', type=Path, default=Path('README.md'))
    parser.add_argument('--repo-owner', default='OpenSUSI')
    parser.add_argument('--repo-name', default='OpenSUSI_MPW_TR2026')
    parser.add_argument('--branch', default='main')
    args = parser.parse_args()
    base_url = args.image_base_url or f"https://{args.repo_owner.lower()}.github.io/{args.repo_name}"
    manifest = load_manifest(args.manifest)
    args.assets.mkdir(parents=True, exist_ok=True)
    tables = [generate_table(source, kind, manifest, args.assets,
                            args.repo_owner, args.repo_name, args.branch, args.site_dir, base_url)
              for source, kind in [('USERS.svg', 'users'), ('PREVIEW.svg', 'preview')]]
    args.site_dir.mkdir(parents=True, exist_ok=True)
    (args.site_dir / '.nojekyll').touch()
    page = ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>OpenSUSI MPW Layout</title>'
            '<style>body{font-family:Arial,sans-serif}table{border-collapse:collapse}'
            'td,th{padding:0;border:1px solid #555}td{line-height:0}img{display:block}</style>'
            '<body>' + '\n'.join(t.replace('### ' + t.splitlines()[0][4:],
                                         '<h2>' + escape(t.splitlines()[0][4:]) + '</h2>', 1)
                                  for t in tables) + '</body></html>')
    (args.site_dir / 'index.html').write_text(page, encoding='utf-8')
    section = START + '\n\nClick a tile to open its project repository or submission directory.\n\n' + '\n\n'.join(tables) + '\n\n' + END
    readme = args.readme.read_text()
    if START in readme:
        start, end = readme.index(START), readme.index(END) + len(END)
    else:
        start = readme.index('### Interactive Layout (SVG)')
        end = readme.index('\n---', readme.index('</table>', start))
    args.readme.write_text(readme[:start] + section + readme[end:])


if __name__ == '__main__':
    main()
