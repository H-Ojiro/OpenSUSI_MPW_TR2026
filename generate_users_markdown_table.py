#!/usr/bin/env python3
# ----- ------ ----- ----- ------ ----- ----- ------ -----
# OpenSUSI - Markdown Table Generator from Manifest
# LICENSE: Apache License Version 2.0
# ----- ------ ----- ----- ------ ----- ----- ------ -----
import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path("project/manifest.json")


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

    # Using 'tree' instead of 'blob' for directory listings as in your example
    return f"https://github.com/{repo_owner}/{repo_name}/tree/{branch}/{rel}"


def entry_display_label(entry: dict[str, Any]) -> str:
    entry_type = entry.get("type", "")
    if entry_type == "teg":
        return "TEG"
    elif entry_type == "fill":
        return "EMPTY"
    else:
        return entry.get("githubId", "-")


def generate_markdown_table(
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

    # Header row
    header_cols = ["   "] + [str(col) for col in range(grid_x)]
    lines = ["| " + " | ".join(header_cols) + " |"]

    # Separator row
    separator_cols = ["---"] * (grid_x + 1)
    lines.append("| " + " | ".join(separator_cols) + " |")

    # Data rows
    for row in range(grid_y):
        row_cells = [str(row)]
        for col in range(grid_x):
            entry = by_tile.get((col, row))
            if entry is None:
                row_cells.append("")
                continue

            label = entry_display_label(entry)
            url = repo_tree_url(entry, repo_owner, repo_name, branch)
            row_cells.append(f"**[{label}]({url})**")

        lines.append("| " + " | ".join(row_cells) + " |")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Markdown Table from project/manifest.json"
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--repo-owner", default=get_default_repo_owner())
    parser.add_argument("--repo-name", default=get_default_repo_name())
    parser.add_argument("--branch", default=get_default_branch())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    markdown_table = generate_markdown_table(
        manifest=manifest,
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        branch=args.branch,
    )
    print(markdown_table)


if __name__ == "__main__":
    main()