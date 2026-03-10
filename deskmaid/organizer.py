"""File organizer - moves files into categorized folders with transaction logging."""

import json
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from deskmaid.config import HISTORY_DIR, ensure_dirs


def _resolve_conflict(dst: Path) -> Path:
    """Handle filename conflicts: file.pdf -> file_(1).pdf -> file_(2).pdf"""
    if not dst.exists():
        return dst

    stem = dst.stem
    suffix = dst.suffix
    parent = dst.parent
    counter = 1

    while True:
        new_name = f"{stem}_({counter}){suffix}"
        candidate = parent / new_name
        if not candidate.exists():
            return candidate
        counter += 1


def organize(
    desktop: Path,
    plan: list[dict],
    on_progress: Callable[[str, int, int], None] | None = None,
) -> dict:
    """Execute the organization plan. Returns the transaction log.

    Args:
        on_progress: Optional callback called after each move as (filename, index, total).
    """
    ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    moves: list[dict] = []

    # Collect category names so we don't move category folders into themselves
    cat_names = {item["category"] for item in plan}

    # Pre-filter actionable items for accurate total count
    actionable = [
        item for item in plan
        if (desktop / item["name"]).exists() and item["name"] not in cat_names
    ]
    total = len(actionable)

    for idx, item in enumerate(actionable, 1):
        filename = item["name"]
        category = item["category"]
        src = desktop / filename

        cat_dir = desktop / category
        cat_dir.mkdir(exist_ok=True)

        dst = _resolve_conflict(cat_dir / filename)
        shutil.move(str(src), str(dst))

        moves.append({
            "src": str(src),
            "dst": str(dst),
            "filename": filename,
            "category": category,
            "type": item.get("type", "file"),
        })

        if on_progress:
            on_progress(filename, idx, total)

    # Save transaction log
    log = {"timestamp": timestamp, "moves": moves}
    log_file = HISTORY_DIR / f"{timestamp}.json"
    log_file.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    return log
