"""Undo mechanism - reverses the last organization operation."""

import json
import shutil
from pathlib import Path

from deskmaid.config import HISTORY_DIR, ensure_dirs


def get_history_logs() -> list[Path]:
    ensure_dirs()
    logs = sorted(HISTORY_DIR.glob("*.json"), reverse=True)
    return logs


def get_last_log() -> dict | None:
    logs = get_history_logs()
    if not logs:
        return None
    return json.loads(logs[0].read_text(encoding="utf-8"))


def undo_last() -> dict | None:
    """Undo the most recent operation. Returns the log that was undone, or None."""
    logs = get_history_logs()
    if not logs:
        return None

    log_file = logs[0]
    log = json.loads(log_file.read_text(encoding="utf-8"))

    for move in reversed(log.get("moves", [])):
        dst = Path(move["dst"])
        src = Path(move["src"])

        if dst.exists():
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst), str(src))

    # Remove empty category directories
    for move in log.get("moves", []):
        dst_dir = Path(move["dst"]).parent
        if dst_dir.exists() and not any(dst_dir.iterdir()):
            dst_dir.rmdir()

    log_file.unlink()
    return log
