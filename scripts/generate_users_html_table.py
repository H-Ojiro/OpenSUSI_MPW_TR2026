#!/usr/bin/env python3
# ----- ------ ----- ----- ------ ----- ----- ------ -----
# OpenSUSI - HTML Table Generator from Manifest
# LICENSE: Apache License Version 2.0
# ----- ------ ----- ----- ------ ----- ----- ------ -----
import argparse
import json
import os
import re
from html import escape
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path("project/manifest.json")
DEFAULT_OUTPUT = Path("USERS.html")


def normalize_string(value: Any) -> str:
    return str(value or "").strip()


def order_id_to_dir_name(order_id: Any) -> str:
    value = normalize_string(order_id)
    match = re.fullmatch(r"ORD-20([0-9]{2})([0-9]{2})([0-9]{2})-(.+)", value)

    if not match:
        return value

    yy, mm, dd, suffix = match.groups()
    return f"ORD-{yy}{mm}{dd}-{suffix}"


def get_default_repo_owner() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        return repo.split("/", 1)[0]
    return "OpenSUSI"


def get_default_repo_name() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        return repo.split("/", 1)[1]
    return "OpenSUSI_MPW_TR2026"


def get_default_branch() -> str:
    return os.environ.get("GITHUB_REF_NAME", "main")


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def filter_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        entry
        for entry in manifest.get("entries", [])
        if entry.get("type") in {"teg", "user", "fill"}
    ]


def sort_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        entries,
        key=lambda e: (
            e.get("row", 9999) if e.get("row") is not None else 9999,
            e.get("col", 9999) if e.get("col") is not None else 9999,
        ),
    )


def repo_tree_url(
    entry: dict[str, Any],
    repo_owner: str,
    repo_name: str,
    branch: str,
) -> str:
    entry_type = entry.get("type", "")
    github_id = entry.get("githubId", "-")

    if entry_type in {"teg", "fill"}:
        rel = "users/000_system"
    else:
        order_dir = order_id_to_dir_name(entry.get("orderId"))
        rel = f"users/{github_id}/{order_dir}"

    return f"https://github.com/{repo_owner}/{repo_name}/tree/{branch}/{rel}"


def entry_display_label(entry: dict[str, Any]) -> str:
    entry_type = entry.get("type", "")
    if entry_type == "teg":
        return "TEG"
    elif entry_type == "fill":
        return "EMPTY"
    else:
        return entry.get("githubId", "-")


def generate_html(
    manifest: dict[str, Any],
    repo_owner: str,
    repo_name: str,
    branch: str,
) -> str:
    grid = manifest.get("grid", {})
    grid_x = int(grid.get("x", 8))
    grid_y = int(grid.get("y", 8))

    entries = sort_entries(filter_entries(manifest))

    by_tile: dict[tuple[int, int], dict[str, Any]] = {}
    for entry in entries:
        row = entry.get("row")
        col = entry.get("col")
        if row is None or col is None:
            continue
        by_tile[(col, row)] = entry

    parts: list[str] = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "    <meta charset=\"UTF-8\">",
        "    <title>OpenSUSI MPW Users Layout</title>",
        "    <style>",
        "        body { font-family: Arial, sans-serif; margin: 20px; }",
        "        h1 { font-size: 20px; }",
        "        table { border-collapse: collapse; margin-top: 10px; }",
        "        th, td { border: 1px solid #ccc; padding: 10px 15px; text-align: center; }",
        "        th { background-color: #f0f0f0; font-weight: bold; }",
        "        td:first-child { background-color: #f0f0f0; font-weight: bold; }",
        "    </style>",
        "</head>",
        "<body>",
        "    <h1>OpenSUSI MPW Users Layout</h1>",
        "    <table>",
        "        <thead>",
        "            <tr>",
        "                <th></th>",
    ]

    for col in range(grid_x):
        parts.append(f"                <th>{col}</th>")

    parts.extend([
        "            </tr>",
        "        </thead>",
        "        <tbody>",
    ])

    for row in range(grid_y):
        parts.append("            <tr>")
        parts.append(f"                <td>{row}</td>")
        for col in range(grid_x):
            entry = by_tile.get((col, row))
            if entry is None:
                parts.append("                <td></td>")
                continue

            label = entry_display_label(entry)
            url = repo_tree_url(entry, repo_owner, repo_name, branch)
            parts.append(
                f'                <td><strong><a href="{escape(url)}" target="_blank">{escape(label)}</a></strong></td>'
            )
        parts.append("            </tr>")

    parts.extend([
        "        </tbody>",
        "    </table>",
        "</body>",
        "</html>",
    ])

    return "\n".join(parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate HTML Table from project/manifest.json"
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repo-owner", default=get_default_repo_owner())
    parser.add_argument("--repo-name", default=get_default_repo_name())
    parser.add_argument("--branch", default=get_default_branch())
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    manifest = load_manifest(args.manifest)
    html_content = generate_html(
        manifest=manifest,
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        branch=args.branch,
    )

    args.output.write_text(html_content, encoding="utf-8")

    print(f"manifest : {args.manifest}")
    print(f"output   : {args.output}")
    print(f"repo     : {args.repo_owner}/{args.repo_name}")
    print(f"branch   : {args.branch}")
    print("DONE")


if __name__ == "__main__":
    main()